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
