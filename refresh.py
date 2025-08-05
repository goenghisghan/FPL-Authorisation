import requests
import os
import json

# === Step 1: Load existing tokens from GitHub Gist ===

GIST_ID = os.environ["GIST_ID"]
GITHUB_TOKEN = os.environ["GIST_TOKEN"]
GIST_API_URL = f"https://api.github.com/gists/{GIST_ID}"

headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
resp = requests.get(GIST_API_URL, headers=headers)
gist_data = resp.json()

# Extract the refresh_token from the Gist
filename = list(gist_data["files"].keys())[0]
tokens = json.loads(gist_data["files"][filename]["content"])
refresh_token = tokens["refresh_token"]

# === Step 2: Use refresh_token to request new tokens ===

url = "https://account.premierleague.com/as/token"
data = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
headers["Content-Type"] = "application/x-www-form-urlencoded"

# First get the raw response for debug purposes
raw_response = requests.post(url, data=data, headers=headers)

print("=== RAW RESPONSE TEXT ===")
print("Status code:", raw_response.status_code)
print(raw_response.text)
print("=== END RAW RESPONSE ===")

# Then parse as JSON
response = raw_response.json()

# === Step 3: Extract and update tokens ===

if "access_token" not in response or "refresh_token" not in response:
    raise Exception("❌ Failed to refresh token. Check logs above for details.")

new_access_token = response["access_token"]
new_refresh_token = response["refresh_token"]

# Save new tokens back to Gist
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

if update_resp.status_code == 200:
    print("✅ Tokens successfully refreshed and stored in Gist.")
else:
    print("❌ Failed to update Gist.")
    print(update_resp.status_code, update_resp.text)
