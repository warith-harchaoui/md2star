"""Tests for the comment-density auditor (``scripts/audit_comments.py``).

The auditor gates rule 4 in CI, so its measurement must be correct: it has to
count ``#`` comments, ignore docstrings, and ignore comments that live inside
string literals. These tests pin exactly those behaviours on synthetic inputs.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# The auditor lives under scripts/ (not in the installed package), so load it
# by path rather than a normal import.
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_comments.py"
_spec = importlib.util.spec_from_file_location("audit_comments", _SCRIPT)
assert _spec and _spec.loader
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def _write(tmp_path: Path, body: str) -> Path:
    """Write *body* to a temp .py file and return its path."""
    p = tmp_path / "sample.py"
    p.write_text(body, encoding="utf-8")
    return p


def test_counting_is_correct_across_edge_cases(tmp_path: Path) -> None:
    """The auditor counts ``#`` comments while ignoring docstrings and strings.

    Three measurement contracts in one pass: plain comment/code density; a
    module docstring counting as neither (rule 4); and a ``#`` inside a string
    literal not being miscounted (tokenize, not a naive scan).
    """
    # 2 comment lines, 2 code lines → density 1.0.
    plain = audit.analyze(_write(tmp_path, "# c1\nx = 1\n# c2\ny = 2\n"))
    assert plain["comments"] == 2 and plain["code"] == 2 and plain["density"] == 1.0

    # A triple-quoted module docstring inflates neither count.
    doc = audit.analyze(_write(tmp_path, '"""Module.\n\nMore.\n"""\n# note\nz = 3\n'))
    assert doc["comments"] == 1 and doc["code"] == 1

    # A '#' inside a string literal is not a comment.
    instr = audit.analyze(_write(tmp_path, 's = "not # a comment"\n'))
    assert instr["comments"] == 0 and instr["code"] == 1


def test_glue_flag_by_name(tmp_path: Path) -> None:
    """__init__.py / __main__.py are flagged as glue (floor-exempt)."""
    init = tmp_path / "__init__.py"
    init.write_text("x = 1\n", encoding="utf-8")
    assert audit.analyze(init)["glue"] is True
    # A normal module is not glue.
    assert audit.analyze(_write(tmp_path, "x = 1\n"))["glue"] is False
