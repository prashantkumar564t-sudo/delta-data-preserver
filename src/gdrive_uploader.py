import os
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode

TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"

def get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Fetches a fresh short-lived access_token using standard urllib."""
    payload = urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")

    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["access_token"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Failed to refresh access token: {e.code} - {error_body}")

def upload_file_to_drive(
    local_filepath: str, 
    folder_id: str = None, 
    client_id: str = None, 
    client_secret: str = None, 
    refresh_token: str = None
) -> bool:
    """
    Uploads file to Google Drive using multipart/related payload with zero external packages.
    """
    if not os.path.exists(local_filepath):
        print(f"[!] Local file not found: {local_filepath}")
        return False

    # Pull credentials from environment if not passed directly
    f_id = folder_id or os.getenv("GDRIVE_FOLDER_ID", "1aVINc1rkrbnaVfATjkMj8yw-JlidKFpe")
    c_id = client_id or os.getenv("GDRIVE_CLIENT_ID")
    c_secret = client_secret or os.getenv("GDRIVE_CLIENT_SECRET")
    r_token = refresh_token or os.getenv("GDRIVE_REFRESH_TOKEN")

    if not (c_id and c_secret and r_token):
        print("[!] Missing OAuth credentials: GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, or GDRIVE_REFRESH_TOKEN.")
        return False

    filename = os.path.basename(local_filepath)
    print(f"[*] Refreshing access token via Google OAuth...")
    
    try:
        access_token = get_access_token(c_id, c_secret, r_token)
    except Exception as e:
        print(f"[!] Token refresh failed: {e}")
        return False

    # Prepare multipart body (metadata + binary file)
    boundary = "===============DeltaDataPreserverBoundary=="
    metadata = {
        "name": filename,
        "parents": [f_id]
    }

    metadata_part = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
    ).encode("utf-8")

    with open(local_filepath, "rb") as f:
        file_bytes = f.read()

    file_part_header = (
        f"--{boundary}\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")

    closing_part = f"\r\n--{boundary}--\r\n".encode("utf-8")

    body = metadata_part + file_part_header + file_bytes + closing_part

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
        "Content-Length": str(len(body))
    }

    print(f"[*] Uploading '{filename}' ({len(file_bytes) / 1024:.2f} KB) to Google Drive...")
    req = urllib.request.Request(DRIVE_UPLOAD_URL, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            print(f"[✓] File successfully uploaded to Google Drive! File ID: {resp_data.get('id')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[!] Drive upload failed: {e.code} - {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"[!] Network error during upload: {e}")
        return False

if __name__ == "__main__":
    from src.config import load_env, DEFAULT_GDRIVE_FOLDER_ID
    load_env()
    target_folder = os.getenv("GDRIVE_FOLDER_ID", DEFAULT_GDRIVE_FOLDER_ID)
    test_file = os.path.join("data", "options", "BTC", "BTC_options_2026-11-09.parquet")
    upload_file_to_drive(test_file, target_folder)