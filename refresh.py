import requests
import os
import json

GIST_ID = os.environ["GIST_ID"]
GITHUB_TOKEN = os.environ["GIST_TOKEN"]
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

# Step 1: Load existing tokens from the Gist
headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
resp = requests.get(GIST_API_URL, headers=headers)
gist_data = resp.json()

# Load the content from the Gist file
filename = list(gist_data["files"].keys())[0]
tokens = json.loads(gist_data["files"][filename]["content"])
refresh_token = tokens["refresh_token"]

# Step 2: Refresh the tokens
url = "https://account.premierleague.com/as/token"
data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
headers["Content-Type"] = "application/x-www-form-urlencoded"

response = requests.post(url, data=data, headers=headers).json()
new_access_token = response["access_token"]
new_refresh_token = response["refresh_token"]

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

print("✅ Tokens successfully refreshed and stored in Gist.")
