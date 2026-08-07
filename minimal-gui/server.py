#!/usr/bin/env python3
"""
md2star minimal GUI · split-pane preview server
================================================

Tiny stdlib HTTP server that exposes the md2docx → PDF pipeline as
a single endpoint the in-browser editor calls on every keystroke
(debounced).

Architecture
------------

* ``GET  /``         → serves :file:`index.html` (the editor UI).
* ``POST /render``   → body is JSON ``{"markdown": "<source>"}``;
                       response is ``application/pdf`` bytes.
* ``GET  /healthz``  → ``200 OK`` if md2docx + soffice are reachable.

The PDF generation pipeline mirrors what ``md2pdf`` does in
``md2star/cli.py``: write the user's markdown to a temp file, call
``md2docx`` to produce a .docx, then call headless LibreOffice
(``soffice --headless --convert-to pdf``) to render the PDF. We
re-implement the chain here (rather than calling ``md2pdf`` straight
through) only because we need to interleave the conversion with the
HTTP lifecycle — the server stays a single Python process and
talks to soffice via ``subprocess``.

Dependencies
------------

The HTTP layer is pure standard library (:mod:`http.server`,
:mod:`subprocess`, :mod:`tempfile`, :mod:`json`, :mod:`pathlib`). Logging,
warnings and OS detection go through :mod:`os_helper` — md2star's sibling in
the same suite — so this demo stays consistent with the packaged tool. Since
it already shells out to ``md2star`` / ``md2docx``, having the suite installed
(which pulls in ``os_helper``) is a given.

Usage
-----

::

    cd minimal-gui
    python3 server.py                    # default: 127.0.0.1:8765
    python3 server.py --port 9999        # alt port
    python3 server.py --bind 0.0.0.0     # accept LAN connections

Then open ``http://127.0.0.1:8765/`` in any browser.

Honest limits
-------------

* PDF rendering is **slow** the first time: soffice cold-start is
  ~3 s. Subsequent calls reuse the daemon (~600 ms). The UI shows
  a "rendering…" indicator while it waits.
* Concurrent calls are serialised by a process-level lock — soffice
  with the user's profile directory is not concurrency-safe.
* The temp folder under :data:`WORK_DIR` is wiped on shutdown.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import atexit
import http.server
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any

import os_helper as osh

# ── Module-level state ────────────────────────────────────────────────


#: Temp directory the server uses for every render. Created at boot
#: and removed on clean shutdown. Each request lands in a fresh
#: subdirectory so concurrent users (rare in this dev loop) cannot
#: clobber each other.
WORK_DIR: Path = Path(tempfile.mkdtemp(prefix="md2star-minimal-gui-"))


#: Process-level lock — soffice + the LibreOffice user profile do not
#: tolerate concurrent ``--convert-to pdf`` calls. Serialise. The lock
#: is short-lived enough (one render = ~600 ms warm) that the human
#: typing on the front end never notices.
RENDER_LOCK: threading.Lock = threading.Lock()


#: Path to the project static folder (this file's directory).
STATIC_DIR: Path = Path(__file__).resolve().parent


#: Path to the md2star project root — we add it to ``sys.path`` so
#: ``python -m md2star`` resolves without an install. Walks up from
#: this file: ``minimal-gui/server.py`` lives inside the project.
PROJECT_DIR: Path = STATIC_DIR.parent


@atexit.register
def _cleanup_work_dir() -> None:
    """Remove the temp directory on interpreter shutdown."""
    shutil.rmtree(WORK_DIR, ignore_errors=True)


# ── md2docx → PDF pipeline ────────────────────────────────────────────


def _find_soffice() -> str | None:
    """
    Resolve the ``soffice`` (headless LibreOffice) binary.

    Returns
    -------
    str or None
        Absolute path on success; ``None`` when LibreOffice is not
        installed (the server will surface this as an HTTP 503).
    """
    found: str | None = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    # Common macOS install location that is rarely on ``$PATH``.
    mac_path: Path = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return str(mac_path) if mac_path.is_file() else None


def render_markdown_to_pdf(markdown: str, fmt: str = "docx") -> bytes:
    """
    Run ``md2{docx,pptx}`` then ``soffice --convert-to pdf`` on a snippet.

    Parameters
    ----------
    markdown : str
        Raw Markdown source from the editor.
    fmt : str, optional
        ``"docx"`` (default) uses the md2docx pipeline — the Musk
        engineering-algorithm doc is the canonical example.
        ``"pptx"`` uses md2pptx — the Kawasaki 10/20/30 deck is the
        canonical example. Any other value raises.

    Returns
    -------
    bytes
        PDF file contents, ready to stream back to the browser.

    Raises
    ------
    RuntimeError
        Any pipeline step failed. The message names which step.
    """
    if fmt not in ("docx", "pptx"):
        raise RuntimeError(f"unsupported format: {fmt!r} (want docx or pptx)")

    # Each render gets its own subdir so the temp files do not pile up
    # between requests. ``WORK_DIR`` itself is shared.
    job_dir: Path = Path(tempfile.mkdtemp(prefix="job-", dir=WORK_DIR))
    md_path: Path = job_dir / "input.md"
    md_path.write_text(markdown, encoding="utf-8")

    # ── md2{docx,pptx} ─────────────────────────────────────────────
    out_path: Path = job_dir / f"input.{fmt}"
    md_proc = subprocess.run(
        # md2star's real CLI is ``md2star <fmt> <input> -o <output>`` (there is
        # no ``convert --format`` interface); ``-m md2star`` runs it in-tree.
        [sys.executable, "-m", "md2star", fmt, str(md_path), "-o", str(out_path)],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if md_proc.returncode != 0 or not out_path.is_file():
        # Fall back to the user's $PATH ``md2docx`` / ``md2pptx`` if
        # ``-m md2star`` is not reachable (e.g. the project has not
        # been pip-installed). Keeps the editor usable on a fresh
        # clone.
        alt_bin: str | None = shutil.which(f"md2{fmt}")
        if alt_bin is not None:
            md_proc = subprocess.run(
                [alt_bin, str(md_path), "-o", str(out_path)],
                capture_output=True, text=True, timeout=60,
            )
        if md_proc.returncode != 0 or not out_path.is_file():
            raise RuntimeError(
                f"md2{fmt} step failed:\n"
                + (md_proc.stderr or md_proc.stdout or "").strip()
            )

    # ── soffice → PDF ──────────────────────────────────────────────
    soffice: str | None = _find_soffice()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice (soffice) is not installed. "
            "Install with `brew install --cask libreoffice` (macOS) "
            "or your distro's package."
        )

    profile_dir: Path = job_dir / "soffice-profile"
    # Impress (soffice on a .pptx) needs an explicit impress filter to
    # produce a PDF instead of the default Draw output on some
    # LibreOffice builds. Writer (.docx) just needs ``pdf``.
    convert_target: str = "pdf:impress_pdf_Export" if fmt == "pptx" else "pdf"
    soffice_proc = subprocess.run(
        [
            soffice,
            "--headless",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to", convert_target,
            "--outdir", str(job_dir),
            str(out_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    pdf_path: Path = job_dir / "input.pdf"
    if soffice_proc.returncode != 0 or not pdf_path.is_file():
        raise RuntimeError(
            "soffice --convert-to pdf step failed:\n"
            + (soffice_proc.stderr or soffice_proc.stdout or "").strip()
        )
    return pdf_path.read_bytes()


# ── HTTP handler ──────────────────────────────────────────────────────


class OverleafHandler(http.server.BaseHTTPRequestHandler):
    """Three routes — see module docstring."""

    server_version = "md2star-minimal-gui/0.1"

    # Silence default-stdlib access log; we re-emit a slimmer line.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
        osh.info("%s — %s", self.address_string(), fmt % args)

    # ── GET ────────────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802 (HTTP method case)
        # Strip the query string so ``/?theme=dark`` still resolves
        # to the editor page (used both by the theme URL param and by
        # headless-Chrome screenshot passes).
        path: str = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/example":
            self._serve_example()
        elif path == "/healthz":
            soffice: str | None = _find_soffice()
            payload: dict[str, Any] = {
                "ok": soffice is not None,
                "soffice": soffice,
                "work_dir": str(WORK_DIR),
            }
            self._send_json(HTTPStatus.OK if soffice else HTTPStatus.SERVICE_UNAVAILABLE, payload)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    # ── POST ───────────────────────────────────────────────────────
    def do_POST(self) -> None:  # noqa: N802
        # Route on the path minus its query string, same as GET.
        path: str = self.path.split("?", 1)[0]
        if path != "/render":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length: int = int(self.headers.get("Content-Length", "0"))
        raw: bytes = self.rfile.read(length) if length > 0 else b""
        try:
            payload: dict[str, Any] = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"bad JSON: {exc}"})
            return
        markdown: str = (payload.get("markdown") or "").strip()
        if not markdown:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing 'markdown'"})
            return
        fmt: str = (payload.get("format") or "docx").lower()
        if fmt not in ("docx", "pptx"):
            self._send_json(HTTPStatus.BAD_REQUEST,
                            {"error": f"unsupported format: {fmt}"})
            return
        try:
            with RENDER_LOCK:
                pdf: bytes = render_markdown_to_pdf(markdown, fmt=fmt)
        except RuntimeError as exc:
            self._send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf)))
        # CORS for the dev case where the user opens the page from
        # ``file://`` or a different port. Loopback-only by default.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(pdf)

    def do_OPTIONS(self) -> None:  # noqa: N802
        # CORS preflight — same broad allow as the response above.
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── helpers ───────────────────────────────────────────────────
    def _serve_example(self) -> None:
        """Serve the bundled sample doc.

        Query string ``?kind=pptx`` selects Kawasaki's 10/20/30 pitch
        deck (``example_pptx.md``); anything else (default) returns
        Musk's five-step engineering algorithm (``example.md``).

        Each file is resolved from the installed ``md2star`` package
        first (so the server works from any checkout), then from the
        sibling ``md2star/data/`` folder inside the repo, then from
        ``assets/``. The first match wins.
        """
        from urllib.parse import parse_qs, urlparse
        qs: dict[str, list[str]] = parse_qs(urlparse(self.path).query)
        kind: str = (qs.get("kind") or ["docx"])[0].lower()
        stem: str = "example_pptx" if kind == "pptx" else "example"

        candidates: list[Path] = []
        try:
            import md2star  # type: ignore
            pkg_dir: Path = Path(md2star.__file__).resolve().parent
            candidates.append(pkg_dir / "data" / f"{stem}.md")
        except Exception:
            pass
        candidates += [
            PROJECT_DIR / "md2star" / "data" / f"{stem}.md",
            PROJECT_DIR / "assets" / f"{stem}.md",
        ]
        for cand in candidates:
            if cand.is_file():
                self._serve_file(cand, "text/markdown; charset=utf-8")
                return
        self.send_error(HTTPStatus.NOT_FOUND, f"{stem}.md not bundled")

    def _serve_file(self, path: Path, content_type: str) -> None:
        try:
            body: bytes = path.read_bytes()
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND, f"missing: {path}")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body: bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ── CLI ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="md2star-minimal-gui-server",
        description=(
            "Single-page Overleaf-style editor for md2star: "
            "Markdown on the left, live PDF on the right, "
            "powered by md2docx + headless LibreOffice."
        ),
    )
    parser.add_argument(
        "--bind", default="127.0.0.1",
        help="Address to bind (default: 127.0.0.1 — loopback only).",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Port to bind (default: 8765).",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress access logging.",
    )
    args: argparse.Namespace = parser.parse_args(argv)

    # os_helper owns logging setup for the whole suite; --quiet drops to WARNING.
    osh.init_logging(
        level=logging.WARNING if args.quiet else logging.INFO,
        stdout=False,
        date_format="%H:%M:%S",
    )

    # Sanity-check soffice before binding the port — saves a confused
    # user a debugging round-trip.
    if _find_soffice() is None:
        osh.warning(
            "LibreOffice (soffice) not found. The /render route will return 503 "
            "until you install it: `brew install --cask libreoffice` (macOS) or "
            "`sudo apt install libreoffice` (Debian/Ubuntu)."
        )

    # A non-loopback bind exposes an unauthenticated server that runs md2docx on
    # any markdown a client sends — the same footgun md2star's packaged GUI
    # guards. Print a loud, unmissable banner (no prompt, so scripted runs are
    # not blocked) naming the exact risk, mirroring md2star/gui_server.py.
    if args.bind != "127.0.0.1":
        bar = "═" * 64
        osh.warning(
            "\n" + bar +
            "\n  This preview server is bound to a NON-LOOPBACK address." +
            f"\n     URL: http://{args.bind}:{args.port}/" +
            "\n  It has NO AUTHENTICATION and runs md2docx against any markdown" +
            "\n     a client sends — anyone who can reach this port can drive" +
            "\n     LibreOffice on this machine." +
            "\n  Appropriate ONLY for trusted local-network use. Otherwise bind" +
            "\n     127.0.0.1 (the default) and use SSH port-forwarding." +
            "\n" + bar
        )

    server: http.server.ThreadingHTTPServer = http.server.ThreadingHTTPServer(
        (args.bind, args.port), OverleafHandler,
    )
    url: str = f"http://{args.bind}:{args.port}/"
    osh.info(
        "md2star minimal GUI — serving on %s (static: %s, work: %s). Ctrl-C to stop.",
        url, STATIC_DIR, WORK_DIR,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        osh.info("Shutting down.")
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
