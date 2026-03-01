import base64
import hashlib
import os
import re
import secrets
import uuid
import json
import requests
import sys
from dotenv import load_dotenv

load_dotenv()

URLS = {
    "auth": "https://account.premierleague.com/as/authorize",
    "start": "https://account.premierleague.com/davinci/policy/262ce4b01d19dd9d385d26bddb4297b6/start",
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

# Step 2: Start the DaVinci flow
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
start_resp = session.post(URLS["start"], headers=headers)
start_data = expect_json(start_resp)

# The /start response now returns a PingOne Protect SDK polling screen as the
# first step (bot-detection).  interactionToken is no longer issued; session
# cookies set during this request handle auth on subsequent calls.
interaction_id = start_data.get("interactionId")
node_id        = start_data.get("id")
connection_id  = start_data.get("connectionId")

print("DaVinci /start response:", file=sys.stderr)
print(json.dumps(start_data, indent=2)[:2000], file=sys.stderr)

if not interaction_id or not node_id or not connection_id:
    raise RuntimeError(
        f"Login flow error: /start missing required fields "
        f"(interactionId={interaction_id}, id={node_id}, connectionId={connection_id})"
    )

def davinci_url(cid):
    return (
        f"https://account.premierleague.com/davinci/connections"
        f"/{cid}/capabilities/customHTMLTemplate"
    )

# Step 3a: Advance the Protect SDK polling screen.
# We submit an empty protectsdk payload (no real browser signals) to move the
# flow forward to the actual login form.
protect_resp = session.post(
    davinci_url(connection_id),
    headers={"interactionId": interaction_id},
    json={
        "id": node_id,
        "eventName": "continue",
        "parameters": {"protectsdk": ""},
    },
)
protect_data = expect_json(protect_resp)
print("Step 3a (Protect step) response:", file=sys.stderr)
print(json.dumps(protect_data, indent=2)[:2000], file=sys.stderr)

login_node_id      = protect_data.get("id")
login_connection_id = protect_data.get("connectionId", connection_id)

if not login_node_id:
    print("Full Protect step response:", file=sys.stderr)
    print(json.dumps(protect_data, indent=2)[:4000], file=sys.stderr)
    raise RuntimeError("Login flow error: no node id in Protect step response")

# Step 3b: Submit credentials to the login form.
# The new DaVinci template does not define a buttonType field and the button's
# onClick has no postProcess — so we drop nextEvent/buttonType and send only
# the three fields the form declares: username, password, buttonValue.
response = session.post(
    davinci_url(login_connection_id),
    headers={"interactionId": interaction_id},
    json={
        "id": login_node_id,
        "eventName": "continue",
        "parameters": {
            "username": os.getenv("EMAIL"),
            "password": os.getenv("PASSWORD"),
            "buttonValue": "SIGNON",
        },
    },
)
login_resp_data = expect_json(response)
print("Step 3b (login) response:", file=sys.stderr)
print(json.dumps(login_resp_data, indent=2)[:2000], file=sys.stderr)

dv_response = login_resp_data.get("dvResponse")
if not dv_response:
    raise RuntimeError(f"No dvResponse in login response: {json.dumps(login_resp_data)[:2000]}")

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
