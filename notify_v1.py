import json
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.cloud import firestore


# === CONFIG ===
SERVICE_ACCOUNT_FILE = 'capstone-carma-firebase-2.json'  # Your downloaded file
#DEVICE_TOKEN = 'fm9_wF7OQvurynCOlxMI7L:APA91bFboepCnwTVTZ0u6Ekt3sY2LnzRGoDLYEisqu46rUXuSmxhSZg4el9qsFjXqoEACA3sZ2_pJvQyBseRNovTNR3bvfcZumpmucIGwhNK8-RR1Ss4KA4'  # From your app logs
PROJECT_ID = 'capstone-carma'  # e.g. capstone-carma


# === AUTH ===
SCOPES = ['https://www.googleapis.com/auth/firebase.messaging']


# === AUTH ===
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
credentials.refresh(Request())
db = firestore.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)

# === SEND ALERT FUNCTION ===
def send_alert(type, body):
    title = "🚨 CARMA Alert"

    # Fetch the latest token each time
    doc = db.collection("devices").document("my-device").get()
    DEVICE_TOKEN = doc.to_dict()["token"]

    # Prepare headers and URL
    url = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"
    headers = {
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json; UTF-8',
    }

    # Create push payload
    payload = {
        "message": {
            "token": DEVICE_TOKEN,
            "notification": {
                "title": title,
                "body": body
            }
        }
    }

    # Send push notification
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"✅ Push sent: {response.status_code}")
    except Exception as e:
        print("❌ Push send error:", e)

    # Save to Firestore
    try:
        db.collection('notifications').add({
            'title': title,
            'body': body,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'type': type
        })
        print("✅ Notification stored in Firestore")
    except Exception as e:
        print("❌ Firestore error:", e)


# === EXAMPLE USAGE ===
if __name__ == '__main__':
    send_alert("alert", "YOLO detected a person near your car.")