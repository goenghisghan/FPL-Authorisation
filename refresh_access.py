import requests
import os
import json

# Load environment variables
GIST_ID = os.environ["GIST_ID"]
GITHUB_TOKEN = os.environ["GIST_TOKEN"]
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

# GitHub API headers (used only for gist fetch/update)
github_headers = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Step 1: Load tokens from the Gist
resp = requests.get(GIST_API_URL, headers=github_headers)
if resp.status_code != 200:
    print("❌ Failed to fetch gist")
    print(resp.status_code, resp.text)
    raise Exception("Failed to load gist")

gist_data = resp.json()
filename = list(gist_data["files"].keys())[0]
tokens = json.loads(gist_data["files"][filename]["content"])

refresh_token = tokens.get("refresh_token")
if not refresh_token:
    raise Exception("❌ No refresh_token found in gist")

# Step 2: Refresh the access token using the refresh token
token_url = "https://account.premierleague.com/as/token"
token_data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
token_headers = {"Content-Type": "application/x-www-form-urlencoded"}

response = requests.post(token_url, data=token_data, headers=token_headers)
if response.status_code != 200:
    print("=== RAW RESPONSE TEXT ===")
    print(response.status_code)
    print(response.text)
    print("=== END RAW RESPONSE ===")
    raise Exception("❌ Failed to refresh access token")

token_response = response.json()
new_access_token = token_response.get("access_token")
new_refresh_token = token_response.get("refresh_token")

if not new_access_token or not new_refresh_token:
    raise Exception("❌ Missing tokens in token response")

# Step 3: Save updated tokens back to the Gist
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

update_resp = requests.patch(GIST_API_URL, headers=github_headers, json=update_payload)
if update_resp.status_code != 200:
    print("❌ Failed to update Gist")
    print(update_resp.status_code, update_resp.text)
    raise Exception("Failed to update Gist")

print("✅ Access token refreshed and Gist updated successfully.")
