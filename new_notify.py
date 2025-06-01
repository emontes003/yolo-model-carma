import json
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# === CONFIG ===
SERVICE_ACCOUNT_FILE = 'capstone-carma-firebase-2.json'  # Replace with your file
PROJECT_ID = 'capstone-carma'

# === AUTH ===
SCOPES = ['https://www.googleapis.com/auth/datastore']
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
credentials.refresh(Request())

# === FIRESTORE ENDPOINT ===
url = f'https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/notifications'

# === DATA TO SEND ===
data = {
    "fields": {
        "title": {"stringValue": "🚨 CARMA Alert"},
        "body": {"stringValue": "YOLO detected a person"},
        "type": {"stringValue": "person"},
        "timestamp": {"timestampValue": "2025-04-15T23:00:00Z"}  # or use ISO 8601 formatted string
    }
}

# === SEND ===
headers = {
    "Authorization": f"Bearer {credentials.token}",
    "Content-Type": "application/json"
}

response = requests.post(url, headers=headers, json=data)

print(f"Status: {response.status_code}")
print("Response:", response.text)
