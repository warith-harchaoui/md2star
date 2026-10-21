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
