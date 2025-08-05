import requests
import os
import json

GIST_ID = os.environ["GIST_ID"]
GITHUB_TOKEN = os.environ["GIST_TOKEN"]
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

# Headers for GitHub API
headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

# Step 1: Load tokens from the Gist
resp = requests.get(GIST_API_URL, headers=headers)
gist_data = resp.json()

filename = list(gist_data["files"].keys())[0]
tokens = json.loads(gist_data["files"][filename]["content"])

refresh_token = tokens["refresh_token"]

# Step 2: Refresh the access token using the refresh token
url = "https://account.premierleague.com/as/token"
data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
headers.update({"Content-Type": "application/x-www-form-urlencoded"})

response = requests.post(url, data=data, headers=headers)
if response.status_code != 200:
    print("Failed to refresh token:")
    print(response.status_code, response.text)
    raise Exception("Failed to refresh token")

token_response = response.json()

new_access_token = token_response.get("access_token")
new_refresh_token = token_response.get("refresh_token")

if not new_access_token or not new_refresh_token:
    raise Exception("Missing tokens in response")

# Step 3: Save the updated tokens back to the Gist
new_content = json.dumps({
    "access_token": new_access_token,
    "refresh_token": new_refresh_token,
}, indent=2)

update_payload = {
    "files": {
        filename: {
            "content": new_content
        }
    }
}

update_resp = requests.patch(GIST_API_URL, headers=headers, json=update_payload)
if update_resp.status_code != 200:
    print("Failed to update Gist:")
    print(update_resp.status_code, update_resp.text)
    raise Exception("Failed to update Gist")

print("✅ Access token refreshed and tokens updated in Gist.")
