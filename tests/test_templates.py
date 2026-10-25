"""Unit tests for the ``md2star templates {list,path}`` subcommand.

Covers the resolution-order mirror in :mod:`md2star.templates`: the
diagnostic command must report the same priority that the conversion
path uses, otherwise the "why is my branding ignored?" debugging it's
meant to short-circuit just becomes more confusing.

The suite is organised by behaviour:

* :class:`TestResolution` pins the candidate priority order and the
  first-existing winner (bundled fallback vs. local override) — the
  regression heart of the module.
* :class:`TestCli` exercises the two subcommands end to end: ``list``
  (both formats, winner marking) and ``path`` (fmt handling, bundled
  vs. per-project), plus the top-level CLI dispatch.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import re
from pathlib import Path

from md2star import templates as tpl

# ──────────────────────────────────────────────────────────────────
# Candidate resolution — the regression heart of the module


class TestResolution:
    """``_candidates`` / ``_first_existing`` mirror ``_resolve_reference_doc``."""

    def test_candidates_priority_order(self, tmp_path: Path) -> None:
        """The candidate list mirrors ``_resolve_reference_doc``'s order.

        Parameters
        ----------
        tmp_path : pathlib.Path
            Stand-in input directory for candidate enumeration.
        """
        cands = tpl._candidates(tmp_path, "docx")
        labels = [label for label, _ in cands]
        # Local overrides beat the cache, which beats the bundled fallback.
        assert labels == [
            "per-project (template)",
            "per-project (legacy)",
            "cached",
            "bundled",
        ]

    def test_first_existing_prefers_local_over_bundled(self, tmp_path: Path) -> None:
        """Bundled wins on an empty dir; a local ``template.docx`` overrides it.

        Parameters
        ----------
        tmp_path : pathlib.Path
            Input directory, first empty then seeded with a local template.
        """
        # With nothing local, only the bundled template exists.
        winner = tpl._first_existing(tpl._candidates(tmp_path, "docx"))
        assert winner is not None
        label, path = winner
        assert label == "bundled"
        assert path.exists()
        assert path.suffix == ".docx"

        # Drop a local template.docx: it must now win over every later candidate.
        local = tmp_path / "template.docx"
        local.write_bytes(b"PK\x03\x04minimal-zip-bytes")
        label, path = tpl._first_existing(tpl._candidates(tmp_path, "docx"))
        assert label == "per-project (template)"
        assert path == local


# ──────────────────────────────────────────────────────────────────
# CLI surface — `templates list` / `templates path` / top-level dispatch


class TestCli:
    """The two command bodies, plus the click wiring that reaches them."""

    def test_list_emits_both_formats_and_marks_winner(self, capsys, tmp_path: Path) -> None:
        """``list`` shows a [docx] + [pptx] block; a local template wins docx.

        Parameters
        ----------
        capsys : pytest.CaptureFixture
            Captures the table output.
        tmp_path : pathlib.Path
            Input dir seeded with a local ``template.docx``.
        """
        # A local docx template so the docx winner flips to per-project while
        # pptx (no local file) stays bundled — one run covers both cases.
        (tmp_path / "template.docx").write_bytes(b"PK\x03\x04stub")

        rc = tpl.cmd_list(str(tmp_path))
        assert rc == 0
        out = capsys.readouterr().out
        # Both formats are listed.
        assert "[docx]" in out
        assert "[pptx]" in out
        # docx resolves to the local template; pptx falls back to bundled.
        assert re.search(r"→\s+per-project \(template\)\s+\S+template\.docx", out)
        assert "→  bundled" in out

    def test_path_resolves_expected_template(self, capsys, tmp_path: Path, monkeypatch) -> None:
        """``path`` prints the resolved template for the format + environment.

        Sweeps default/explicit fmt, bundled fallback vs. local override, and
        CWD- vs. source-file-relative resolution. Each case is
        (fmt or None for the default, local-template filename or None, use_src,
        expected suffix).
        """
        cases = [
            (None, None, False, "template.docx"),  # default fmt = docx
            ("docx", None, False, "template.docx"),  # explicit docx
            ("pptx", "template.pptx", False, "template.pptx"),  # local CWD override
            ("pptx", "template.pptx", True, "template.pptx"),  # source-dir keying
        ]
        for i, (fmt, seed_local, use_src, expected_suffix) in enumerate(cases):
            # A fresh sub-CWD per case so seeded local templates don't leak across.
            work = tmp_path / f"case{i}"
            work.mkdir()
            monkeypatch.chdir(work)
            if seed_local is not None:
                # Seed a per-project template so resolution has a local winner.
                (work / seed_local).write_bytes(b"PK\x03\x04stub")
            source = None
            if use_src:
                # A source file next to the template exercises source-dir keying.
                src = work / "deck.md"
                src.write_text("# Hi\n")
                source = str(src)

            # `None` for fmt means "call it the way the command's default
            # does", which is the case worth covering separately.
            rc = tpl.cmd_path(source=source) if fmt is None else tpl.cmd_path(fmt, source)
            assert rc == 0
            line = capsys.readouterr().out.strip()
            # Ends in the expected template and points at a real file (bundled
            # fallback) or the seeded local override.
            assert line.endswith(expected_suffix)
            if seed_local is None:
                assert Path(line).exists()
            else:
                assert line == str((work / seed_local).resolve())

    def test_cli_dispatches_templates_subcommands(self, capsys, tmp_path: Path) -> None:
        """Both ``templates`` verbs are reachable through the real command line.

        They were reachable only through the argparse dispatcher until 3.10.0 —
        the click front-end had no ``templates`` command at all, so this is the
        wiring that was missing rather than merely moved.

        Parameters
        ----------
        capsys : pytest.CaptureFixture
            Captures the dispatched subcommand's output.
        tmp_path : pathlib.Path
            A directory to resolve ``--dir`` against.
        """
        from md2star.cli import main as cli_main

        assert cli_main(["templates", "list", "--dir", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        # The subcommand ran and produced its two-format table.
        assert "[docx]" in out and "[pptx]" in out

        assert cli_main(["templates", "path", "--fmt", "pptx"]) == 0
        assert capsys.readouterr().out.strip().endswith("template.pptx")
