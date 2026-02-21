from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import yaml
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
GDOC_MIME = "application/vnd.google-apps.document"
GSLIDE_MIME = "application/vnd.google-apps.presentation"


@dataclass
class AppConfig:
    folder_id: str
    credentials_json_path: str
    token_json_path: str
    scopes: List[str]


def load_config(path: str = "config.yaml") -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Create it by copying config.example.yaml -> config.yaml"
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    drive = raw.get("google_drive", {}) or {}
    auth = raw.get("auth", {}) or {}
    scopes = raw.get("scopes", None)

    folder_id = drive.get("folder_id", "")
    if not folder_id or "PASTE_YOUR_FOLDER_ID_HERE" in str(folder_id):
        raise ValueError("Please set google_drive.folder_id in config.yaml")

    credentials_json_path = auth.get("credentials_json_path", "credentials.json")
    token_json_path = auth.get("token_json_path", "token.json")

    if not scopes:
        scopes = ["https://www.googleapis.com/auth/drive.file"]

    return AppConfig(
        folder_id=str(folder_id),
        credentials_json_path=str(credentials_json_path),
        token_json_path=str(token_json_path),
        scopes=[str(s) for s in scopes],
    )


def resolve_unique_name(
    service, name: str, folder_id: str, supports_all_drives: bool = False
) -> str:
    """
    Check if a file with 'name' exists in 'folder_id'.
    If so, append -1, -2, etc. until unique.
    """
    # Escape single quotes for the Drive API query
    safe_name = name.replace("'", "\\'")

    query = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"

    req_kwargs = {}
    if supports_all_drives:
        req_kwargs["supportsAllDrives"] = True
        req_kwargs["includeItemsFromAllDrives"] = True

    results = service.files().list(q=query, fields="files(id)", **req_kwargs).execute()
    files = results.get("files", [])

    if not files:
        return name

    # Name exists, find next suffix
    n = 1
    while True:
        new_name = f"{name}-{n}"
        safe_new_name = new_name.replace("'", "\\'")
        query = (
            f"name = '{safe_new_name}' and '{folder_id}' in parents and trashed = false"
        )
        results = (
            service.files().list(q=query, fields="files(id)", **req_kwargs).execute()
        )
        if not results.get("files", []):
            return new_name
        n += 1


def get_drive_service(cfg: AppConfig):
    """
    Returns an authenticated Drive API v3 service.

    First run opens a local browser window for OAuth consent and writes token_json_path.
    """
    creds: Optional[Credentials] = None

    if os.path.exists(cfg.token_json_path):
        creds = Credentials.from_authorized_user_file(cfg.token_json_path, cfg.scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(cfg.credentials_json_path):
                raise FileNotFoundError(
                    f"Missing OAuth client file: {cfg.credentials_json_path}\n"
                    f"Download it from Google Cloud Console and place it at that path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(cfg.credentials_json_path, cfg.scopes)
            creds = flow.run_local_server(port=0)

        with open(cfg.token_json_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def upload_file_to_drive(
    service,
    local_path: str,
    drive_folder_id: str,
    target_name: Optional[str] = None,
    supports_all_drives: bool = False,
) -> Tuple[str, Optional[str]]:
    """
    Upload a local .docx or .pptx to Google Drive and convert it.
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")

    ext = os.path.splitext(local_path)[1].lower()
    if ext == ".docx":
        local_mime = DOCX_MIME
        target_mime = GDOC_MIME
    elif ext == ".pptx":
        local_mime = PPTX_MIME
        target_mime = GSLIDE_MIME
    else:
        raise ValueError(f"Unsupported file extension: {ext}. Use .docx or .pptx")

    if target_name is None:
        base = os.path.basename(local_path)
        target_name = os.path.splitext(base)[0]

    # Resolve name collision
    target_name = resolve_unique_name(
        service, target_name, drive_folder_id, supports_all_drives
    )

    file_metadata = {
        "name": target_name,
        "parents": [drive_folder_id],
        "mimeType": target_mime,
    }

    media = MediaFileUpload(local_path, mimetype=local_mime, resumable=True)

    req_kwargs = {}
    if supports_all_drives:
        req_kwargs["supportsAllDrives"] = True

    created = (
        service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name, mimeType, parents, webViewLink",
            **req_kwargs,
        )
        .execute()
    )

    return created["id"], created.get("webViewLink")


def main():
    parser = argparse.ArgumentParser(
        description="Upload a .docx or .pptx to Google Drive and convert it to Google Docs/Slides."
    )
    parser.add_argument("file", help="Path to local .docx or .pptx")
    parser.add_argument("--name", default=None, help="Optional name for the created Google Doc/Slide")
    parser.add_argument(
        "--supports-all-drives",
        action="store_true",
        help="Enable if uploading into a Shared Drive folder",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    service = get_drive_service(cfg)

    file_id, link = upload_file_to_drive(
        service,
        local_path=args.file,
        drive_folder_id=cfg.folder_id,
        target_name=args.name,
        supports_all_drives=args.supports_all_drives,
    )

    print(f"Created file fileId: {file_id}")
    if link:
        print(f"Open: {link}")


if __name__ == "__main__":
    main()
