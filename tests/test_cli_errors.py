"""Top-level error handling in the md2docx / md2pptx / md2pdf wrappers.

The wrappers catch :class:`md2star.errors.Md2starError` subclasses and
print a clean two-block message (``md2star: <headline>`` + indented
``<hint>``) instead of a Python traceback. Exit codes follow shell
conventions: 127 for missing system deps, 2 for invalid input, 1
otherwise.

These tests pin both contracts: the messages reach stderr in the
documented shape AND the exit codes match the documented mapping.
"""

from __future__ import annotations

import pytest

from md2star import errors
from md2star.cli import (
    _render_error,
    md2docx_main,
    md2pdf_main,
    md2pptx_main,
)


# ──────────────────────────────────────────────────────────────────
# Renderer — headline + indented hint


def test_render_error_writes_headline_and_hint(capsys) -> None:
    """`_render_error` produces a two-block stderr message."""
    exc = errors.MissingDependencyError(
        "pandoc not found",
        hint="install via brew / apt / winget",
    )
    _render_error(exc)
    err = capsys.readouterr().err
    assert "md2star: pandoc not found" in err
    assert "  install via brew / apt / winget" in err


def test_render_error_handles_multiline_hint(capsys) -> None:
    """Each line of the hint is indented separately."""
    exc = errors.MissingDependencyError(
        "soffice missing",
        hint="line 1\nline 2",
    )
    _render_error(exc)
    err = capsys.readouterr().err
    assert "  line 1" in err
    assert "  line 2" in err


def test_render_error_skips_empty_hint(capsys) -> None:
    """An empty hint emits only the headline (no trailing whitespace line)."""
    exc = errors.Md2starError("naked error", hint="")
    _render_error(exc)
    err = capsys.readouterr().err.strip()
    assert err == "md2star: naked error"


# ──────────────────────────────────────────────────────────────────
# md2docx / md2pptx / md2pdf — invalid input path


def test_md2docx_missing_input_returns_2(capsys) -> None:
    """Nonexistent input maps to InvalidInputError → exit 2."""
    rc = md2docx_main(["/totally/not/here.md"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "input file not found" in err
    assert "md2star accepts a single" in err


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


def test_missing_pandoc_returns_127(capsys, monkeypatch, tmp_path) -> None:
    """Simulate pandoc absent from PATH → MissingDependencyError → exit 127."""
    md = tmp_path / "doc.md"
    md.write_text("# Hi\n")

    # shutil.which sees nothing.
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)

    rc = md2docx_main([str(md)])
    assert rc == 127
    err = capsys.readouterr().err
    assert "pandoc not found" in err
    assert "brew install pandoc" in err
