"""Tests for the click front-end (``md2star.click_cli``).

The click CLI is a thin adapter over :func:`md2star.cli._convert`; these tests
verify the adapter (option→argv translation, delegation, exit-code propagation),
not the conversion pipeline. ``_convert`` and the GUI/doctor entries are mocked
so the tests are fast and need no Pandoc.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from md2star import click_cli


def test_argv_translation_covers_all_option_kinds() -> None:
    """Value flags, boolean switches, the lint tri-state, and unset options."""
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
    assert argv[0] == "doc.md"
    for flag, val in [
        ("--output", "out.docx"),
        ("--author", "Ada"),
        ("--bib", "refs.bib"),
        ("--bibliography-name", "Works"),
        ("--lang", "en"),
        ("--date", "2026"),
        ("--reference-doc", "tpl.docx"),
        ("--skip-phase", "mermaid"),
    ]:
        assert argv[argv.index(flag) + 1] == val
    assert "--offline" in argv and "--allow-remote-images" in argv
    assert "--verbose" in argv and "--quiet" not in argv
    assert "--lint" in argv and "--no-lint" not in argv

    # Unset options vanish (template/metadata defaults win); lint=False forwards
    # explicitly, distinct from lint=None.
    assert click_cli._argv_from_options("d.md", {"lint": None}) == ["d.md"]
    assert "--no-lint" in click_cli._argv_from_options("d.md", {"lint": False})


@pytest.mark.parametrize("fmt", ["docx", "pptx", "pdf"])
def test_format_command_delegates_and_propagates(monkeypatch, tmp_path, fmt) -> None:
    """Each format command calls _convert(fmt, …) and mirrors its exit code."""
    rc_box = {"rc": 0}
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        click_cli, "_convert", lambda f, argv: calls.append((f, argv)) or rc_box["rc"]
    )
    src = tmp_path / "in.md"
    src.write_text("# hi\n")

    # Success path: fmt + input + flag reach _convert, exit 0.
    ok = CliRunner().invoke(click_cli.cli, [fmt, str(src), "--author", "Ada"])
    assert ok.exit_code == 0 and calls[0][0] == fmt
    assert calls[0][1][0] == str(src) and "--author" in calls[0][1]

    # Non-zero _convert propagates as the command exit code.
    rc_box["rc"] = 1
    assert CliRunner().invoke(click_cli.cli, [fmt, str(src)]).exit_code == 1


def test_bad_input_and_version() -> None:
    """A missing input is a click usage error (2); --version prints the version."""
    from md2star import __version__

    miss = CliRunner().invoke(click_cli.cli, ["docx", "/no/such/file.md"])
    assert miss.exit_code == 2  # click rejects Path(exists=True) before _convert

    ver = CliRunner().invoke(click_cli.cli, ["--version"])
    assert ver.exit_code == 0 and __version__ in ver.output


def test_gui_doctor_and_main_wrapper(monkeypatch, tmp_path) -> None:
    """gui/doctor delegate to their entries; main() returns an int, never raises."""
    import md2star.doctor as doc
    import md2star.gui_server as gs

    seen: dict[str, list[str]] = {}
    monkeypatch.setattr(gs, "main", lambda argv: seen.__setitem__("gui", argv) or 0)
    monkeypatch.setattr(doc, "main", lambda argv: seen.__setitem__("doctor", argv) or 0)

    assert (
        CliRunner().invoke(click_cli.cli, ["gui", "--port", "9000", "--no-browser"]).exit_code == 0
    )
    assert "--port" in seen["gui"] and "9000" in seen["gui"] and "--no-browser" in seen["gui"]
    assert CliRunner().invoke(click_cli.cli, ["doctor", "--json"]).exit_code == 0
    assert seen["doctor"] == ["--json"]

    # main() returns an int for both success and usage-error, rather than exiting.
    monkeypatch.setattr(click_cli, "_convert", lambda f, argv: 0)
    src = tmp_path / "in.md"
    src.write_text("# hi\n")
    assert click_cli.main(["docx", str(src)]) == 0
    assert click_cli.main(["docx", "/no/such/file.md"]) != 0
