"""Unit tests for the ``md2star templates {list,path}`` subcommand.

Covers the resolution-order mirror in :mod:`md2star.templates`:
the diagnostic command must report the same priority that the
conversion path uses, otherwise the "why is my branding ignored?"
debugging it's meant to short-circuit just becomes more confusing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from md2star import templates as tpl


# ──────────────────────────────────────────────────────────────────
# Candidate enumeration


def test_candidates_priority_order(tmp_path: Path) -> None:
    """The candidate list mirrors `_resolve_reference_doc`'s order."""
    cands = tpl._candidates(tmp_path, "docx")
    labels = [label for label, _ in cands]
    assert labels == [
        "per-project (template)",
        "per-project (legacy)",
        "cached",
        "bundled",
    ]


def test_first_existing_picks_bundled_when_nothing_local(tmp_path: Path) -> None:
    """With an empty input dir, only the bundled template exists."""
    winner = tpl._first_existing(tpl._candidates(tmp_path, "docx"))
    assert winner is not None
    label, path = winner
    assert label == "bundled"
    assert path.exists()
    assert path.suffix == ".docx"


def test_first_existing_picks_per_project_when_present(tmp_path: Path) -> None:
    """A local ``template.docx`` overrides every later candidate."""
    local = tmp_path / "template.docx"
    local.write_bytes(b"PK\x03\x04minimal-zip-bytes")

    winner = tpl._first_existing(tpl._candidates(tmp_path, "docx"))
    assert winner is not None
    label, path = winner
    assert label == "per-project (template)"
    assert path == local


# ──────────────────────────────────────────────────────────────────
# `templates list` — table output


def test_list_emits_both_formats(capsys, tmp_path: Path) -> None:
    """The list output must include a [docx] AND a [pptx] block."""
    rc = tpl.main(["list", "--dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[docx]" in out
    assert "[pptx]" in out
    # Bundled is the winner from an empty input dir.
    assert out.count("→  bundled") == 2


def test_list_marks_per_project_winner(capsys, tmp_path: Path) -> None:
    """When a local template.docx exists, it is marked as the winner."""
    (tmp_path / "template.docx").write_bytes(b"PK\x03\x04stub")

    rc = tpl.main(["list", "--dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    # The docx winner is now per-project, the pptx winner is still bundled.
    assert re.search(r"→\s+per-project \(template\)\s+\S+template\.docx", out)
    assert "→  bundled" in out


# ──────────────────────────────────────────────────────────────────
# `templates path` — one-line resolved path output


def test_path_returns_bundled_with_empty_dir(capsys, tmp_path: Path, monkeypatch) -> None:
    """An empty CWD resolves to the bundled template."""
    monkeypatch.chdir(tmp_path)
    rc = tpl.main(["path", "--fmt", "docx"])
    assert rc == 0
    line = capsys.readouterr().out.strip()
    assert line.endswith("template.docx")
    assert Path(line).exists()


def test_path_returns_per_project_when_present(capsys, tmp_path: Path) -> None:
    """An input file in a dir with template.pptx resolves to it."""
    local = tmp_path / "template.pptx"
    local.write_bytes(b"PK\x03\x04stub")
    src = tmp_path / "deck.md"
    src.write_text("# Hi\n")

    rc = tpl.main(["path", "--fmt", "pptx", str(src)])
    assert rc == 0
    line = capsys.readouterr().out.strip()
    assert line == str(local.resolve())


def test_path_explicit_fmt_default_docx(capsys, tmp_path: Path, monkeypatch) -> None:
    """`md2star templates path` without --fmt defaults to docx."""
    monkeypatch.chdir(tmp_path)
    rc = tpl.main(["path"])
    assert rc == 0
    assert capsys.readouterr().out.strip().endswith("template.docx")


# ──────────────────────────────────────────────────────────────────
# Top-level CLI plumbing


def test_cli_dispatches_templates_subcommand(capsys) -> None:
    """`md2star templates list` reaches templates.main via cli.main."""
    from md2star.cli import main as cli_main

    rc = cli_main(["templates", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[docx]" in out and "[pptx]" in out
