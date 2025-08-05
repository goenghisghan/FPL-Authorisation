import requests
import os
import json

# Load environment variables
gist_id = os.getenv("GIST_ID")  # e.g. abc1234567890defgh
gist_token = os.getenv("GIST_TOKEN")  # stored in GitHub Secrets

gist_url = f"https://api.github.com/gists/{gist_id}"
headers = {
    "Authorization": f"Bearer {gist_token}",
    "Accept": "application/vnd.github.v3+json"
}

# Step 1: Fetch the existing token JSON from the Gist
response = requests.get(gist_url, headers=headers)
data = response.json()

file_key = list(data["files"].keys())[0]
token_json = json.loads(data["files"][file_key]["content"])

refresh_token = token_json["refresh_token"]

# Step 2: Use the refresh_token to get new tokens
url = "https://account.premierleague.com/as/token"
payload = {
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    "client_id": "bfcbaf69-aade-4c1b-8f00-c1cb8a193030",
}
headers_token = {"Content-Type": "application/x-www-form-urlencoded"}

response = requests.post(url, data=payload, headers=headers_token)
tokens = response.json()

# Optional: print access token for testing
print("\n=== NEW ACCESS TOKEN (base64) ===")
import base64
print(base64.b64encode(tokens["access_token"].encode()).decode())
print("=== END ===")

# Step 3: Save updated tokens back to the Gist
new_token_data = {
    "refresh_token": tokens["refresh_token"],
    "access_token": tokens["access_token"]
}

update_payload = {
    "files": {
        file_key: {
            "content": json.dumps(new_token_data, indent=2)
        }
    }
}

update_response = requests.patch(gist_url, headers=headers, json=update_payload)
if update_response.status_code == 200:
    print("✅ Token Gist updated successfully.")
else:
    print("❌ Failed to update Gist:", update_response.text)
