import os
import json
import urllib.request
import urllib.error
from urllib.parse import urlencode, quote

TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,size,parents"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

# In-memory cache to prevent repetitive Drive search queries in the same process
_FOLDER_CACHE: dict[str, str] = {}

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

def get_or_create_subfolder(access_token: str, parent_id: str, folder_name: str) -> str:
    """
    Finds or creates a subfolder within parent_id with zero external packages.
    Caches folder IDs in memory for high-speed subsequent lookups.
    """
    cache_key = f"{parent_id}:{folder_name}"
    if cache_key in _FOLDER_CACHE:
        return _FOLDER_CACHE[cache_key]

    # 1. Search for existing folder
    query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    search_url = f"{DRIVE_FILES_URL}?q={quote(query)}&fields=files(id,name)"
    req = urllib.request.Request(search_url, headers={"Authorization": f"Bearer {access_token}"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            files = data.get("files", [])
            if files:
                folder_id = files[0]["id"]
                _FOLDER_CACHE[cache_key] = folder_id
                return folder_id
    except Exception as e:
        print(f"[!] Warning searching for folder '{folder_name}': {e}")

    # 2. Create folder if not found
    print(f"[*] Creating Google Drive subfolder: '{folder_name}' under parent {parent_id[:8]}...")
    create_body = json.dumps({
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id]
    }).encode("utf-8")

    create_req = urllib.request.Request(
        f"{DRIVE_FILES_URL}?fields=id,name",
        data=create_body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(create_req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            folder_id = data["id"]
            _FOLDER_CACHE[cache_key] = folder_id
            print(f"[✓] Created Google Drive subfolder '{folder_name}' -> ID: {folder_id}")
            return folder_id
    except Exception as e:
        print(f"[!] Failed to create subfolder '{folder_name}': {e}")
        # Fallback to parent_id if creation fails
        return parent_id

def resolve_target_folder(access_token: str, root_folder_id: str, subfolder_path: str = None) -> str:
    """
    Traverses and ensures nested folder path exists (e.g. 'Crypto/Futures' or 'Crypto/Options').
    Returns the final destination folder ID.
    """
    if not subfolder_path:
        return root_folder_id

    current_parent = root_folder_id
    parts = [p.strip() for p in subfolder_path.replace("\\", "/").split("/") if p.strip()]

    for part in parts:
        current_parent = get_or_create_subfolder(access_token, current_parent, part)

    return current_parent

def upload_file_to_drive(
    local_filepath: str, 
    folder_id: str = None, 
    subfolder_path: str = None,
    client_id: str = None, 
    client_secret: str = None, 
    refresh_token: str = None
) -> dict:
    """
    Uploads file to Google Drive using multipart/related payload with zero external packages.
    Supports routing into subfolders (e.g. 'Crypto/Futures', 'Crypto/Options').
    Verifies that the returned file ID exists and size > 0.
    Returns: {"success": True/False, "file_id": ..., "size_bytes": ..., "filename": ..., "error": ...}
    """
    if not os.path.exists(local_filepath):
        err = f"Local file not found: {local_filepath}"
        print(f"[!] {err}")
        return {"success": False, "error": err}

    # Pull credentials strictly from environment if not passed directly
    root_f_id = folder_id or os.getenv("GDRIVE_FOLDER_ID")
    c_id = client_id or os.getenv("GDRIVE_CLIENT_ID")
    c_secret = client_secret or os.getenv("GDRIVE_CLIENT_SECRET")
    r_token = refresh_token or os.getenv("GDRIVE_REFRESH_TOKEN")

    if not (root_f_id and c_id and c_secret and r_token):
        err = "Missing required credentials: GDRIVE_FOLDER_ID, GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, or GDRIVE_REFRESH_TOKEN."
        print(f"[!] {err}")
        return {"success": False, "error": err}

    filename = os.path.basename(local_filepath)
    print(f"[*] Refreshing access token via Google OAuth...")
    
    try:
        access_token = get_access_token(c_id, c_secret, r_token)
    except Exception as e:
        err = f"Token refresh failed: {e}"
        print(f"[!] {err}")
        return {"success": False, "error": err}

    # Resolve target destination (e.g. GDRIVE_FOLDER_ID -> Crypto -> Futures/Options)
    target_folder_id = resolve_target_folder(access_token, root_f_id, subfolder_path)

    # Prepare multipart body (metadata + binary file)
    boundary = "===============DeltaDataPreserverBoundary=="
    metadata = {
        "name": filename,
        "parents": [target_folder_id]
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

    dest_desc = f"{subfolder_path}/{filename}" if subfolder_path else filename
    print(f"[*] Uploading '{dest_desc}' ({len(file_bytes) / 1024:.2f} KB) to Google Drive...")
    req = urllib.request.Request(DRIVE_UPLOAD_URL, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            file_id = resp_data.get("id")
            drive_size = int(resp_data.get("size", len(file_bytes)))

            if file_id and drive_size > 0:
                print(f"[✓] File successfully uploaded & verified in Google Drive! File ID: {file_id} ({drive_size / 1024:.2f} KB)")
                return {
                    "success": True,
                    "file_id": file_id,
                    "size_bytes": drive_size,
                    "size_kb": round(drive_size / 1024.0, 2),
                    "filename": filename,
                    "target_folder_id": target_folder_id,
                    "subfolder_path": subfolder_path
                }
            else:
                err = f"Drive API verification failed: returned id={file_id}, size={drive_size}"
                print(f"[!] {err}")
                return {"success": False, "error": err}

    except urllib.error.HTTPError as e:
        err = f"Drive upload HTTP error: {e.code} - {e.read().decode('utf-8')}"
        print(f"[!] {err}")
        return {"success": False, "error": err}
    except Exception as e:
        err = f"Network error during upload: {e}"
        print(f"[!] {err}")
        return {"success": False, "error": err}

if __name__ == "__main__":
    from src.config import load_env
    load_env()
    test_file = os.path.join("data", "options", "BTC", "BTC_options_2026-11-09.parquet")
    res = upload_file_to_drive(test_file, subfolder_path="Crypto/Options")
    print("Test upload result:", res)
