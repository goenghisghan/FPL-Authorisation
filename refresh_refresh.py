import requests
import os
import json

# Load environment variables
GIST_ID = os.environ["GIST_ID"]
GITHUB_TOKEN = os.environ["GIST_TOKEN"]
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

# Step 1: Load tokens from Gist
headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
resp = requests.get(GIST_API_URL, headers=headers)
if resp.status_code != 200:
    raise Exception(f"❌ Failed to fetch Gist: {resp.status_code}\n{resp.text}")

gist_data = resp.json()
filename = list(gist_data["files"].keys())[0]
tokens = json.loads(gist_data["files"][filename]["content"])
refresh_token = tokens["refresh_token"]

# Step 2: Use refresh_token to get new access_token AND refresh_token
url = "https://account.premierleague.com/as/token"
data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
headers["Content-Type"] = "application/x-www-form-urlencoded"

response = requests.post(url, data=data, headers=headers)
if response.status_code != 200:
    print("=== RAW RESPONSE TEXT ===")
    print(response.status_code, response.text)
    print("=== END RAW RESPONSE ===")
    raise Exception("❌ Failed to refresh token. Check logs above for details.")

token_response = response.json()
new_access_token = token_response.get("access_token")
new_refresh_token = token_response.get("refresh_token")

if not new_access_token or not new_refresh_token:
    raise Exception("❌ Missing tokens in response.")

# Step 3: Save updated tokens back to Gist
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
    raise Exception(f"❌ Failed to update Gist: {update_resp.status_code}\n{update_resp.text}")

print("✅ Refresh token and access token successfully updated in Gist.")
