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
"""

from __future__ import annotations

import logging

from md2star import errors
from md2star.cli import (
    _render_error,
    md2docx_main,
    md2pdf_main,
    md2pptx_main,
)

# ──────────────────────────────────────────────────────────────────
# Renderer — headline + indented hint


def test_render_error_writes_headline_and_hint(caplog) -> None:
    """`_render_error` logs a two-block message (headline + indented hint)."""
    # Capture md2star records at any level for the duration of this test.
    caplog.set_level(logging.DEBUG, logger="md2star")
    exc = errors.MissingDependencyError(
        "pandoc not found",
        hint="install via brew / apt / winget",
    )
    _render_error(exc)
    # Headline and hint are separate records; the hint keeps its 2-space indent.
    assert "md2star: pandoc not found" in caplog.messages
    assert "  install via brew / apt / winget" in caplog.messages


def test_render_error_handles_multiline_hint(caplog) -> None:
    """Each line of the hint is indented and logged separately."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    exc = errors.MissingDependencyError(
        "soffice missing",
        hint="line 1\nline 2",
    )
    _render_error(exc)
    assert "  line 1" in caplog.messages
    assert "  line 2" in caplog.messages


def test_render_error_skips_empty_hint(caplog) -> None:
    """An empty hint emits only the headline record (no blank hint line)."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    exc = errors.Md2starError("naked error", hint="")
    _render_error(exc)
    # Exactly one record: the headline. No trailing empty-hint record.
    assert caplog.messages == ["md2star: naked error"]


# ──────────────────────────────────────────────────────────────────
# md2docx / md2pptx / md2pdf — invalid input path


def test_md2docx_missing_input_returns_2(caplog) -> None:
    """Nonexistent input maps to InvalidInputError → exit 2."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    rc = md2docx_main(["/totally/not/here.md"])
    assert rc == 2
    # Headline + hint are logged; both substrings appear across the records.
    assert "input file not found" in caplog.text
    assert "md2star accepts a single" in caplog.text


def test_md2pptx_missing_input_returns_2(capsys) -> None:
    """Same contract on the PPTX wrapper."""
    rc = md2pptx_main(["/nope/missing.md"])
    assert rc == 2


def test_md2pdf_missing_input_returns_2(capsys) -> None:
    """Same contract on the PDF wrapper."""
    rc = md2pdf_main(["/nope/missing.md"])
    assert rc == 2


# ──────────────────────────────────────────────────────────────────
# Missing system dependency — exit 127 (shell "command not found"
# convention).


def test_missing_pandoc_returns_127(caplog, monkeypatch, tmp_path) -> None:
    """Simulate pandoc absent from PATH → MissingDependencyError → exit 127."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    md = tmp_path / "doc.md"
    md.write_text("# Hi\n")

    # shutil.which sees nothing.
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)

    rc = md2docx_main([str(md)])
    assert rc == 127
    assert "pandoc not found" in caplog.text
    assert "brew install pandoc" in caplog.text
