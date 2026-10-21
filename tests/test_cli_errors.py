"""Top-level error handling in the md2docx / md2pptx / md2pdf wrappers.

The wrappers catch :class:`md2star.errors.Md2starError` subclasses and
print a clean two-block message (``md2star: <headline>`` + indented
``<hint>``) instead of a Python traceback. Exit codes follow shell
conventions: 127 for missing system deps, 2 for invalid input, 1
otherwise.

These tests pin both contracts: the messages reach the logging surface in
the documented shape AND the exit codes match the documented mapping.

Diagnostics now flow through :mod:`md2star.logging` (a logger, not bare
``print``), so we assert on records via pytest's ``caplog`` fixture rather
than on captured stderr. The on-screen shape is unchanged because the
handler's format is ``"%(message)s"`` (see :mod:`md2star.logging`).

The seven original cases collapse into four functional scenarios: the
parametrized ``_render_error`` shape (headline+hint / multiline / empty),
the shared missing-input exit-2 contract across all three wrappers, and
the missing-system-dependency exit-127 contract.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import logging

import pytest

from md2star import errors
from md2star.cli import (
    _render_error,
    md2docx_main,
    md2pdf_main,
    md2pptx_main,
)

# ──────────────────────────────────────────────────────────────────
# Renderer — headline + indented hint, across its three shapes.
# ──────────────────────────────────────────────────────────────────


def test_render_error_logs_headline_then_indented_hint(caplog) -> None:
    """``_render_error`` logs the headline first, then each hint line indented.

    Sweeps the three hint shapes: single-line, multiline (each line its own
    indented record), and empty (headline only — proving no stray blank record).
    """
    cases = [
        (
            errors.MissingDependencyError(
                "pandoc not found", hint="install via brew / apt / winget"
            ),
            ["md2star: pandoc not found", "  install via brew / apt / winget"],
        ),
        (
            errors.MissingDependencyError("soffice missing", hint="line 1\nline 2"),
            ["md2star: soffice missing", "  line 1", "  line 2"],
        ),
        (errors.Md2starError("naked error", hint=""), ["md2star: naked error"]),
    ]
    for exc, expected in cases:
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="md2star")
        _render_error(exc)
        # The full record sequence must match — order and indentation included.
        assert caplog.messages == expected


# ──────────────────────────────────────────────────────────────────
# Invalid input — exit 2 across every wrapper.
# ──────────────────────────────────────────────────────────────────


def test_missing_input_returns_2(caplog) -> None:
    """Nonexistent input maps to InvalidInputError → exit 2 on every wrapper."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    # A path that cannot exist trips the invalid-input branch on all three.
    for main in (md2docx_main, md2pptx_main, md2pdf_main):
        assert main(["/totally/not/here.md"]) == 2


def test_missing_input_message_shape(caplog) -> None:
    """The exit-2 path also logs the documented headline + hint substrings."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    # Drive one wrapper to inspect the human-facing message, not just the code.
    rc = md2docx_main(["/totally/not/here.md"])
    assert rc == 2
    # Headline + hint are logged; both substrings appear across the records.
    assert "input file not found" in caplog.text
    assert "md2star accepts a single" in caplog.text


# ──────────────────────────────────────────────────────────────────
# Missing system dependency — exit 127 (shell "command not found").
# ──────────────────────────────────────────────────────────────────


def test_missing_pandoc_returns_127(caplog, monkeypatch, tmp_path) -> None:
    """Simulate pandoc absent from PATH → MissingDependencyError → exit 127."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    md = tmp_path / "doc.md"
    md.write_text("# Hi\n")

    # shutil.which sees nothing, so the dependency probe fails.
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)

    rc = md2docx_main([str(md)])
    # 127 is the shell "command not found" convention for a missing binary.
    assert rc == 127
    # The message names the missing tool and the install hint.
    assert "pandoc not found" in caplog.text
    assert "brew install pandoc" in caplog.text


# ──────────────────────────────────────────────────────────────────
# Unreadable input — the user's file/directory, not an md2star bug.
# ──────────────────────────────────────────────────────────────────


def test_non_utf8_input_returns_2_not_a_traceback(caplog, tmp_path) -> None:
    """A Latin-1 source is invalid input, so it must not raise.

    `read_text(encoding="utf-8")` used to let UnicodeDecodeError escape, and
    this module's contract is that a traceback means "please file a bug" — so
    a user whose file came out of a Windows editor was being told they had
    found one. The message names the offending byte and its offset so they
    can find it.
    """
    caplog.set_level(logging.DEBUG, logger="md2star")
    src = tmp_path / "latin1.md"
    src.write_bytes("# Café\n\npère\n".encode("latin-1"))

    rc = md2docx_main([str(src), "-o", str(tmp_path / "out.docx"), "--offline"])
    assert rc == 2
    assert "not valid UTF-8" in caplog.text
    assert "0xe9" in caplog.text  # the byte it choked on
    assert "offset 5" in caplog.text
    assert "iconv" in caplog.text  # an actionable way out


def test_unwritable_source_dir_returns_2_not_a_traceback(caplog, tmp_path) -> None:
    """A read-only source directory is a setup problem, reported as one.

    The preprocessed Markdown is written beside the input on purpose, so that
    relative image paths keep resolving — which means a read-only source dir
    cannot work. It used to surface as a raw PermissionError from tempfile.
    """
    import os
    import stat

    src_dir = tmp_path / "readonly"
    src_dir.mkdir()
    src = src_dir / "doc.md"
    src.write_text("# Hi\n\nText.\n", encoding="utf-8")
    os.chmod(src_dir, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(src_dir, os.W_OK):  # running as root ignores the mode
            pytest.skip("source dir is still writable (running as root?)")
        caplog.set_level(logging.DEBUG, logger="md2star")
        rc = md2docx_main([str(src), "-o", str(tmp_path / "out.docx"), "--offline"])
        assert rc == 2
        assert "cannot write a working file next to doc.md" in caplog.text
        assert "writable" in caplog.text
    finally:
        # Restore before tmp_path cleanup, which otherwise cannot recurse in.
        os.chmod(src_dir, stat.S_IRWXU)
