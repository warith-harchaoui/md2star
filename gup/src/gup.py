from __future__ import annotations

"""
gup.py — Google Drive Upload & Convert.

A CLI utility to upload local ``.docx`` and ``.pptx`` files to a specific
Google Drive folder and automatically convert them to Google Docs and Google
Slides.

The script ensures:

1. **No name collisions** by appending ``-1``, ``-2``, … suffixes.
2. **Mandatory folder identification** via CLI for security (no accidental
   uploads to the Drive root).
3. **Smart ID extraction** from full Drive URLs so users can paste either
   the raw folder ID or the browser URL.

Dependencies
------------
- ``google-api-python-client``
- ``google-auth-oauthlib``
- ``pyyaml``

Examples
--------
Upload a DOCX file to a specific Drive folder::

    $ python gup.py report.docx --folder-id 1ABC-xyz

Upload using the full Drive URL::

    $ python gup.py slides.pptx \\
        --folder-id "https://drive.google.com/drive/folders/1ABC-xyz"

Author
------
Warith Harchaoui
"""

import argparse
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ──────────────────────────────────────────────────────────────────────
# MIME type constants — mapping between local Office formats and their
# Google Workspace equivalents used for server-side conversion.
# ──────────────────────────────────────────────────────────────────────
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
GDOC_MIME = "application/vnd.google-apps.document"
GSLIDE_MIME = "application/vnd.google-apps.presentation"


# ──────────────────────────────────────────────────────────────────────
# Configuration data class
# ──────────────────────────────────────────────────────────────────────


@dataclass
class AppConfig:
    """
    Configuration for GUp authentication and scopes.

    Attributes
    ----------
    credentials_json_path : str
        Path to the OAuth client-secret JSON file downloaded from the
        Google Cloud Console.  Default ``"credentials.json"``.
    token_json_path : str
        Path where the cached OAuth token is stored (auto-created on
        first successful login).  Default ``"token.json"``.
    scopes : list[str] or None
        OAuth2 scopes requested.  Defaults to the least-privilege
        ``drive.file`` scope, which only grants access to files created
        by this application.

    Examples
    --------
    >>> cfg = AppConfig()
    >>> cfg.scopes
    ['https://www.googleapis.com/auth/drive.file']
    """

    credentials_json_path: str = "credentials.json"
    token_json_path: str = "token.json"
    scopes: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Set default scopes to least-privilege ``drive.file`` if none given."""
        if self.scopes is None:
            self.scopes = ["https://www.googleapis.com/auth/drive.file"]


# ──────────────────────────────────────────────────────────────────────
# Configuration loading
# ──────────────────────────────────────────────────────────────────────


def load_config(path: str = "config.yaml") -> AppConfig:
    """
    Load GUp configuration from a YAML file.

    Parameters
    ----------
    path : str, optional
        Path to the YAML configuration file.  If the file does not exist,
        all defaults from :class:`AppConfig` are used.

    Returns
    -------
    AppConfig
        Populated configuration instance.

    Examples
    --------
    >>> cfg = load_config("gup/config.yaml")
    >>> cfg.credentials_json_path
    'credentials.json'
    """
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    # Extract the nested "auth" section (gracefully handle missing keys)
    auth = raw.get("auth", {}) or {}
    scopes = raw.get("scopes", None)

    return AppConfig(
        credentials_json_path=auth.get("credentials_json_path", "credentials.json"),
        token_json_path=auth.get("token_json_path", "token.json"),
        scopes=scopes,
    )


# ──────────────────────────────────────────────────────────────────────
# Name-collision resolution
# ──────────────────────────────────────────────────────────────────────


def resolve_unique_name(
    service,
    name: str,
    folder_id: str,
    supports_all_drives: bool = False,
) -> str:
    """
    Check for name collisions in the target Google Drive folder.

    If a file with the given *name* already exists in the folder, the
    function appends ``-1``, ``-2``, … until a unique name is found.

    Parameters
    ----------
    service
        Authenticated Google Drive API v3 service resource.
    name : str
        Desired file name (without extension).
    folder_id : str
        ID of the target Drive folder.
    supports_all_drives : bool, optional
        Pass ``True`` when uploading into a Shared Drive folder.

    Returns
    -------
    str
        A unique name that does not collide with existing files.

    Notes
    -----
    Single quotes in *name* are escaped for the Drive API query language.
    """
    # Escape single quotes for the Drive API query syntax
    safe_name = name.replace("'", "\\'")

    query = f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false"

    # Build optional kwargs for Shared Drive support
    req_kwargs: dict = {}
    if supports_all_drives:
        req_kwargs["supportsAllDrives"] = True
        req_kwargs["includeItemsFromAllDrives"] = True

    results = (
        service.files().list(q=query, fields="files(id)", **req_kwargs).execute()
    )
    files = results.get("files", [])

    # No collision — the original name is fine
    if not files:
        return name

    # Name exists — find the next available numeric suffix
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


# ──────────────────────────────────────────────────────────────────────
# OAuth2 authentication
# ──────────────────────────────────────────────────────────────────────


def get_drive_service(cfg: Optional[AppConfig] = None):
    """
    Return an authenticated Google Drive API v3 service instance.

    Handles OAuth client-secrets and token caching automatically:

    1. If a cached token exists, load and reuse it.
    2. If the token has expired but has a refresh token, silently refresh.
    3. Otherwise, open a local browser flow for interactive login.

    Parameters
    ----------
    cfg : AppConfig or None, optional
        Configuration with paths to credential/token files and scopes.
        If ``None``, default :class:`AppConfig` values are used.

    Returns
    -------
    googleapiclient.discovery.Resource
        Authenticated Drive API v3 service.

    Raises
    ------
    FileNotFoundError
        If the OAuth client-secrets file is missing and no cached token
        is available.
    """
    if cfg is None:
        cfg = AppConfig()

    creds: Optional[Credentials] = None

    # ── 1. Try to load a cached token ──
    if os.path.exists(cfg.token_json_path):
        creds = Credentials.from_authorized_user_file(
            cfg.token_json_path, cfg.scopes
        )

    # ── 2. Refresh or re-authenticate ──
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Silent refresh (no browser interaction needed)
            creds.refresh(Request())
        else:
            # Full interactive flow — requires client-secrets file
            if not os.path.exists(cfg.credentials_json_path):
                raise FileNotFoundError(
                    f"Missing OAuth client file: {cfg.credentials_json_path}\n"
                    f"Download it from Google Cloud Console and place it at that path."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                cfg.credentials_json_path, cfg.scopes
            )
            creds = flow.run_local_server(port=0)

        # Persist token for subsequent runs
        with open(cfg.token_json_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ──────────────────────────────────────────────────────────────────────
# File upload (with server-side conversion)
# ──────────────────────────────────────────────────────────────────────


def upload_file_to_drive(
    service,
    local_path: str,
    drive_folder_id: str,
    target_name: Optional[str] = None,
    supports_all_drives: bool = False,
) -> Tuple[str, Optional[str]]:
    """
    Upload a local Office file to Drive and trigger server-side conversion.

    Parameters
    ----------
    service
        Authenticated Google Drive API v3 service resource.
    local_path : str
        Path to the local ``.docx`` or ``.pptx`` file.
    drive_folder_id : str
        ID of the target Drive folder.
    target_name : str or None, optional
        Name for the created Google Doc / Slide.  If ``None``, the stem
        of *local_path* is used (e.g. ``report.docx`` → ``report``).
    supports_all_drives : bool, optional
        Pass ``True`` when uploading into a Shared Drive folder.

    Returns
    -------
    tuple[str, str or None]
        ``(file_id, web_view_link)`` — the web link may be ``None`` if
        the API does not return one.

    Raises
    ------
    FileNotFoundError
        If *local_path* does not exist.
    ValueError
        If the file extension is not ``.docx`` or ``.pptx``.
    """
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"File not found: {local_path}")

    # ── Determine MIME types for local file and target conversion ──
    ext = os.path.splitext(local_path)[1].lower()
    if ext == ".docx":
        local_mime = DOCX_MIME
        target_mime = GDOC_MIME
    elif ext == ".pptx":
        local_mime = PPTX_MIME
        target_mime = GSLIDE_MIME
    else:
        raise ValueError(f"Unsupported file extension: {ext}. Use .docx or .pptx")

    # ── Derive a display name from the filename if not provided ──
    if target_name is None:
        base = os.path.basename(local_path)
        target_name = os.path.splitext(base)[0]

    # ── Resolve potential name collision in the target folder ──
    target_name = resolve_unique_name(
        service, target_name, drive_folder_id, supports_all_drives
    )

    # ── Build the Drive API request ──
    file_metadata = {
        "name": target_name,
        "parents": [drive_folder_id],
        "mimeType": target_mime,  # triggers server-side conversion
    }

    media = MediaFileUpload(local_path, mimetype=local_mime, resumable=True)

    req_kwargs: dict = {}
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


# ──────────────────────────────────────────────────────────────────────
# Folder-ID extraction
# ──────────────────────────────────────────────────────────────────────


def extract_folder_id(input_str: str) -> str:
    """
    Extract the folder ID from a Drive URL or return the input as-is.

    Supports URLs of the form::

        https://drive.google.com/drive/folders/<ID>
        https://drive.google.com/drive/folders/<ID>?usp=sharing

    Parameters
    ----------
    input_str : str
        Either a raw folder ID or a full Google Drive folder URL.

    Returns
    -------
    str
        The extracted folder ID.

    Examples
    --------
    >>> extract_folder_id("1ABCxyz_abc123")
    '1ABCxyz_abc123'

    >>> extract_folder_id("https://drive.google.com/drive/folders/1ABCxyz_abc123?usp=sharing")
    '1ABCxyz_abc123'
    """
    input_str = input_str.strip()

    # Attempt regex extraction from a standard Drive folder URL
    match = re.search(r"/folders/([a-zA-Z0-9_-]{25,})", input_str)
    if match:
        return match.group(1)

    # Fallback: split-based extraction for edge-case URL formats
    if "drive.google.com" in input_str and "/folders/" in input_str:
        parts = input_str.split("/folders/")
        if len(parts) > 1:
            return parts[1].split("?")[0].split("/")[0]

    # Already a raw ID — return unchanged
    return input_str


# ──────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """
    Parse CLI arguments and orchestrate the upload workflow.

    This is the entry-point invoked by the installed ``gup`` wrapper script.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Upload a .docx or .pptx to Google Drive and convert it "
            "to Google Docs/Slides."
        ),
    )
    parser.add_argument("file", help="Path to local .docx or .pptx")
    parser.add_argument(
        "--name",
        default=None,
        help="Optional name for the created Google Doc/Slide",
    )
    parser.add_argument(
        "--supports-all-drives",
        action="store_true",
        help="Enable if uploading into a Shared Drive folder",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--folder-id",
        required=True,
        help=(
            "Google Drive folder ID "
            "(from https://drive.google.com/drive/folders/<FOLDER_ID>)"
        ),
    )
    args = parser.parse_args()

    # Parse folder ID from a raw ID or full URL
    folder_id = extract_folder_id(args.folder_id)

    # ── Auto-discover config.yaml if not explicitly specified ──
    if not args.config:
        if os.path.exists("config.yaml"):
            args.config = "config.yaml"
        elif os.path.exists("gup/config.yaml"):
            args.config = "gup/config.yaml"

    # Load configuration (or use defaults)
    cfg = load_config(args.config) if args.config else None

    # Authenticate and build the Drive API service
    service = get_drive_service(cfg)

    # Perform the upload with server-side conversion
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
