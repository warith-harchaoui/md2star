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


def test_counts_comments_over_code(tmp_path: Path) -> None:
    """Density is comment_lines / code_lines for a simple module."""
    # 2 comment lines, 2 code lines → density 1.0.
    src = "# c1\nx = 1\n# c2\ny = 2\n"
    stats = audit.analyze(_write(tmp_path, src))
    assert stats["comments"] == 2
    assert stats["code"] == 2
    assert stats["density"] == 1.0


def test_docstrings_are_excluded(tmp_path: Path) -> None:
    """A module docstring counts as neither comment nor code (rule 4)."""
    # The triple-quoted module docstring spans 3 lines but must not inflate the
    # comment count — only the '# note' line and 'z = 3' count.
    src = '"""Module.\n\nMore.\n"""\n# note\nz = 3\n'
    stats = audit.analyze(_write(tmp_path, src))
    assert stats["comments"] == 1
    assert stats["code"] == 1


def test_hash_inside_string_is_not_a_comment(tmp_path: Path) -> None:
    """A '#' inside a string literal must not be miscounted as a comment."""
    # tokenize (not a naive '#' scan) is why this works.
    src = 's = "not # a comment"\n'
    stats = audit.analyze(_write(tmp_path, src))
    assert stats["comments"] == 0
    assert stats["code"] == 1


def test_glue_flag_by_name(tmp_path: Path) -> None:
    """__init__.py / __main__.py are flagged as glue (floor-exempt)."""
    init = tmp_path / "__init__.py"
    init.write_text("x = 1\n", encoding="utf-8")
    assert audit.analyze(init)["glue"] is True
    # A normal module is not glue.
    assert audit.analyze(_write(tmp_path, "x = 1\n"))["glue"] is False
