from __future__ import annotations

"""
gup (Google Drive Upload & Convert)

A utility to upload local .docx and .pptx files to a specific Google Drive folder
and automatically convert them to Google Docs and Google Slides.

The script ensures:
1. No name collisions by appending suffixes.
2. Mandatory folder identification via CLI for security.
3. Smart ID extraction from full Drive URLs.
"""

import argparse
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

import yaml
import re
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
    """Configuration for GUp authentication and scopes."""
    credentials_json_path: str = "credentials.json"
    token_json_path: str = "token.json"
    scopes: Optional[List[str]] = None

    def __post_init__(self):
        # Default to least-privilege 'drive.file' scope
        if self.scopes is None:
            self.scopes = ["https://www.googleapis.com/auth/drive.file"]


def load_config(path: str = "config.yaml") -> AppConfig:
    """Loads GUp configuration from a YAML file."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    auth = raw.get("auth", {}) or {}
    scopes = raw.get("scopes", None)

    return AppConfig(
        credentials_json_path=auth.get("credentials_json_path", "credentials.json"),
        token_json_path=auth.get("token_json_path", "token.json"),
        scopes=scopes,
    )


def resolve_unique_name(
    service, name: str, folder_id: str, supports_all_drives: bool = False
) -> str:
    """
    Checks for name collisions in the target Google Drive folder.
    Returns a unique name by appending '-1', '-2', etc. if needed.
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


def get_drive_service(cfg: Optional[AppConfig] = None):
    """
    Returns an authenticated Google Drive API v3 service instance.
    Handles OAuth client secrets and token caching automatically.
    """
    if cfg is None:
        cfg = AppConfig()

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
    Uploads a local Office file to Drive and triggers server-side conversion.
    Returns a tuple of (file_id, web_view_link).
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


def extract_folder_id(input_str: str) -> str:
    """
    Extract the folder ID from a Drive URL or return the input if it's already an ID.
    Supports: https://drive.google.com/drive/folders/<ID>
    """
    input_str = input_str.strip()
    # Simple regex for Drive folder URL
    match = re.search(r"/folders/([a-zA-Z0-9_-]{25,})", input_str)
    if match:
        return match.group(1)
    
    # Also handle URLs that might end with ?usp=sharing etc.
    if "drive.google.com" in input_str and "/folders/" in input_str:
        # Fallback split
        parts = input_str.split("/folders/")
        if len(parts) > 1:
            return parts[1].split("?")[0].split("/")[0]

    return input_str


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
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--folder-id", required=True, help="Google Drive folder ID (from https://drive.google.com/drive/folders/<FOLDER_ID>)")
    args = parser.parse_args()

    folder_id = extract_folder_id(args.folder_id)

    # Try to find config.yaml if not specified
    if not args.config:
        if os.path.exists("config.yaml"):
             args.config = "config.yaml"
        elif os.path.exists("gup/config.yaml"):
             args.config = "gup/config.yaml"

    cfg = None
    if args.config:
        cfg = load_config(args.config)

    service = get_drive_service(cfg) if cfg else get_drive_service(None)

    file_id, link = upload_file_to_drive(
        service,
        local_path=args.file,
        drive_folder_id=folder_id,
        target_name=args.name,
        supports_all_drives=args.supports_all_drives,
    )

    print(f"Created file fileId: {file_id}")
    if link:
        print(f"Open: {link}")


if __name__ == "__main__":
    main()
