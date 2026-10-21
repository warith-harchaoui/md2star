"""Path-confinement tests for the GUI's /fs/* endpoints.

Everything funnels through ``gui_server._safe_within_root``, which refuses
absolute paths, ``..`` traversal, and symlinks resolving outside the open
folder, while permitting legitimate nested files. These tests poke the branches
directly (no live server). They are grouped by behaviour but keep every
individual security assertion — this is the security surface, so nothing is
dropped, only consolidated.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from md2star import gui_server


@pytest.fixture
def open_root(tmp_path, monkeypatch):
    """Open ``tmp_path/workspace`` as the folder root, resetting it afterwards."""
    root = tmp_path / "workspace"
    root.mkdir()
    gui_server._set_folder_root(root.resolve())
    yield root.resolve()
    gui_server._set_folder_root(None)


def _make(root: Path, rel: str, content: str = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def test_confinement_allows_inside_and_blocks_escapes(open_root) -> None:
    """Legitimate nested paths resolve; traversal and absolute paths are rejected.

    Covers the full allow/deny matrix in one pass: no-root rejection, simple and
    nested files, ``.`` = root, ``..`` traversal (shallow/deep/to-/etc), and
    POSIX + Windows absolute paths.
    """
    # Nested files inside the root resolve to real paths within it.
    _make(open_root, "alpha.md")
    _make(open_root, "sub/nested.md")
    simple = gui_server._safe_within_root("alpha.md")
    assert simple is not None and simple.name == "alpha.md" and simple.parent == open_root
    nested = gui_server._safe_within_root("sub/nested.md")
    assert nested is not None and "sub" in nested.parts
    # "." is the root itself — allowed (stays inside).
    assert gui_server._safe_within_root(".") == open_root

    # Every escape attempt returns None.
    for bad in [
        "../escape.md",
        "sub/../../escape.md",
        "../../../etc/passwd",  # traversal
        "/etc/passwd",
        "/tmp/notes.md",
        "C:\\Windows\\System32\\foo",  # absolute
    ]:
        assert gui_server._safe_within_root(bad) is None, bad

    # With no folder open, even a plain name is rejected.
    gui_server._set_folder_root(None)
    assert gui_server._safe_within_root("foo.md") is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink semantics")
def test_symlink_confinement(open_root, tmp_path) -> None:
    """A symlink whose target escapes the root is rejected; an inside one is allowed."""
    # Symlink pointing OUTSIDE the workspace → rejected.
    outside = tmp_path / "outside.md"
    outside.write_text("secret")
    (open_root / "trap.md").symlink_to(outside)
    assert gui_server._safe_within_root("trap.md") is None

    # Symlink to a sibling INSIDE the workspace → allowed, resolves to the real file.
    real = _make(open_root, "real.md")
    (open_root / "alias.md").symlink_to(real)
    result = gui_server._safe_within_root("alias.md")
    assert result is not None and result.resolve() == real.resolve()


def test_session_template_fmt_allowlist() -> None:
    """``_session_template`` honours the docx/pptx allowlist and rejects the rest."""
    gui_server._set_folder_root(Path("/tmp"))
    try:
        assert gui_server._session_template("png") is None
        assert gui_server._session_template("../etc/passwd") is None
    finally:
        gui_server._set_folder_root(None)


# ── who is asking: Origin / Host gate ────────────────────────────────────────
# Path confinement answers what a request may touch. These answer who may ask.
# They run a real server on loopback and send the exact headers a browser
# would, because the hole they close is a property of the HTTP exchange rather
# than of any one handler.


@pytest.fixture
def live_server(tmp_path):
    """A real GUI server on a free loopback port, with a folder already open."""
    import http.client
    import threading
    from http.server import ThreadingHTTPServer

    root = tmp_path / "notes"
    root.mkdir()
    (root / "thesis.md").write_text("# years of work\n", encoding="utf-8")
    gui_server._set_folder_root(root.resolve())

    srv = ThreadingHTTPServer(("127.0.0.1", 0), gui_server._Handler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()

    def request(method: str, path: str, *, headers: dict, body: str | None = None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()

    try:
        yield request, port, root
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)
        gui_server._set_folder_root(None)


def test_the_page_itself_is_served(live_server) -> None:
    """The legitimate case: same-origin, loopback Host. Must still work."""
    request, port, root = live_server
    host = f"127.0.0.1:{port}"
    status, body = request(
        "POST",
        "/fs/save",
        headers={"Host": host, "Origin": f"http://{host}", "Content-Type": "application/json"},
        body=json.dumps({"path": "thesis.md", "content": "# edited\n"}),
    )
    assert status == 200, body
    assert (root / "thesis.md").read_text() == "# edited\n"


def test_a_local_script_with_no_origin_still_works(live_server) -> None:
    """curl and scripted local use send no Origin; that must stay allowed.

    A browser cannot be made to *omit* Origin on a cross-origin call, so
    "absent" is not a hole an attacker can walk through.
    """
    request, port, root = live_server
    status, body = request(
        "POST",
        "/fs/save",
        headers={"Host": f"127.0.0.1:{port}", "Content-Type": "application/json"},
        body=json.dumps({"path": "thesis.md", "content": "# by script\n"}),
    )
    assert status == 200, body
    assert (root / "thesis.md").read_text() == "# by script\n"


def test_another_site_cannot_delete_your_notes(live_server) -> None:
    """The attack, end to end: a cross-origin simple request must not land.

    ``text/plain`` is CORS-safelisted, so this is a *simple* request — there is
    no preflight for the server to refuse, and the attacker never needs to read
    a reply. Before the Origin gate, ``/fs/open {"path": "~"}`` followed by
    ``/fs/delete`` ran happily from any page the user had open.
    """
    request, port, root = live_server
    evil = {
        "Host": f"127.0.0.1:{port}",
        "Origin": "https://evil.example",
        "Content-Type": "text/plain;charset=UTF-8",
    }
    # Re-point the root at the user's home…
    status, _ = request("POST", "/fs/open", headers=evil, body=json.dumps({"path": "~"}))
    assert status == 403
    assert gui_server._folder_root() == root.resolve()  # root never moved
    # …and delete / overwrite what is there.
    status, _ = request(
        "POST", "/fs/delete", headers=evil, body=json.dumps({"paths": ["thesis.md"]})
    )
    assert status == 403
    status, _ = request(
        "POST", "/fs/save", headers=evil, body=json.dumps({"path": "thesis.md", "content": "owned"})
    )
    assert status == 403
    assert (root / "thesis.md").read_text() == "# years of work\n"


def test_a_rebound_domain_is_refused_even_though_its_origin_matches(live_server) -> None:
    """DNS rebinding: Origin agrees with Host, and Host is the giveaway.

    An attacker domain resolved to 127.0.0.1 is same-origin to the browser, so
    the Origin check alone would pass it. What it cannot change is the name it
    puts in ``Host``.
    """
    request, port, root = live_server
    status, _ = request(
        "POST",
        "/fs/delete",
        headers={
            "Host": f"evil.example:{port}",
            "Origin": f"http://evil.example:{port}",
            "Content-Type": "application/json",
        },
        body=json.dumps({"paths": ["thesis.md"]}),
    )
    assert status == 403
    assert (root / "thesis.md").exists()


def test_an_opaque_origin_is_not_treated_as_absent(live_server) -> None:
    """A sandboxed iframe or a file:// page sends ``Origin: null``.

    It is not this page, so folding it in with "no Origin at all" would hand
    the hole straight back.
    """
    request, port, root = live_server
    status, _ = request(
        "POST",
        "/fs/delete",
        headers={
            "Host": f"127.0.0.1:{port}",
            "Origin": "null",
            "Content-Type": "application/json",
        },
        body=json.dumps({"paths": ["thesis.md"]}),
    )
    assert status == 403
    assert (root / "thesis.md").exists()


def test_reading_your_markdown_is_gated_too(live_server) -> None:
    """GET is not exempt: ``/fs/read`` hands back the user's own prose."""
    request, port, _ = live_server
    status, _ = request(
        "GET",
        "/fs/read?path=thesis.md",
        headers={"Host": f"127.0.0.1:{port}", "Origin": "https://evil.example"},
    )
    assert status == 403


def test_host_name_parsing_keeps_ipv6_literals_whole() -> None:
    """Splitting on the last colon would cut ``[::1]:8765`` in half."""
    assert gui_server._host_name("127.0.0.1:8765") == "127.0.0.1"
    assert gui_server._host_name("localhost") == "localhost"
    assert gui_server._host_name("[::1]:8765") == "[::1]"
    assert gui_server._host_name("LocalHost:1234") == "localhost"


# ── free text reaching a response header ─────────────────────────────────────
# A successful render forwards the converter's warnings in `X-Md2star-Stderr`.
# `send_header` writes `name: value\r\n` and validates nothing, so that header
# is the one place where captured text decides response *structure*.


def test_a_newline_cannot_split_the_render_response(live_server, monkeypatch) -> None:
    """A multi-line warning must not forge a header or a body.

    `encode("ascii", "replace")` does not save us here: CR and LF *are* ASCII,
    so they pass through untouched. Driven over a raw socket because the defect
    is only visible in the bytes on the wire — an HTTP client library parses
    the forged header as if the server had meant it.
    """
    import http.client
    import io
    import socket

    request, port, root = live_server

    # A converter that succeeds while warning in several lines, which is the
    # "rendered OK, with warnings" case the header exists to carry.
    def fake_convert(fmt: str, argv: list[str]) -> int:
        out = Path(argv[argv.index("-o") + 1])
        out.write_bytes(b"%PDF-1.4 real output")
        # Shaped exactly like a splitting payload: a plausible warning, then a
        # forged header, then the blank line that would end the header block,
        # then a body of the attacker's choosing.
        sys.stderr.write(
            "\r\n".join(
                [
                    "md2star warning: postprocess failed",
                    "X-Injected: yes",
                    "",
                    "<html>forged body</html>",
                ]
            )
        )
        return 0

    # Patched at its source: the handler does `from .cli import _convert`
    # inside the request, so the name it resolves is md2star.cli's.
    import md2star.cli

    monkeypatch.setattr(md2star.cli, "_convert", fake_convert)

    body = json.dumps({"markdown": "# hi\n", "format": "pdf"})
    sock = socket.create_connection(("127.0.0.1", port), timeout=30)
    try:
        sock.sendall(
            (
                f"POST /render HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n"
            ).encode()
            + body.encode()
        )
        raw = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            raw += chunk
    finally:
        sock.close()

    head, _, payload = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")

    # The attacker's text may appear *inside* one header value — harmless. What
    # must not happen is it becoming a header line, or a body, of its own.
    assert not any(line.lower().startswith(b"x-injected") for line in lines), head
    assert payload == b"%PDF-1.4 real output", payload[:120]

    # The warning still arrives, flattened onto exactly one line: a fix that
    # dropped the text would pass the checks above and tell the user nothing.
    carried = [line for line in lines if line.lower().startswith(b"x-md2star-stderr:")]
    assert len(carried) == 1
    assert b"postprocess failed" in carried[0]
    assert b"forged body" in carried[0]

    # And a real client agrees there is one well-formed header block.
    parsed = http.client.parse_headers(io.BytesIO(head.split(b"\r\n", 1)[1] + b"\r\n\r\n"))
    assert parsed.get("X-Injected") is None
    assert "postprocess failed" in parsed["X-Md2star-Stderr"]


def test_single_line_header_flattens_every_whitespace_run() -> None:
    """No CR, LF or tab may survive, and the text must stay readable."""
    assert gui_server._single_line_header("a\r\nb") == "a b"
    assert gui_server._single_line_header("a\n\nX-Evil: 1") == "a X-Evil: 1"
    assert gui_server._single_line_header("  padded \t out  ") == "padded out"
    assert gui_server._single_line_header("héllo") == "h?llo"
    assert gui_server._single_line_header("x" * 50, limit=10) == "x" * 10
    assert gui_server._single_line_header("   ") == ""


# ── the extension header becomes part of a filename ──────────────────────────


def test_extract_refuses_an_extension_that_is_a_path(live_server) -> None:
    """``X-Md2star-Ext`` is matched whole, not suffix-sniffed.

    The header lands inside the name `/extract` writes the upload to, and
    `is_supported()` only looks at the suffix — so `../../x.pdf` passed the
    old check. Nothing escaped, because the literal stem in front glued the
    `../` onto a directory that does not exist, but that was the prefix
    saving us rather than the validation, and the write failed with an
    unhandled FileNotFoundError instead of a clean refusal.
    """
    request, port, _ = live_server
    host = f"127.0.0.1:{port}"
    for evil in ("../../../../tmp/pwned.pdf", "/../../tmp/pwned.pdf", "/tmp/pwned.pdf"):
        status, body = request(
            "POST",
            "/extract",
            headers={"Host": host, "X-Md2star-Ext": evil, "Content-Type": "application/pdf"},
            body="%PDF-1.4 whatever",
        )
        assert status == 415, f"{evil!r} was not refused: {status} {body!r}"
    assert not Path("/tmp/pwned.pdf").exists()


def test_vendor_assets_stay_under_vendor(monkeypatch) -> None:
    """``/vendor/...`` is confined by the guard, on every OS.

    The old guard rejected a ``".."`` segment after splitting on ``"/"`` only.
    A backslash is a separator on Windows, so ``..\\..\\secret`` arrived as one
    segment it waved through and the OS then resolved out of the vendor
    directory. Reachability was narrow — reading needs the reply, so a browser
    is stopped by the Origin gate and the same-origin policy — but the
    docstring promised confinement it did not deliver off POSIX.

    The filesystem is stubbed out on purpose. On POSIX a traversal fails
    anyway, because ``..\\..\\secret`` is merely an odd filename that does not
    exist, so a test run here would pass against the old code and prove
    nothing. Handing the lookup a store that answers *every* path makes the
    guard the only thing that can refuse — which is what we mean to assert.
    """

    class _AnyFile:
        """A store where every path exists, so only the guard can say no."""

        def joinpath(self, *parts):
            return self

        def read_bytes(self):
            return b"SECRET"

    monkeypatch.setattr(gui_server.resources, "files", lambda _pkg: _AnyFile())

    for evil in (
        "..\\..\\..\\secret.txt",
        "../../../secret.txt",
        "/etc/passwd",
        "subdir\\..\\..\\x",
        "C:\\Windows\\win.ini",
        "./x",
        "",
    ):
        assert gui_server._read_vendor(evil) is None, f"{evil!r} was not refused"

    # The same stub must still hand back an ordinary nested asset, so the
    # assertions above are about traversal and not about refusing everything.
    assert gui_server._read_vendor("pdfjs/pdf.worker.js") == b"SECRET"


def test_a_real_vendor_asset_is_still_served() -> None:
    """Confinement must not cost us the assets the editor needs offline."""
    from importlib import resources

    vendor = resources.files("md2star.data.gui").joinpath("vendor")
    names = [p.name for p in vendor.iterdir() if p.is_file()]
    assert names, "no vendored asset to test against"
    assert gui_server._read_vendor(names[0]) is not None
