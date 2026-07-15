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


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        # A single-line hint: headline plus one 2-space-indented hint line.
        (
            errors.MissingDependencyError(
                "pandoc not found", hint="install via brew / apt / winget"
            ),
            ["md2star: pandoc not found", "  install via brew / apt / winget"],
        ),
        # A multiline hint: each line is indented and logged as its own record.
        (
            errors.MissingDependencyError("soffice missing", hint="line 1\nline 2"),
            ["md2star: soffice missing", "  line 1", "  line 2"],
        ),
        # An empty hint: only the headline, no trailing blank hint record.
        (errors.Md2starError("naked error", hint=""), ["md2star: naked error"]),
    ],
    ids=["single-line-hint", "multiline-hint", "empty-hint"],
)
def test_render_error_logs_headline_then_indented_hint(
    exc: errors.Md2starError, expected: list[str], caplog
) -> None:
    """``_render_error`` logs the headline first, then each hint line indented.

    Parametrised over the three hint shapes the renderer must handle. The
    exact record list is asserted so the empty-hint case proves no stray
    blank record leaks out.
    """
    # Capture md2star records at any level for the duration of this test.
    caplog.set_level(logging.DEBUG, logger="md2star")
    _render_error(exc)
    # The full record sequence must match — order and indentation included.
    assert caplog.messages == expected


# ──────────────────────────────────────────────────────────────────
# Invalid input — exit 2 across every wrapper.
# ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "main",
    [md2docx_main, md2pptx_main, md2pdf_main],
    ids=["md2docx", "md2pptx", "md2pdf"],
)
def test_missing_input_returns_2(main, caplog) -> None:
    """Nonexistent input maps to InvalidInputError → exit 2 on every wrapper."""
    caplog.set_level(logging.DEBUG, logger="md2star")
    # A path that cannot exist trips the invalid-input branch.
    rc = main(["/totally/not/here.md"])
    # All three wrappers share the exit-2 contract for bad input.
    assert rc == 2


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
