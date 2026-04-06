"""
test_gup.py — Unit tests for gup/src/gup.py.

Only pure functions that do **not** require Google API credentials are
tested here: ``extract_folder_id``, ``load_config``, and ``AppConfig``.

The Google API client libraries are mocked if they are not installed,
so these tests run in any Python environment with only ``pytest`` and
``pyyaml``.

Test Coverage:
- Folder ID extraction: raw IDs, full URLs, URLs with query params
- Configuration loading: missing files, valid YAML, partial configs
- AppConfig defaults: scopes, credential paths, token paths
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

# ── Mock heavy Google dependencies if they are not installed ──────
# This allows us to import gup.py (which has top-level google imports)
# without requiring the full google-auth / google-api-python-client stack.
# We use MagicMock so attribute access (e.g. `from X import Y`) succeeds.
_GOOGLE_MODULES = [
    "google",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.credentials",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.http",
]
for _mod_name in _GOOGLE_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = mock.MagicMock()

# ── Make the gup/src/ directory importable ────────────────────────
_GUP_DIR = str(Path(__file__).resolve().parent.parent / "gup" / "src")
if _GUP_DIR not in sys.path:
    sys.path.insert(0, _GUP_DIR)

from gup import AppConfig, extract_folder_id, load_config  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# extract_folder_id
# ──────────────────────────────────────────────────────────────────


class TestExtractFolderId:
    """Tests for extract_folder_id()."""

    def test_raw_id(self) -> None:
        """A plain folder ID should be returned as-is."""
        # User may paste just the ID without the full URL
        raw = "1ABCxyz_abc1234567890123456"
        assert extract_folder_id(raw) == raw

    def test_full_url(self) -> None:
        """Full Drive URL should extract the folder ID correctly."""
        # Common case: user copies URL from browser address bar
        fid = "1ABCxyz_abc1234567890123456"
        url = f"https://drive.google.com/drive/folders/{fid}"
        assert extract_folder_id(url) == fid

    def test_url_with_query_params(self) -> None:
        """URL with query parameters should still extract the ID."""
        # Drive URLs often include ?usp=sharing or other params
        fid = "1ABCxyz_abc1234567890123456"
        url = f"https://drive.google.com/drive/folders/{fid}?usp=sharing"
        assert extract_folder_id(url) == fid

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be removed."""
        # User may accidentally include spaces when pasting
        assert extract_folder_id("  abc123  ") == "abc123"


# ──────────────────────────────────────────────────────────────────
# AppConfig
# ──────────────────────────────────────────────────────────────────


class TestAppConfig:
    """Tests for AppConfig.__post_init__ defaults."""

    def test_default_scopes(self) -> None:
        """Default scope should be least-privilege drive.file."""
        # drive.file only grants access to files created by this app
        cfg = AppConfig()
        assert cfg.scopes == ["https://www.googleapis.com/auth/drive.file"]

    def test_custom_scopes(self) -> None:
        """Custom scopes should override defaults."""
        # Users may need full drive access for Shared Drives
        cfg = AppConfig(scopes=["https://www.googleapis.com/auth/drive"])
        assert cfg.scopes == ["https://www.googleapis.com/auth/drive"]

    def test_default_paths(self) -> None:
        """Default paths should be set to standard filenames."""
        cfg = AppConfig()
        assert cfg.credentials_json_path == "credentials.json"
        assert cfg.token_json_path == "token.json"


# ──────────────────────────────────────────────────────────────────
# load_config
# ──────────────────────────────────────────────────────────────────


class TestLoadConfig:
    """Tests for load_config()."""

    def test_missing_file_returns_defaults(self) -> None:
        """When the config file does not exist, defaults should be used."""
        # Graceful degradation: missing config should not crash the app
        cfg = load_config("/non/existent/config.yaml")
        assert cfg.credentials_json_path == "credentials.json"
        assert cfg.token_json_path == "token.json"
        assert cfg.scopes == ["https://www.googleapis.com/auth/drive.file"]

    def test_valid_yaml(self, tmp_path: Path) -> None:
        """A well-formed YAML file should populate the config correctly."""
        # Complete config with all fields specified
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "auth:\n"
            "  credentials_json_path: my_creds.json\n"
            "  token_json_path: my_token.json\n"
            "scopes:\n"
            "  - https://www.googleapis.com/auth/drive\n"
        )
        cfg = load_config(str(config_file))
        assert cfg.credentials_json_path == "my_creds.json"
        assert cfg.token_json_path == "my_token.json"
        assert cfg.scopes == ["https://www.googleapis.com/auth/drive"]

    def test_partial_yaml(self, tmp_path: Path) -> None:
        """A YAML file with only some fields should use defaults for the rest."""
        # Partial config: only override token path, use defaults for others
        config_file = tmp_path / "config.yaml"
        config_file.write_text("auth:\n  token_json_path: custom.json\n")
        cfg = load_config(str(config_file))
        assert cfg.credentials_json_path == "credentials.json"  # default
        assert cfg.token_json_path == "custom.json"  # overridden

    def test_empty_yaml(self, tmp_path: Path) -> None:
        """An empty YAML file should yield default values."""
        # Edge case: empty file should be treated as missing config
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = load_config(str(config_file))
        assert cfg.credentials_json_path == "credentials.json"
