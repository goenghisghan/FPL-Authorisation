import base64
import hashlib
import os
import re
import secrets
import uuid
import json
import requests
from dotenv import load_dotenv

load_dotenv()

URLS = {
    "auth": "https://account.premierleague.com/as/authorize",
    "start": "https://account.premierleague.com/davinci/policy/262ce4b01d19dd9d385d26bddb4297b6/start",
    "login": "https://account.premierleague.com/davinci/connections/0d8c928e4970386733ce110b9dda8412/capabilities/customHTMLTemplate",
    "resume": "https://account.premierleague.com/as/resume",
    "token": "https://account.premierleague.com/as/token",
    "me": "https://fantasy.premierleague.com/api/me/",
}

def generate_code_verifier():
    return secrets.token_urlsafe(64)[:128]

def generate_code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")

def update_gist_with_tokens(access_token, refresh_token):
    GIST_ID = os.environ["GIST_ID"]
    GIST_TOKEN = os.environ["GIST_TOKEN"]
    GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

    headers = {"Authorization": f"Bearer {GIST_TOKEN}"}
    resp = requests.get(GIST_API_URL, headers=headers)
    resp.raise_for_status()
    gist_data = resp.json()

    filename = list(gist_data["files"].keys())[0]

    tokens_content = json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token
    }, indent=2)

    update_payload = {
        "files": {
            filename: {
                "content": tokens_content
            }
        }
    }

    update_resp = requests.patch(GIST_API_URL, headers=headers, json=update_payload)
    update_resp.raise_for_status()
    print("✅ Tokens successfully saved to Gist.")

code_verifier = generate_code_verifier()
code_challenge = generate_code_challenge(code_verifier)
initial_state = uuid.uuid4().hex

session = requests.Session()
session.headers.update({
    # Some IdP branches are UA/Accept-sensitive
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
})

def expect_json(resp: requests.Response) -> dict:
    """Raise for HTTP errors and return JSON; if JSON fails, print diagnostics."""
    try:
        resp.raise_for_status()
    except Exception:
        # Print body to help debugging on CI
        print("HTTP error from DaVinci endpoint:", file=sys.stderr)
        print("Status:", resp.status_code, file=sys.stderr)
        print("Headers:", dict(resp.headers), file=sys.stderr)
        print("Body:", resp.text[:2000], file=sys.stderr)
        raise
    try:
        return resp.json()
    except ValueError:
        print("Non-JSON response from DaVinci endpoint:", file=sys.stderr)
        print("Status:", resp.status_code, file=sys.stderr)
        print("Headers:", dict(resp.headers), file=sys.stderr)
        print("Body:", resp.text[:2000], file=sys.stderr)
        raise

# Step 1: Request authorization page
params = {
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
    "redirect_uri": "https://fantasy.premierleague.com/",
    "response_type": "code",
    "scope": "openid profile email offline_access",
    "state": initial_state,
    "code_challenge": code_challenge,
    "code_challenge_method": "S256",
}
auth_response = session.get(URLS["auth"], params=params)
login_html = auth_response.text

access_token = re.search(r'"accessToken":"([^"]+)"', login_html).group(1)
new_state = re.search(r'<input[^>]+name="state"[^>]+value="([^"]+)"', login_html).group(1)

# Step 2: Use accessToken to get interaction id and token
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
start_resp = session.post(URLS["start"], headers=headers)
data = expect_json(start_resp)

# Log unexpected payloads
if "interactionToken" not in data:
    print("DaVinci /start payload did not include 'interactionToken'. Full payload:", file=sys.stderr)
    print(json.dumps(data, indent=2)[:4000], file=sys.stderr)

# Try common keys and then fail cleanly
interaction_id = data.get("interactionId") or data.get("id")
interaction_token = (
    data.get("interactionToken")
    or data.get("interactionJwt")
    or data.get("token")
)

if not interaction_id or not interaction_token:
    raise RuntimeError(
        "Login flow changed: missing interactionId/interactionToken from /start. "
        "See stderr for the raw payload. "
        "This usually means the IdP returned an error or a different policy branch. "
        "Try re-running locally to capture the exact payload."
    )

# Step 3: log in with interaction tokens (2 POST requests)
response = session.post(
    URLS["login"],
    headers={"interactionId": interaction_id, "interactionToken": interaction_token},
    json={
        "id": response["id"],
        "eventName": "continue",
        "parameters": {"eventType": "polling"},
        "pollProps": {"status": "continue", "delayInMs": 10, "retriesAllowed": 1, "pollChallengeStatus": False},
    },
)

response = session.post(
    URLS["login"],
    headers={"interactionId": interaction_id, "interactionToken": interaction_token},
    json={
        "id": response.json()["id"],
        "nextEvent": {
            "constructType": "skEvent",
            "eventName": "continue",
            "params": [],
            "eventType": "post",
            "postProcess": {},
        },
        "parameters": {
            "buttonType": "form-submit",
            "buttonValue": "SIGNON",
            "username": os.getenv("EMAIL"),
            "password": os.getenv("PASSWORD"),
        },
        "eventName": "continue",
    },
)
print("Login step response JSON:")
print(response.json())
dv_response = response.json()["dvResponse"]

# Step 4: Resume login and handle redirect
response = session.post(
    URLS["resume"],
    data={"dvResponse": dv_response, "state": new_state},
    allow_redirects=False,
)

location = response.headers["Location"]
auth_code = re.search(r"[?&]code=([^&]+)", location).group(1)

# Step 5: Exchange auth code for access token
response = session.post(
    URLS["token"],
    data={
        "grant_type": "authorization_code",
        "redirect_uri": "https://fantasy.premierleague.com/",
        "code": auth_code,
        "code_verifier": code_verifier,
        "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
    },
)
response.raise_for_status()
token_response = response.json()

refresh_token = token_response.get("refresh_token")
access_token = token_response.get("access_token")

# Just update the gist directly with raw tokens, no encoding or printing
update_gist_with_tokens(access_token, refresh_token)

print("✅ Login complete and tokens saved to Gist.")
