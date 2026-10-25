"""The command line itself: one surface, built with click.

Until 3.10.0 md2star shipped two parsers — an argparse CLI (``md2star`` /
``md2docx`` …) and a click twin (``md2star-x``) that rebuilt an argv and handed
it back to the argparse engine to be re-parsed. Two parsers for one interface
meant two places to add a flag, and these are the five commands and nine
options that had only ever been added to one of them:

* commands: ``audit``, ``cache-dir``, ``clear-cache``, ``templates list``,
  ``templates path`` — absent from the click side entirely;
* options: ``--allow-remote-templates`` and ``--no-lint`` on docx/pdf, plus
  ``--eyeball-iterations``, ``--no-visual-confirm``, ``--reference-slides``,
  ``--smart-layout`` and ``--template`` on pptx.

So most of what is pinned here is **parity**, not plumbing. The engine is
mocked where the subject is the parsing; the Pandoc passthrough is checked
against a real pandoc because that is the behaviour md2star exists for and the
one click does not give for free.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path

import pytest

from md2star import cli
from md2star.pipeline import ConvertOptions

needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not on PATH")


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A minimal Markdown file with two headings, so --toc has work to do."""
    src = tmp_path / "in.md"
    src.write_text("# Un\n\nDu texte.\n\n# Deux\n\nEncore.\n", encoding="utf-8")
    return src


@pytest.fixture
def spy(monkeypatch) -> list[tuple[str, ConvertOptions, list[str]]]:
    """Capture what the CLI hands the engine, without converting anything."""
    calls: list[tuple[str, ConvertOptions, list[str]]] = []

    def _record(fmt: str, opts: ConvertOptions, pandoc_args=()) -> int:
        calls.append((fmt, opts, list(pandoc_args)))
        return 0

    # Patched where cli.py looks it up: the module imports the name directly.
    monkeypatch.setattr(cli, "convert", _record)
    return calls


# ── the passthrough ──────────────────────────────────────────────────────────


class TestPandocPassthrough:
    """Unknown flags are Pandoc's. This is the whole point of the tool."""

    def test_an_unknown_flag_is_separated_from_the_input(self, spy, source: Path) -> None:
        """The input is found; the flag md2star never heard of is forwarded."""
        assert cli.main(["docx", str(source), "--toc", "--metadata=subject:X"]) == 0
        fmt, opts, pandoc_args = spy[0]
        assert fmt == "docx"
        assert opts.input == str(source)
        assert pandoc_args == ["--toc", "--metadata=subject:X"]

    def test_a_flag_before_the_input_still_works(self, spy, source: Path) -> None:
        """argparse's `parse_known_args` tolerated this order; click must too.

        click's own `ignore_unknown_options` does not: an unknown option lands
        in the leftover args in place, so the positional would have bound to
        `--toc`. `_split_input` is what keeps the two orders equivalent.
        """
        assert cli.main(["docx", "--toc", str(source)]) == 0
        _, opts, pandoc_args = spy[0]
        assert opts.input == str(source)
        assert pandoc_args == ["--toc"]

    def test_the_order_of_forwarded_flags_is_preserved(self, spy, source: Path) -> None:
        """Pandoc's last value wins, so the order is load-bearing, not cosmetic."""
        assert cli.main(["pdf", "--toc", str(source), "-M", "a=1", "--wrap=none"]) == 0
        assert spy[0][2] == ["--toc", "-M", "a=1", "--wrap=none"]

    def test_input_only_options_is_a_usage_error(self) -> None:
        """Nothing filename-shaped at all is a usage error, not a crash."""
        assert cli.main(["docx", "--toc"]) == 2

    @needs_pandoc
    def test_a_forwarded_flag_really_reaches_pandoc(self, tmp_path: Path) -> None:
        """End to end, against a real pandoc, asserted on the output bytes.

        A mocked engine proves the CLI *collected* the flag; only the produced
        document proves pandoc *received* it. `--toc` makes pandoc emit a
        table-of-contents field, which the plain conversion does not have.
        """
        src = tmp_path / "doc.md"
        src.write_text("# Un\n\nTexte.\n\n# Deux\n\nTexte.\n", encoding="utf-8")

        plain, with_toc = tmp_path / "plain.docx", tmp_path / "toc.docx"
        assert cli.main(["docx", str(src), "-o", str(plain), "--offline"]) == 0
        assert cli.main(["docx", str(src), "-o", str(with_toc), "--offline", "--toc"]) == 0

        def _has_toc_field(path: Path) -> bool:
            body = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
            return "TOC" in body and "instrText" in body

        assert not _has_toc_field(plain), "the control document already had a TOC"
        assert _has_toc_field(with_toc), "--toc never reached pandoc"

    @needs_pandoc
    def test_pandoc_rejects_its_own_bad_flag_and_the_code_propagates(self, tmp_path: Path) -> None:
        """A flag nobody knows is pandoc's to refuse, and its exit code is ours."""
        src = tmp_path / "doc.md"
        src.write_text("# Un\n", encoding="utf-8")
        rc = cli.main(
            ["docx", str(src), "-o", str(tmp_path / "x.docx"), "--offline", "--not-a-flag"]
        )
        # Not 0 and not click's 2: this is pandoc's own "Unknown option" status,
        # which means md2star forwarded the flag instead of swallowing it.
        assert rc not in (0, 2)


# ── option parity across the three converters ────────────────────────────────


class TestSharedOptions:
    """Every md2star option reaches the engine as a typed field."""

    @pytest.mark.parametrize("fmt", ["docx", "pptx", "pdf"])
    def test_every_shared_option_is_accepted_and_forwarded(
        self, spy, tmp_path: Path, fmt: str
    ) -> None:
        """One invocation per format carrying the full shared option set.

        `--allow-remote-templates` and `--no-lint` are in here because docx and
        pdf did not have them on the click side at all; a run that spells them
        and gets a usage error is the regression this catches.
        """
        src = tmp_path / "in.md"
        src.write_text("# Hi\n", encoding="utf-8")
        bib = tmp_path / "refs.bib"
        bib.write_text("@book{k, title={T}}\n", encoding="utf-8")
        reference = tmp_path / "ref.docx"
        reference.write_bytes(b"PK\x03\x04stub")

        assert (
            cli.main(
                [
                    fmt,
                    str(src),
                    "-o",
                    str(tmp_path / f"out.{fmt}"),
                    "--author",
                    "Ada",
                    "--bib",
                    str(bib),
                    "--bibliography-name",
                    "Works",
                    "--lang",
                    "fr",
                    "--date",
                    "2026",
                    "--no-lint",
                    "--skip-phase",
                    "mermaid",
                    "--skip-phase",
                    "language",
                    "--reference-doc",
                    str(reference),
                    "--offline",
                    "--no-remote-templates",
                    "--allow-remote-templates",
                    "--allow-remote-images",
                    "--verbose",
                ]
            )
            == 0
        )
        _, opts, _pandoc = spy[0]
        assert opts.author == "Ada"
        assert opts.bib == str(bib)
        assert opts.bibliography_name == "Works"
        assert opts.lang == "fr" and opts.date == "2026"
        assert opts.lint is False
        # Repeatable, and in the order given — the engine skips phases by name.
        assert opts.skip_phase == ("mermaid", "language")
        assert opts.reference_doc == str(reference)
        assert opts.offline and opts.no_remote_templates and opts.allow_remote_images
        assert opts.verbose and not opts.quiet
        # The back-compat no-op must not leak into the engine's options.
        assert not hasattr(opts, "allow_remote_templates")

    def test_lint_defaults_off_and_turns_on(self, spy, source: Path) -> None:
        """Off by default is the contract: a conversion stays deterministic."""
        assert cli.main(["docx", str(source)]) == 0
        assert spy[0][1].lint is False
        assert cli.main(["docx", str(source), "--lint"]) == 0
        assert spy[1][1].lint is True

    def test_verbose_and_quiet_together_is_a_usage_error(self, spy, source: Path) -> None:
        """argparse used a mutually-exclusive group; click needs the check written."""
        assert cli.main(["docx", str(source), "-v", "-q"]) == 2
        assert spy == []

    def test_the_smart_layout_options_exist_on_pptx_only(self, spy, tmp_path: Path) -> None:
        """All five, and only on the format whose pipeline can honour them."""
        src = tmp_path / "deck.md"
        src.write_text("# Slide\n", encoding="utf-8")
        designer = tmp_path / "designer.pptx"
        designer.write_bytes(b"PK\x03\x04stub")

        assert (
            cli.main(
                [
                    "pptx",
                    str(src),
                    "--smart-layout",
                    "--template",
                    str(designer),
                    "--reference-slides",
                    "--no-visual-confirm",
                    "--eyeball-iterations",
                    "2",
                ]
            )
            == 0
        )
        _, opts, _pandoc = spy[0]
        assert opts.smart_layout and opts.reference_slides and opts.no_visual_confirm
        assert opts.template == str(designer) and opts.eyeball_iterations == 2

        # docx has no such path, so the flag is not quietly accepted and
        # ignored — it falls through to pandoc, which has no --smart-layout
        # either. The engine is mocked here, so only the routing is asserted.
        assert cli.main(["docx", str(src), "--smart-layout"]) == 0
        assert spy[1][2] == ["--smart-layout"]

    @pytest.mark.parametrize("fmt", ["docx", "pptx", "pdf"])
    def test_a_non_zero_engine_code_becomes_the_exit_code(
        self, monkeypatch, source: Path, fmt: str
    ) -> None:
        """Pandoc's and LibreOffice's failures must survive the click layer."""
        monkeypatch.setattr(cli, "convert", lambda *_a, **_k: 7)
        assert cli.main([fmt, str(source)]) == 7

    def test_a_missing_input_is_the_engines_typed_error(self, caplog) -> None:
        """Exit 2 with a hint, not click's bare "does not exist".

        Deliberately not `click.Path(exists=True)`: the engine's own
        InvalidInputError names the resolved path and says what md2star accepts,
        and `md2docx` has reported it that way since long before click.
        """
        caplog.set_level(logging.DEBUG, logger="md2star")
        assert cli.main(["docx", "/totally/not/here.md"]) == 2
        assert "input file not found" in caplog.text


# ── the commands the click side never had ────────────────────────────────────


class TestCommandParity:
    """The five commands that existed only on the argparse dispatcher."""

    def test_cache_dir_prints_the_resolved_path(self, capsys, isolated_cache) -> None:
        """Script-friendly: one path on stdout, exit 0."""
        assert cli.main(["cache-dir"]) == 0
        assert capsys.readouterr().out.strip() == str(isolated_cache)

    def test_clear_cache_reports_what_it_freed(self, capsys, isolated_cache) -> None:
        """And actually removes it — a report without the deletion is worse than none."""
        isolated_cache.mkdir(parents=True, exist_ok=True)
        (isolated_cache / "junk.bin").write_bytes(b"x" * 2048)
        assert cli.main(["clear-cache"]) == 0
        assert "cleared cache" in capsys.readouterr().out
        assert not (isolated_cache / "junk.bin").exists()

    def test_audit_is_reachable_and_returns_its_verdict(self, monkeypatch, tmp_path: Path) -> None:
        """`md2star audit deck.pptx [--json] [--strict]`, newly on the click side."""
        pytest.importorskip("pptx")
        from md2star import pptx_audit

        seen: dict[str, object] = {}

        def _fake(deck_path: str, *, as_json: bool = False, strict: bool = False) -> int:
            seen.update(deck=deck_path, as_json=as_json, strict=strict)
            return 1

        monkeypatch.setattr(pptx_audit, "run", _fake)
        deck = tmp_path / "deck.pptx"
        deck.write_bytes(b"PK\x03\x04stub")
        # Exit 1 is the documented "a defect was found" status, so it has to
        # come back out of click rather than being flattened to 0.
        assert cli.main(["audit", str(deck), "--json", "--strict"]) == 1
        assert seen == {"deck": str(deck), "as_json": True, "strict": True}

    def test_doctor_and_gui_delegate_their_parsed_flags(self, monkeypatch) -> None:
        """Both took an argv until 3.10.0; now they take arguments."""
        from md2star import doctor, gui_server

        seen: dict[str, object] = {}
        monkeypatch.setattr(
            doctor, "run", lambda *, as_json=False: seen.__setitem__("json", as_json) or 0
        )
        monkeypatch.setattr(gui_server, "serve", lambda **kw: seen.__setitem__("gui", kw) or 0)

        assert cli.main(["doctor", "--json"]) == 0
        assert seen["json"] is True
        assert cli.main(["gui", "--port", "9000", "--no-browser", "--bind", "0.0.0.0"]) == 0
        assert seen["gui"] == {"port": 9000, "no_browser": True, "bind": "0.0.0.0"}

    def test_twin_delegates_its_parsed_flags(self, monkeypatch, tmp_path: Path) -> None:
        """The reverse direction, with its own option set."""
        from md2star import twin_cli

        seen: dict[str, object] = {}

        def _fake(input_path: str, **kwargs: object) -> int:
            seen.update(input=input_path, **kwargs)
            return 0

        monkeypatch.setattr(twin_cli, "run", _fake)
        assert cli.main(["twin", "report.pdf", "--out", str(tmp_path), "--diagrams"]) == 0
        assert seen["input"] == "report.pdf"
        assert seen["out_dir"] == str(tmp_path)
        assert seen["diagrams"] is True and seen["no_images"] is False


# ── the surface itself ───────────────────────────────────────────────────────


class TestHelpAndVersion:
    def test_every_command_answers_to_dash_h(self) -> None:
        """`-h` as well as `--help`, on the group and on each subcommand."""
        assert cli.main(["-h"]) == 0
        for name in cli.cli.commands:
            assert cli.main([name, "-h"]) == 0, f"{name} has no -h"

    def test_the_version_is_the_packages_own(self, capsys) -> None:
        """Read from `__version__`, not from installed distribution metadata.

        An editable checkout would otherwise report whatever was last
        pip-installed.
        """
        from md2star import __version__

        for flag in ("-V", "--version"):
            assert cli.main([flag]) == 0
            assert capsys.readouterr().out.strip() == f"md2star {__version__}"

    def test_the_commands_are_listed_in_a_useful_order(self, capsys) -> None:
        """docx/pptx/pdf first. click sorts alphabetically unless told not to."""
        cli.main(["--help"])
        listing = capsys.readouterr().out.split("Commands:", 1)[1]
        order = [line.split()[0] for line in listing.splitlines() if line.startswith("  ")]
        assert order[:3] == ["docx", "pptx", "pdf"]

    def test_the_help_does_not_describe_a_second_front_end(self, capsys) -> None:
        """It said "click front-end … a modern alternative to the argparse CLI".

        There is one command line now, so help text promising a choice between
        two is a stale architecture note shipped to users.
        """
        cli.main(["--help"])
        text = capsys.readouterr().out.lower()
        assert "argparse" not in text and "md2star-x" not in text
        assert "front-end" not in text


class TestShorthandEntryPoints:
    """`md2docx` / `md2pptx` / `md2pdf` are the same commands, not copies."""

    @pytest.mark.parametrize(
        ("entry", "fmt"),
        [("md2docx_main", "docx"), ("md2pptx_main", "pptx"), ("md2pdf_main", "pdf")],
    )
    def test_each_shorthand_drives_its_format(self, spy, source: Path, entry, fmt) -> None:
        assert getattr(cli, entry)([str(source), "--toc"]) == 0
        seen_fmt, opts, pandoc_args = spy[0]
        assert seen_fmt == fmt and opts.input == str(source)
        # The passthrough works through the shorthand too, which is how most
        # people actually reach it.
        assert pandoc_args == ["--toc"]

    def test_they_are_the_groups_own_commands(self) -> None:
        """Identity, not equality: one object per format, two ways in.

        This is what makes "a flag can only be added once" true rather than
        merely intended — the two parsers before it drifted by nine options.
        """
        for fmt in ("docx", "pptx", "pdf"):
            assert cli.cli.commands[fmt] is cli._CONVERTERS[fmt]

    def test_the_pptx_only_options_are_absent_from_the_others(self) -> None:
        """A promise the docx pipeline cannot keep is better left unmade."""
        for fmt in ("docx", "pdf"):
            names = {opt for param in cli._CONVERTERS[fmt].params for opt in param.opts}
            assert "--smart-layout" not in names and "--template" not in names
        pptx_names = {opt for param in cli._CONVERTERS["pptx"].params for opt in param.opts}
        assert {"--smart-layout", "--template", "--reference-slides"} <= pptx_names
