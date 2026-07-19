"""Tests for the click front-end (``md2star.click_cli``).

The click CLI is a thin adapter over :func:`md2star.cli._convert`; these tests
verify the adapter, not the conversion pipeline (which has its own coverage). We
mock ``_convert`` so the tests are fast and need no Pandoc: what matters is that
click options are translated into the right argv and that exit codes propagate.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from md2star import click_cli


def test_argv_from_options_maps_all_flags() -> None:
    """Every supplied option becomes the matching argparse-style flag."""
    argv = click_cli._argv_from_options(
        "doc.md",
        {
            "output": "out.docx",
            "author": "Ada",
            "bib": "refs.bib",
            "bibliography_name": "Works",
            "lang": "en",
            "date": "2026",
            "reference_doc": "tpl.docx",
            "skip_phase": "mermaid",
            "offline": True,
            "no_remote_templates": True,
            "allow_remote_images": True,
            "verbose": True,
            "quiet": False,
            "lint": True,
        },
    )
    # Input stays first; each value flag is followed by its value.
    assert argv[0] == "doc.md"
    for flag, val in [
        ("--output", "out.docx"), ("--author", "Ada"), ("--bib", "refs.bib"),
        ("--bibliography-name", "Works"), ("--lang", "en"), ("--date", "2026"),
        ("--reference-doc", "tpl.docx"), ("--skip-phase", "mermaid"),
    ]:
        assert argv[argv.index(flag) + 1] == val
    # Boolean switches appear as bare flags; --lint (True) not --no-lint.
    assert "--offline" in argv and "--allow-remote-images" in argv
    assert "--verbose" in argv and "--quiet" not in argv
    assert "--lint" in argv and "--no-lint" not in argv


def test_argv_omits_unset_options() -> None:
    """Unset options are absent so template/metadata defaults win."""
    argv = click_cli._argv_from_options("d.md", {"lint": None})
    assert argv == ["d.md"]  # nothing but the input


def test_lint_tristate_emits_no_lint() -> None:
    """--no-lint (lint=False) forwards explicitly, distinct from unset."""
    assert "--no-lint" in click_cli._argv_from_options("d.md", {"lint": False})


@pytest.mark.parametrize("fmt", ["docx", "pptx", "pdf"])
def test_format_command_delegates_to_convert(monkeypatch, tmp_path, fmt) -> None:
    """Each format command calls _convert with its fmt and returns rc 0."""
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(click_cli, "_convert", lambda f, argv: calls.append((f, argv)) or 0)
    src = tmp_path / "in.md"
    src.write_text("# hi\n")

    result = CliRunner().invoke(click_cli.cli, [fmt, str(src), "--author", "Ada"])
    assert result.exit_code == 0
    assert calls and calls[0][0] == fmt
    assert calls[0][1][0] == str(src) and "--author" in calls[0][1]


def test_nonzero_convert_propagates(monkeypatch, tmp_path) -> None:
    """A non-zero _convert exit code surfaces as the command's exit code."""
    monkeypatch.setattr(click_cli, "_convert", lambda f, argv: 1)
    src = tmp_path / "in.md"
    src.write_text("# hi\n")
    result = CliRunner().invoke(click_cli.cli, ["docx", str(src)])
    assert result.exit_code == 1


def test_missing_input_is_click_usage_error(tmp_path) -> None:
    """A nonexistent input is rejected by click before _convert runs."""
    result = CliRunner().invoke(click_cli.cli, ["docx", str(tmp_path / "nope.md")])
    assert result.exit_code == 2  # click usage error for a bad Path(exists=True)


def test_version_flag() -> None:
    """`md2star-x --version` prints the single-sourced version."""
    from md2star import __version__

    result = CliRunner().invoke(click_cli.cli, ["--version"])
    assert result.exit_code == 0 and __version__ in result.output


def test_gui_command_delegates(monkeypatch) -> None:
    """`md2star-x gui` forwards port/bind/no-browser to the GUI entry."""
    import md2star.gui_server as gs

    seen: list[list[str]] = []
    monkeypatch.setattr(gs, "main", lambda argv: seen.append(argv) or 0)
    result = CliRunner().invoke(click_cli.cli, ["gui", "--port", "9000", "--no-browser"])
    assert result.exit_code == 0
    assert "--port" in seen[0] and "9000" in seen[0] and "--no-browser" in seen[0]


def test_doctor_command_delegates(monkeypatch) -> None:
    """`md2star-x doctor --json` forwards to the doctor entry."""
    import md2star.doctor as doc

    seen: list[list[str]] = []
    monkeypatch.setattr(doc, "main", lambda argv: seen.append(argv) or 0)
    result = CliRunner().invoke(click_cli.cli, ["doctor", "--json"])
    assert result.exit_code == 0 and seen[0] == ["--json"]


def test_main_returns_int(monkeypatch, tmp_path) -> None:
    """The `main()` wrapper returns an int exit code (not sys.exit)."""
    monkeypatch.setattr(click_cli, "_convert", lambda f, argv: 0)
    src = tmp_path / "in.md"
    src.write_text("# hi\n")
    assert click_cli.main(["docx", str(src)]) == 0
    # A usage error (missing input) comes back as a non-zero int, not a raise.
    assert click_cli.main(["docx", str(tmp_path / "missing.md")]) != 0
