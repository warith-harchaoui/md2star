"""Path-confinement tests for the GUI's /fs/* endpoints.

The endpoints expose a small folder-browser API to the localhost
client. Everything funnels through ``gui_server._safe_within_root``
which:

* refuses absolute paths (``/etc/passwd``, ``C:\\Windows\\…``)
* refuses ``..`` traversal that would escape the open folder
* refuses symlinks whose resolved target is outside the open folder
* permits legitimate nested files

These tests poke each branch directly (no HTTP / live server needed).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from md2star import gui_server


@pytest.fixture
def open_root(tmp_path, monkeypatch):
    """Open ``tmp_path`` as the gui_server's folder root for the test.

    Cleans up afterwards so other tests aren't left with a stale root.
    """
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


class TestNoFolderOpen:
    """With no folder root set, every path is rejected."""

    def test_returns_none_when_no_root(self):
        gui_server._set_folder_root(None)
        assert gui_server._safe_within_root("foo.md") is None


class TestNestedFilesAllowed:
    """Legitimate paths inside the root resolve fine."""

    def test_simple_file(self, open_root):
        _make(open_root, "alpha.md")
        result = gui_server._safe_within_root("alpha.md")
        assert result is not None
        assert result.name == "alpha.md"
        assert result.parent == open_root

    def test_nested_file(self, open_root):
        _make(open_root, "sub/nested.md")
        result = gui_server._safe_within_root("sub/nested.md")
        assert result is not None
        assert "sub" in result.parts


class TestPathTraversal:
    """``..`` segments cannot escape the open root."""

    def test_double_dot_blocked(self, open_root):
        assert gui_server._safe_within_root("../escape.md") is None

    def test_deep_double_dot_blocked(self, open_root):
        assert gui_server._safe_within_root("sub/../../escape.md") is None

    def test_double_dot_to_etc_blocked(self, open_root):
        # On macOS / Linux this would resolve to something like
        # /private/var/folders/.../etc/passwd, which is outside the
        # workspace root.
        assert gui_server._safe_within_root("../../../etc/passwd") is None


class TestAbsolutePathsBlocked:
    """Absolute paths short-circuit before resolve() can do anything."""

    def test_posix_absolute(self, open_root):
        assert gui_server._safe_within_root("/etc/passwd") is None

    def test_windows_absolute_drive(self, open_root):
        assert gui_server._safe_within_root("C:\\Windows\\System32\\foo") is None

    def test_unix_absolute_to_temp(self, open_root):
        assert gui_server._safe_within_root("/tmp/notes.md") is None


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="symlink test relies on POSIX symlink semantics",
)
class TestSymlinkEscape:
    """A symlink inside the root whose target is OUTSIDE the root is rejected."""

    def test_symlink_to_outside_file(self, open_root, tmp_path):
        # Create a real file outside the workspace.
        outside = tmp_path / "outside.md"
        outside.write_text("secret")
        # Inside the workspace, drop a symlink pointing at the outside file.
        link = open_root / "trap.md"
        link.symlink_to(outside)
        # The link's resolved target leaves the root → rejected.
        assert gui_server._safe_within_root("trap.md") is None

    def test_symlink_to_inside_file_allowed(self, open_root):
        # A symlink to a sibling INSIDE the root is fine.
        real = _make(open_root, "real.md")
        link = open_root / "alias.md"
        link.symlink_to(real)
        result = gui_server._safe_within_root("alias.md")
        assert result is not None
        # Resolves to the real file path inside the root.
        assert result.resolve() == real.resolve()


class TestEmptyAndDotRelative:
    """Edge cases around the empty / dot path."""

    def test_dot_resolves_to_root(self, open_root):
        # "." is the open root itself — legal.
        result = gui_server._safe_within_root(".")
        # We allow this; some handlers may not want it but the
        # confinement test is "stays inside the root".
        assert result is not None
        assert result == open_root


class TestSessionTemplateConfinement:
    """``_session_template`` honors the same fmt allowlist (docx / pptx only)."""

    def test_invalid_fmt_returns_none(self):
        # Even if session dir exists, only docx/pptx are valid formats.
        gui_server._set_folder_root(Path("/tmp"))
        assert gui_server._session_template("png") is None
        assert gui_server._session_template("../etc/passwd") is None
        gui_server._set_folder_root(None)
