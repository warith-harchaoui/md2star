"""
Live-server tests for the full GUI's new POST routes: /extract and /lint.

Unlike tests/test_gui_security.py (which pokes handler helpers directly), these
spin up the real ``ThreadingHTTPServer`` on an ephemeral port and drive it over
HTTP with the stdlib client, so the do_POST dispatch and the handlers are
exercised end to end.

* /lint always responds (the AI pass is self-guarding: it returns the buffer
  unchanged when Ollama is absent), so it runs everywhere.
* /extract's happy path needs Pandoc (to build a DOCX fixture) and Kreuzberg
  (to read it back), so the round-trip is skipped when either is missing; the
  unsupported-extension rejection runs everywhere.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import threading
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import pytest

from md2star import gui_server

_HAS_KREUZBERG = importlib.util.find_spec("kreuzberg") is not None
_HAS_PANDOC = shutil.which("pandoc") is not None


@pytest.fixture
def server() -> Iterator[str]:
    """Start the GUI server on an ephemeral port; yield its base URL."""
    # Port 0 → the OS assigns a free port, so parallel test runs never clash.
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), gui_server._Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(url: str, *, data: bytes, headers: dict[str, str]) -> tuple[int, bytes]:
    """POST raw bytes and return (status, body), turning HTTP errors into a tuple."""
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — localhost
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_lint_returns_buffer_and_never_crashes(server: str) -> None:
    """/lint echoes a well-formed JSON result even with no Ollama available."""
    payload = json.dumps({"markdown": "# Title\n\nsome text\n"}).encode("utf-8")
    status, body = _post(
        server + "/lint", data=payload, headers={"Content-Type": "application/json"}
    )
    assert status == 200
    result = json.loads(body)
    assert result["ok"] is True
    assert "markdown" in result and isinstance(result["changed"], bool)


def test_extract_rejects_unsupported_extension(server: str) -> None:
    """/extract refuses a non-document extension with a 415."""
    status, _ = _post(
        server + "/extract",
        data=b"not a document",
        headers={"X-Md2star-Ext": ".md"},
    )
    assert status == 415


def _fake_twin(path, out_dir, *, image_handler=None, **_kw):  # noqa: ANN001, ANN202
    """Offline stand-in for ``to_markdown_twin`` (see tests/test_api.py)."""
    from pathlib import Path as _P

    out = _P(out_dir)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "image_1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    md = out / f"{_P(path).stem}.md"
    md.write_text("# Twin\n", encoding="utf-8")
    return md


def test_extract_twin_requires_open_folder(server: str) -> None:
    """Twin mode with no folder open is refused with a 409 (assets need a home)."""
    gui_server._set_folder_root(None)
    status, _ = _post(
        server + "/extract",
        data=b"fake-doc",
        headers={"X-Md2star-Ext": ".docx", "X-Md2star-Twin": "1", "X-Md2star-Name": "note.docx"},
    )
    assert status == 409


def test_extract_twin_writes_assets_and_markdown(
    server: str, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Twin mode writes <stem>.md + assets/ into the open folder and reports them."""
    monkeypatch.setattr("md2star.reverse.to_markdown_twin", _fake_twin, raising=True)
    gui_server._set_folder_root(tmp_path)
    try:
        status, body = _post(
            server + "/extract",
            data=b"fake-doc",
            headers={
                "X-Md2star-Ext": ".docx",
                "X-Md2star-Twin": "1",
                "X-Md2star-Name": "My Report.docx",
            },
        )
    finally:
        gui_server._set_folder_root(None)

    assert status == 200, body
    result = json.loads(body)
    assert result["twin"] is True
    assert result["assets"] == 1
    # The client name is sanitised to a bare, root-relative stem for the .md.
    assert result["filename"] == "My Report.md"
    assert (tmp_path / "My Report.md").exists()
    assert (tmp_path / "assets" / "image_1.png").is_file()


@pytest.mark.skipif(
    not (_HAS_PANDOC and _HAS_KREUZBERG),
    reason="round-trip needs pandoc (forward) + kreuzberg (reverse)",
)
def test_extract_docx_roundtrips_to_markdown(server: str, tmp_path) -> None:
    """A DOCX built by the converter is read back to Markdown through /extract."""
    from md2star.cli import _convert

    md = tmp_path / "in.md"
    md.write_text("# Heading One\n\nA **bold** word.\n", encoding="utf-8")
    docx = tmp_path / "out.docx"
    assert _convert("docx", [str(md), "-o", str(docx)]) == 0

    status, body = _post(
        server + "/extract",
        data=docx.read_bytes(),
        headers={"X-Md2star-Ext": ".docx"},
    )
    assert status == 200
    result = json.loads(body)
    assert result["ok"] is True
    assert "Heading One" in result["markdown"]
    assert "bold" in result["markdown"]
