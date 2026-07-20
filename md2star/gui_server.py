"""md2star local GUI server — Overleaf-style Markdown editor with live PDF preview.

Launches a localhost-only HTTP server that fronts the existing
``md2star`` CLI: the browser sends Markdown + a small JSON options blob;
the server invokes ``_convert(fmt, ...)`` from :mod:`md2star.cli` against
a temp file and streams the resulting bytes back. The frontend renders
the PDF result inline via PDF.js (no DOCX/PPTX rendering in the browser
— those formats are simply offered as a download).

Endpoints
---------

* ``GET  /``                 → ``index.html`` (shipped under ``md2star/data/gui/``).
* ``GET  /app.js``           → the frontend ES module.
* ``GET  /favicon.svg``      → tiny inline SVG, no network calls.
* ``POST /render``           → run the converter, stream back the bytes.
* ``POST /shutdown``         → clean process exit (used by the in-page
                                "Quit server" button so users do not have
                                to find the terminal).

The server binds to ``127.0.0.1`` only (no LAN exposure) and uses
``ThreadingHTTPServer`` so a slow ``/render`` does not block fast
``/preview`` reads. There is no auth and no sandbox — it is intended
to run on the same machine as the user invoking it, just like Jupyter
or Vite's dev server.

Security note
-------------
The only untrusted input is the ``/fs/*`` path a browser sends. Every such
path is funnelled through :func:`_safe_within_root`, which rejects ``..``
segments, absolute paths and symlink escapes so a request can never read or
write outside the single folder root the user opened. That confinement is
unit-tested in ``tests/test_gui_security.py``.


Author
------
`Warith Harchaoui <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

import os_helper as osh

from . import __version__

# Per-server-process cache-busting tag. We splice it into every static
# asset URL in the served index.html so a stale browser is forced to
# re-fetch app.js / styles.css / fonts / vendor bundles on the next
# reload after a `md2star gui` restart. Without this, browsers happily
# serve months-old cached ES modules even though we send no-store —
# their in-memory module map is the culprit, and a query-string is the
# only reliable way to bust it short of versioned filenames.
_SESSION_CACHE_BUST = uuid.uuid4().hex[:8]


# Per-server-process directory where an in-session uploaded custom
# template lives. Lazy-created on first /template POST; wiped on
# /shutdown and (best-effort) at process exit.
_SESSION_DIR: Path | None = None
_SESSION_TEMPLATE_LOCK = threading.Lock()


def _session_dir() -> Path:
    """Return the per-process session tempdir, creating it on demand."""
    global _SESSION_DIR
    with _SESSION_TEMPLATE_LOCK:
        if _SESSION_DIR is None:
            _SESSION_DIR = Path(tempfile.mkdtemp(prefix="md2star-gui-session-"))
    return _SESSION_DIR


def _session_template(fmt: str) -> Path | None:
    """Return the uploaded template path for *fmt* if one exists."""
    if _SESSION_DIR is None or fmt not in ("docx", "pptx"):
        return None
    cand = _SESSION_DIR / f"template.{fmt}"
    return cand if cand.exists() else None


def _session_template_status() -> dict[str, bool]:
    """Snapshot of which session templates are currently uploaded."""
    return {
        "docx": _session_template("docx") is not None,
        "pptx": _session_template("pptx") is not None,
    }


# ── Server-side draft auto-save ─────────────────────────────────────
# The editor POSTs to /draft every few seconds (after typing pauses).
# We persist to $XDG_CACHE_HOME/md2star/drafts/last.md so the user can
# come back after a browser crash, a `md2star gui` restart, or even a
# machine reboot and get their content back. This is the "safest"
# tier — localStorage is the in-browser fallback for offline; XDG is
# the durable copy.
from .cache import cache_dir as _cache_dir  # noqa: E402  (avoid top-level cycle)


def _draft_path() -> Path:
    return _cache_dir("drafts") / "last.md"


# ── Folder-browser session state ─────────────────────────────────────
# The user opens one folder per process; every subsequent /fs/* call is
# confined to its subtree. Set by POST /fs/open, cleared by POST
# /fs/close. The state is process-local — closing the browser tab does
# not auto-close the folder (the user might just be refreshing).
_FOLDER_ROOT: Path | None = None
_FOLDER_LOCK = threading.Lock()


def _set_folder_root(p: Path | None) -> None:
    global _FOLDER_ROOT
    with _FOLDER_LOCK:
        _FOLDER_ROOT = p


def _folder_root() -> Path | None:
    return _FOLDER_ROOT


def _safe_within_root(rel: str) -> Path | None:
    """Resolve *rel* against the open folder root, refusing escapes.

    Returns the absolute Path on success, ``None`` if no folder is
    open or if the resolution leaves the root (``..`` traversal, an
    absolute path argument, symlink chicanery).
    """
    root = _folder_root()
    if root is None:
        return None
    # Reject absolute paths up front — the contract is "relative to
    # the open folder". We check several shapes:
    #
    # * POSIX-absolute: ``/etc/passwd``
    # * UNC / forward-slash root: ``\\server\share`` / ``\\?\C:\``
    # * Windows drive-letter: ``C:\\Windows\\...`` (which os.path.isabs
    #   on POSIX returns False for — explicit check needed for
    #   defense-in-depth when the server is reached from a Windows
    #   client even though it's running on a POSIX host).
    if rel.startswith("/") or rel.startswith("\\") or os.path.isabs(rel):
        return None
    if len(rel) >= 2 and rel[1] == ":" and rel[0].isalpha():
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _native_folder_picker(prompt: str) -> Path | None:
    """Pop a native folder-chooser dialog. Returns None when unsupported / cancelled.

    macOS uses ``osascript`` (built in). Linux tries ``zenity`` then
    ``kdialog``. Windows uses PowerShell's ``FolderBrowserDialog``.
    When no backend is available we return None and the caller falls
    back to the in-page text input.
    """
    try:
        if osh.macos():
            script = (
                f'POSIX path of (choose folder with prompt "{prompt}")'
            )
            out = subprocess.check_output(
                ["osascript", "-e", script],
                stderr=subprocess.DEVNULL,
                timeout=300,
            ).decode("utf-8", errors="replace").strip()
            return Path(out) if out else None
        if osh.linux():
            if shutil.which("zenity"):
                out = subprocess.check_output(
                    ["zenity", "--file-selection", "--directory",
                     "--title", prompt],
                    stderr=subprocess.DEVNULL, timeout=300,
                ).decode("utf-8", errors="replace").strip()
                return Path(out) if out else None
            if shutil.which("kdialog"):
                out = subprocess.check_output(
                    ["kdialog", "--getexistingdirectory", str(Path.home()),
                     "--title", prompt],
                    stderr=subprocess.DEVNULL, timeout=300,
                ).decode("utf-8", errors="replace").strip()
                return Path(out) if out else None
        if osh.windows():
            # PowerShell one-liner so we don't need a separate .ps1 asset.
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
                f"$d.Description = '{prompt}';"
                "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }",
            ]
            out = subprocess.check_output(
                cmd, stderr=subprocess.DEVNULL, timeout=300,
            ).decode("utf-8", errors="replace").strip()
            return Path(out) if out else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return None


# MIME map for outgoing converted files. The browser uses this to decide
# how to handle the response. HTML is the live-preview path; the others
# are the user-triggered downloads.
_OUTPUT_MIME: dict[str, str] = {
    "html": "text/html; charset=utf-8",
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


# Tiny inline favicon so the page does not 404 in the network panel.
# Drawn as a dark-blue document with a small "★" — readable at 16×16.
_FAVICON_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect x="5" y="3" width="22" height="26" rx="3" fill="#007AFF"/>
<path fill="#FFCC00" d="M16 10l1.8 4.4 4.7.3-3.6 3 1.2 4.5L16 19.8l-4.1 2.4 1.2-4.5-3.6-3 4.7-.3z"/>
</svg>"""


def _read_data(name: str) -> bytes:
    """Return the bytes of a file shipped under ``md2star/data/gui/<name>``."""
    return resources.files("md2star.data.gui").joinpath(name).read_bytes()


def _content_type_for_static(path: str) -> str:
    """Map a URL path to an HTTP ``Content-Type`` for the static GUI files."""
    if path.endswith(".html"):
        return "text/html; charset=utf-8"
    if path.endswith((".js", ".mjs")):
        return "application/javascript; charset=utf-8"
    if path.endswith(".css"):
        return "text/css; charset=utf-8"
    if path.endswith(".svg"):
        return "image/svg+xml"
    if path.endswith(".woff2"):
        return "font/woff2"
    if path.endswith(".woff"):
        return "font/woff"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".txt"):
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def _sniff_ooxml_format(data: bytes) -> str | None:
    """Peek inside an OOXML zip and return "docx", "pptx", or None.

    Both formats use the same zip envelope; the discriminator is
    whether ``word/`` or ``ppt/`` entries are present in the central
    directory. We scan only the first ~64 kB so a malformed body cannot
    pin the server.
    """
    import io
    import zipfile
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return None
    if any(n.startswith("word/") for n in names):
        return "docx"
    if any(n.startswith("ppt/") for n in names):
        return "pptx"
    return None


def _read_vendor(rel_path: str) -> bytes | None:
    """Read a file under ``md2star/data/gui/vendor/<rel_path>``.

    Returns ``None`` for path-traversal attempts (``..`` segments) or for
    files that do not exist. The vendored assets (PDF.js, Tailwind,
    CodeMirror bundle, fonts) live there and the GUI references them via
    ``/vendor/...`` URLs so the editor works fully offline.
    """
    if not rel_path or ".." in rel_path.split("/") or rel_path.startswith("/"):
        return None
    try:
        root = resources.files("md2star.data.gui").joinpath("vendor")
        target = root.joinpath(*rel_path.split("/"))
        return target.read_bytes()
    except (FileNotFoundError, IsADirectoryError, OSError):
        return None


class _Handler(BaseHTTPRequestHandler):
    """One request → one response. Threading is handled by the parent server."""

    # Silence the default access log to keep the terminal readable when
    # the user uses ``md2star gui`` interactively. Errors still print.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def log_error(self, format: str, *args: Any) -> None:  # noqa: A002
        sys.stderr.write("md2star gui: " + (format % args) + "\n")

    # ─────────────────────────────────────────────────────────────────
    # GET — static assets only
    # ─────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:  # noqa: N802
        # Strip the query string before path matching — every static
        # asset has a `?v={{CACHE_BUST}}` appended for browser cache
        # busting and `self.path` keeps the raw query string verbatim.
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            # Splice the per-server cache-bust tag into the served HTML
            # so a stale browser is forced to re-fetch app.js / styles
            # / fonts / vendor bundles on the next reload.
            html = _read_data("index.html").replace(
                b"{{CACHE_BUST}}", _SESSION_CACHE_BUST.encode("ascii")
            )
            return self._send_bytes(html, "text/html; charset=utf-8")
        if path == "/app.js":
            return self._send_bytes(_read_data("app.js"), "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self._send_bytes(_read_data("styles.css"), "text/css; charset=utf-8")
        if path == "/favicon.svg":
            return self._send_bytes(_FAVICON_SVG, "image/svg+xml")
        if path == "/version":
            return self._send_bytes(
                json.dumps({"version": __version__}).encode("utf-8"),
                "application/json",
            )
        if path == "/draft":
            # Return the most recent on-disk draft so a returning user
            # picks up where they left off. 204 when nothing is cached
            # (first visit / cleared draft).
            target = _draft_path()
            if not target.exists():
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            return self._send_bytes(target.read_bytes(),
                                    "text/markdown; charset=utf-8")
        if path == "/template/status":
            return self._send_bytes(
                json.dumps({"session_status": _session_template_status()}).encode("utf-8"),
                "application/json",
            )
        if path == "/example":
            # Serve the bundled `assets/example.md` (mirrored into
            # `md2star/data/example.md` so it ships inside the wheel —
            # one level UP from `data/gui/` which is what _read_data
            # resolves against). Default editor content when no
            # localStorage / server draft is present.
            try:
                example = resources.files("md2star.data").joinpath(
                    "example.md"
                ).read_bytes()
                return self._send_bytes(example, "text/markdown; charset=utf-8")
            except (FileNotFoundError, ModuleNotFoundError, OSError):
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        if path == "/fs/status":
            return self._handle_fs_status()
        if path == "/fs/list":
            return self._handle_fs_list()
        if path == "/fs/read":
            return self._handle_fs_read()
        if path.startswith("/vendor/"):
            rel = path[len("/vendor/"):]
            data = _read_vendor(rel)
            if data is None:
                return self.send_error(404, f"unknown vendor asset {rel!r}")
            return self._send_bytes(data, _content_type_for_static(rel))
        self.send_error(404, f"unknown path {self.path!r}")

    # ─────────────────────────────────────────────────────────────────
    # POST — actions
    # ─────────────────────────────────────────────────────────────────

    def do_POST(self) -> None:  # noqa: N802
        # Every mutating action is a distinct POST path; dispatch on the path
        # (query string stripped) to the matching handler. Unknown paths 404
        # rather than silently succeeding.
        path = self.path.split("?", 1)[0]
        if path == "/render":
            return self._handle_render()
        if path == "/template":
            return self._handle_template_upload()
        if path == "/template/clear":
            return self._handle_template_clear()
        if path == "/draft":
            return self._handle_draft_save()
        # ``/fs/*`` is the folder-browser API; each verb is path-confined by
        # _safe_within_root inside its handler (see the module security note).
        if path == "/fs/open":
            return self._handle_fs_open()
        if path == "/fs/close":
            return self._handle_fs_close()
        if path == "/fs/save":
            return self._handle_fs_save()
        if path == "/fs/create":
            return self._handle_fs_create()
        if path == "/fs/delete":
            return self._handle_fs_delete()
        if path == "/shutdown":
            return self._handle_shutdown()
        self.send_error(404, f"unknown path {self.path!r}")

    def _read_json(self) -> dict[str, Any]:
        # Read exactly Content-Length bytes (0 → empty body → empty dict). A
        # malformed body is a client error (400), not a server crash.
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            self.send_error(400, f"invalid JSON: {exc}")
            return {}

    def _handle_render(self) -> None:
        # The browser posts the editor buffer + a format + an options blob;
        # default to PDF (the live-preview format) when unspecified.
        payload = self._read_json()
        markdown: str = payload.get("markdown") or ""
        fmt: str = (payload.get("format") or "pdf").lower()
        opts: dict[str, Any] = payload.get("options") or {}

        if fmt not in _OUTPUT_MIME:
            return self.send_error(400, f"unknown format {fmt!r}")

        # The CLI is imported lazily so a thread that never converts does
        # not pay the import cost of pandoc / lua-filter resolution.
        from .cli import _convert

        # Each render runs in a throwaway folder (auto-removed on exit) so the
        # user's disk stays clean and concurrent renders can't collide.
        with osh.temporary_folder(prefix="md2star-gui-") as workdir:
            md_path = Path(workdir) / "input.md"
            out_path = Path(workdir) / f"output.{fmt}"
            md_path.write_text(markdown, encoding="utf-8")

            # Translate the JSON options blob into the same argv the CLI takes,
            # appending each flag only when the option was actually supplied.
            argv: list[str] = [str(md_path), "-o", str(out_path)]
            if opts.get("author"):
                argv.extend(["--author", str(opts["author"])])
            if opts.get("lang"):
                argv.extend(["--lang", str(opts["lang"])])
            if opts.get("date"):
                argv.extend(["--date", str(opts["date"])])
            if opts.get("bibliography_name"):
                argv.extend(["--bibliography-name", str(opts["bibliography_name"])])
            if opts.get("lint"):
                argv.append("--lint")
            # Per-phase skips let the UI turn off e.g. mermaid or image embedding.
            for phase in opts.get("skip_phases") or []:
                argv.extend(["--skip-phase", str(phase)])

            # Honor an in-session uploaded reference template
            # (POST /template). PDF rendering shares the DOCX template
            # because the PDF goes through DOCX → soffice. If absent,
            # the CLI's own resolver kicks in (source dir → XDG cache
            # → deraison.ai → bundled). --bib still not exposed in
            # the GUI; users who need bibliographies can run
            # md2docx --bib from the CLI instead.
            template_fmt = "docx" if fmt in ("docx", "pdf") else "pptx"
            uploaded = _session_template(template_fmt)
            if uploaded is not None:
                argv.extend(["--reference-doc", str(uploaded)])

            # Capture the CLI's stdout/stderr so we can surface failures
            # back to the browser instead of silently letting them drop
            # into the server terminal.
            stderr_buf = _StdRedirect(sys.stderr)
            rc: int
            try:
                with stderr_buf:
                    rc = _convert(fmt, argv)
            except SystemExit as exc:  # argparse exits on bad flags
                rc = int(exc.code or 1)
            except Exception as exc:  # noqa: BLE001
                rc = 1
                stderr_buf.captured += f"\nmd2star gui: unexpected error: {exc}\n"

            # Failure (non-zero exit or no output file) → a JSON 500 carrying the
            # captured stderr so the editor can show *why* the render failed.
            if rc != 0 or not out_path.exists():
                err_body = json.dumps({
                    "ok": False,
                    "exit_code": rc,
                    "stderr": stderr_buf.captured,
                }).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_body)))
                self.end_headers()
                self.wfile.write(err_body)
                return

            # Success → stream the rendered bytes inline with the right MIME so
            # PDF.js can preview a PDF and DOCX/PPTX download cleanly.
            data = out_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", _OUTPUT_MIME[fmt])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Disposition",
                f'inline; filename="md2star-output.{fmt}"',
            )
            # Forward any stderr from the CLI so the GUI can show "rendered
            # OK, with warnings" — pulling the bytes through a header keeps
            # the body a clean PDF/DOCX/PPTX stream.
            if stderr_buf.captured.strip():
                self.send_header(
                    "X-Md2star-Stderr",
                    stderr_buf.captured.strip().encode("ascii", "replace").decode("ascii")[:4000],
                )
            self.end_headers()
            self.wfile.write(data)

    # ─────────────────────────────────────────────────────────────────
    # POST /template — upload an in-session reference docx
    # ─────────────────────────────────────────────────────────────────

    def _handle_template_upload(self) -> None:
        """Receive a raw ``.docx`` / ``.pptx`` body and save it as the session template.

        The format is taken from the ``X-Md2star-Format`` header (which the
        frontend infers from the file extension); we fall back to peeking
        inside the OOXML zip if the header is missing or invalid.
        """
        # Reject an empty body up front (nothing to save).
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return self.send_error(400, "empty upload")
        # Cap at 50 MB — bigger than any reasonable Office template and
        # protects the server from accidental upload floods.
        if length > 50 * 1024 * 1024:
            return self.send_error(413, "upload exceeds 50 MB cap")

        # Every OOXML file is a zip, so a missing ``PK\x03\x04`` magic means the
        # body is not a .docx/.pptx — reject before writing anything to disk.
        data = self.rfile.read(length)
        if not data.startswith(b"PK\x03\x04"):
            return self.send_error(
                415, "body does not look like a .docx/.pptx (no OOXML zip header)"
            )

        # Trust the frontend's format header, but verify by peeking inside the
        # zip if it is missing or bogus (docx vs pptx changes where it is used).
        fmt = (self.headers.get("X-Md2star-Format") or "").strip().lower()
        if fmt not in ("docx", "pptx"):
            fmt = _sniff_ooxml_format(data) or ""
        if fmt not in ("docx", "pptx"):
            return self.send_error(
                415, "could not determine format (expected .docx or .pptx)"
            )

        # Persist under the per-process session dir; the next /render for this
        # format picks it up via _session_template.
        target = _session_dir() / f"template.{fmt}"
        target.write_bytes(data)
        body = json.dumps({
            "ok": True, "format": fmt, "bytes": len(data),
            "session_status": _session_template_status(),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_template_clear(self) -> None:
        """Delete every in-session uploaded template."""
        fmt = ""
        try:
            payload = self._read_json() if int(
                self.headers.get("Content-Length", "0") or "0"
            ) > 0 else {}
            fmt = (payload.get("format") or "").lower()
        except Exception:
            fmt = ""

        # Clear just the named format, or both when none was specified.
        cleared: list[str] = []
        candidates = (fmt,) if fmt in ("docx", "pptx") else ("docx", "pptx")
        for f in candidates:
            p = _session_template(f)
            if p is not None:
                p.unlink(missing_ok=True)
                cleared.append(f)

        body = json.dumps({
            "ok": True, "cleared": cleared,
            "session_status": _session_template_status(),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ─────────────────────────────────────────────────────────────────
    # POST /draft  +  GET /draft  — server-side editor auto-save
    # ─────────────────────────────────────────────────────────────────

    def _handle_draft_save(self) -> None:
        """Persist editor markdown to $XDG_CACHE_HOME/md2star/drafts/last.md."""
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > 5 * 1024 * 1024:
            return self.send_error(413, "draft body too large (5 MB cap)")
        data = self.rfile.read(length) if length else b""
        # Atomic write so a crash mid-save can't leave a half-written
        # file: write to a sibling tempfile, then rename.
        target = _draft_path()
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        body = json.dumps({
            "ok": True, "bytes": len(data),
            "path": str(target),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ─────────────────────────────────────────────────────────────────
    # /fs/*  — folder browser (open / list / read / save / create /
    # delete). Every path is confined to the user-chosen root.
    # ─────────────────────────────────────────────────────────────────

    def _query(self) -> dict[str, str]:
        """Parse the URL query string into a flat dict."""
        q = self.path.split("?", 1)
        if len(q) < 2:
            return {}
        return {
            k: (v[0] if v else "")
            for k, v in urllib.parse.parse_qs(q[1], keep_blank_values=True).items()
        }

    def _json_ok(self, payload: dict[str, Any]) -> None:
        # Shared 200-JSON responder for the /fs/* verbs; no-store so the browser
        # never caches a stale directory listing.
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _handle_fs_status(self) -> None:
        # Report whether a folder is open (and which) so the UI can show the
        # browser pane or the "open a folder" prompt.
        root = _folder_root()
        self._json_ok({
            "open": root is not None,
            "root": str(root) if root else None,
        })

    def _handle_fs_open(self) -> None:
        """Pick a folder (native dialog) or use a caller-supplied path."""
        # A caller-supplied path wins (headless / scripted use); otherwise pop a
        # native OS folder chooser.
        payload = self._read_json()
        supplied = (payload.get("path") or "").strip()
        if supplied:
            target = Path(supplied).expanduser()
            if not target.exists() or not target.is_dir():
                return self.send_error(404, f"not a directory: {target}")
        else:
            picked = _native_folder_picker("Pick a folder for md2star")
            if picked is None:
                return self.send_error(
                    501,
                    "no native folder picker available; supply { \"path\": \"…\" }"
                )
            target = picked
        _set_folder_root(target.resolve())
        return self._json_ok({"ok": True, "root": str(_folder_root())})

    def _handle_fs_close(self) -> None:
        _set_folder_root(None)
        return self._json_ok({"ok": True})

    def _handle_fs_list(self) -> None:
        """List one directory level inside the open root."""
        root = _folder_root()
        if root is None:
            return self.send_error(409, "no folder open")
        q = self._query()
        rel = q.get("path", "")
        target = root if rel in ("", ".") else _safe_within_root(rel)
        if target is None or not target.exists() or not target.is_dir():
            return self.send_error(404, f"not a directory: {rel!r}")
        # Sort directories first, then files, each alphabetically — the ordering
        # the file-tree UI expects. Paths are returned relative to the root so
        # the client never learns the absolute filesystem layout.
        dirs, files = [], []
        try:
            for entry in sorted(
                target.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            ):
                if entry.name.startswith("."):
                    continue   # skip dot-files; cuts noise
                rel_p = entry.relative_to(root).as_posix()
                if entry.is_dir():
                    dirs.append({"name": entry.name, "path": rel_p})
                elif entry.is_file():
                    files.append({
                        "name": entry.name,
                        "path": rel_p,
                        "size": entry.stat().st_size,
                        "is_md": entry.suffix.lower() in (".md", ".markdown"),
                    })
        except PermissionError as exc:
            return self.send_error(403, f"permission denied: {exc}")
        return self._json_ok({"path": rel, "dirs": dirs, "files": files})

    def _handle_fs_read(self) -> None:
        # Confine the path, then only ever hand back Markdown — the editor has no
        # business reading arbitrary binaries out of the opened folder.
        q = self._query()
        rel = q.get("path", "")
        target = _safe_within_root(rel)
        if target is None or not target.exists() or not target.is_file():
            return self.send_error(404, f"not a file: {rel!r}")
        if target.suffix.lower() not in (".md", ".markdown"):
            return self.send_error(415, "only .md/.markdown files are readable")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _handle_fs_save(self) -> None:
        """Write the request body to the file at ``path`` inside the open root."""
        payload = self._read_json()
        rel = (payload.get("path") or "").strip()
        content = payload.get("content", "")
        if not isinstance(content, str):
            return self.send_error(400, "content must be a string")
        target = _safe_within_root(rel)
        if target is None:
            return self.send_error(404, f"path is outside the open folder: {rel!r}")
        if target.suffix.lower() not in (".md", ".markdown"):
            return self.send_error(415, "only .md/.markdown files can be saved")
        # Atomic write: stage to a sibling ``.tmp`` then rename, so a crash
        # mid-write never truncates the user's real file.
        osh.make_directory(str(target.parent))
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(target)
        return self._json_ok({"ok": True, "path": rel, "bytes": len(content)})

    def _handle_fs_create(self) -> None:
        """Create a new empty (or seeded) .md file at ``path``."""
        payload = self._read_json()
        rel = (payload.get("path") or "").strip()
        seed = payload.get("seed", "")
        target = _safe_within_root(rel)
        if target is None:
            return self.send_error(404, f"path is outside the open folder: {rel!r}")
        if target.suffix.lower() not in (".md", ".markdown"):
            return self.send_error(415, "filename must end in .md or .markdown")
        if target.exists():
            return self.send_error(409, f"file already exists: {rel!r}")
        osh.make_directory(str(target.parent))
        target.write_text(seed if isinstance(seed, str) else "", encoding="utf-8")
        return self._json_ok({"ok": True, "path": rel})

    def _handle_fs_delete(self) -> None:
        """Delete one or several .md files. Non-md paths are silently skipped."""
        payload = self._read_json()
        paths = payload.get("paths") or []
        if not isinstance(paths, list):
            return self.send_error(400, "paths must be a list")
        # Delete is best-effort per path: anything that fails the confinement,
        # existence, or .md-only checks is reported under ``skipped`` rather than
        # aborting the whole batch — so one bad entry can't block the rest.
        deleted, skipped = [], []
        for raw in paths:
            if not isinstance(raw, str):
                skipped.append(raw)
                continue
            target = _safe_within_root(raw)
            if target is None or not target.exists() or not target.is_file():
                skipped.append(raw)
                continue
            if target.suffix.lower() not in (".md", ".markdown"):
                skipped.append(raw)   # safety: never delete non-md from here
                continue
            try:
                target.unlink()
                deleted.append(raw)
            except OSError:
                skipped.append(raw)
        return self._json_ok({
            "ok": True, "deleted": deleted, "skipped": skipped,
        })

    def _handle_shutdown(self) -> None:
        # We schedule the actual shutdown on a side thread so the response
        # can finish first — calling ``server.shutdown()`` from the same
        # thread that's handling the request deadlocks ``ThreadingHTTPServer``.
        body = b'{"ok":true}\n'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        threading.Thread(
            target=lambda: self.server.shutdown(),  # type: ignore[union-attr]
            daemon=True,
        ).start()

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


class _StdRedirect:
    """Tiny context manager that captures ``sys.stderr`` writes into a string.

    Used to wrap the synchronous ``_convert`` call so any warnings the CLI
    emits (failed mermaid render, deraison.ai download fallback, …) can be
    surfaced to the GUI instead of vanishing into the server terminal.
    """

    def __init__(self, original: Any) -> None:
        self.original = original
        self.captured = ""

    def __enter__(self) -> _StdRedirect:
        sys.stderr = self  # type: ignore[assignment]
        return self

    def __exit__(self, *_: Any) -> None:
        sys.stderr = self.original

    def write(self, chunk: str) -> int:
        # Pass through to the real stderr so the developer launching the
        # server still sees the messages live.
        try:
            self.original.write(chunk)
        except Exception:
            pass
        self.captured += chunk
        return len(chunk)

    def flush(self) -> None:
        try:
            self.original.flush()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────
# Bind / port allocation
# ─────────────────────────────────────────────────────────────────────


def _pick_port(preferred: int) -> int:
    """Return *preferred* if free, otherwise the next free port the OS allocates."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", preferred))
            return preferred
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


# ─────────────────────────────────────────────────────────────────────
# Public entry point — ``md2star gui [--port N] [--no-browser]``
# ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Console entry point invoked via ``md2star gui [...]``."""
    parser = argparse.ArgumentParser(
        prog="md2star gui",
        description="Launch the local Markdown → PDF preview GUI.",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Preferred port (default: %(default)s; auto-falls-back if in use).",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Do not auto-open the browser. The URL is still printed.",
    )
    parser.add_argument(
        "--bind", default="127.0.0.1",
        help=("Bind address (default: %(default)s, localhost only). "
              "Set to 0.0.0.0 to expose to the LAN (security risk; no auth)."),
    )
    args = parser.parse_args(argv)

    port = _pick_port(args.port) if args.bind == "127.0.0.1" else args.port
    server = ThreadingHTTPServer((args.bind, port), _Handler)

    url = f"http://{args.bind}:{port}/"
    print(f"md2star {__version__} — GUI listening on {url}")
    if args.bind != "127.0.0.1":
        # LAN / 0.0.0.0 binding is a footgun. Loud multi-line banner so
        # the operator cannot miss it. No prompt — we don't want to
        # block scripted deployments — but the message names the exact
        # risks so anyone reading their logs sees the issue.
        banner = "═" * 64
        print(
            "\n" + banner +
            "\n  ⚠  md2star GUI is bound to a NON-LOOPBACK address." +
            f"\n     URL: {url}" +
            "\n  ⚠  The server has NO AUTHENTICATION and runs the md2star CLI" +
            "\n     against any markdown a client sends. Anyone who can reach" +
            "\n     this port can write files inside the open folder root and" +
            "\n     upload arbitrary DOCX/PPTX templates." +
            "\n  ⚠  This is appropriate ONLY for trusted local-network use." +
            "\n     For anything else, bind to 127.0.0.1 (the default) and" +
            "\n     use SSH port-forwarding to reach the GUI remotely." +
            "\n" + banner + "\n",
            file=sys.stderr,
        )
    print("Press Ctrl-C to stop (or use the in-page Quit button).")

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nmd2star gui: stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
