# google_utils.py
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def create_drive_folder(folder_name, parent_id=None):
    try:
        print(f"🚀 Creating folder: {folder_name}")
        service = get_drive_service()

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        # Step 1: create folder
        folder = service.files().create(
            body=metadata, fields="id, name"
        ).execute()

        print(f"✅ Folder created with ID: {folder['id']}")

        # Step 2: get webViewLink
        folder = service.files().get(
            fileId=folder["id"], fields="id, name, webViewLink"
        ).execute()

        print(f"🌐 webViewLink:", folder.get("webViewLink"))

        # Step 3: add permission (optional)
        permission = {
            "type": "user",
            "role": "writer",
            "emailAddress": "marialynmirabel20@gmail.com",
        }
        service.permissions().create(
            fileId=folder["id"], body=permission, fields="id"
        ).execute()

        return folder

    except Exception as e:
        print("❌ Drive folder creation error:", e)
        return {"id": None, "webViewLink": ""}

