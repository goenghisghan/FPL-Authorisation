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

filename = list(gist_data["files"].keys())[0]
tokens = json.loads(gist_data["files"][filename]["content"])
refresh_token = tokens["refresh_token"]

# Step 2: Refresh access token only
url = "https://account.premierleague.com/as/token"
data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
headers.update({"Content-Type": "application/x-www-form-urlencoded"})

response = requests.post(url, data=data, headers=headers)
response_data = response.json()

if response.status_code != 200:
    print("=== RAW RESPONSE TEXT ===")
    print(response.text)
    print("=== END RAW RESPONSE ===")
    raise Exception("❌ Failed to refresh access token. Check logs above for details.")

new_access_token = response_data["access_token"]

# Step 3: Update Gist with new access_token but keep old refresh_token
tokens["access_token"] = new_access_token

new_content = json.dumps(tokens, indent=2)

update_payload = {
    "files": {
        filename: {
            "content": new_content
        }
    }
}
update_resp = requests.patch(GIST_API_URL, headers=headers, json=update_payload)

if update_resp.status_code == 200:
    print("✅ Access token successfully refreshed and updated in Gist.")
else:
    print("❌ Failed to update Gist with new access token.")
    print(update_resp.text)
