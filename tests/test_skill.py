"""Tests for the md2star Claude / OpenCode skill packaging.

Goals 5 and 6 require md2star to ship as a well-formed skill with exhaustive,
enforced triggers. These tests assert the SKILL.md exists, has the required
frontmatter, and that ``scripts/check_triggers.py`` reports full trigger-bucket
coverage — so a thin or drifted description fails CI, not production.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SKILL = _REPO / "skills" / "md2star" / "SKILL.md"


def _load_checker():
    """Import scripts/check_triggers.py (not an installed module) by path."""
    spec = importlib.util.spec_from_file_location(
        "check_triggers", _REPO / "scripts" / "check_triggers.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_skill_md_exists_and_has_frontmatter() -> None:
    """SKILL.md exists with name + description frontmatter and references."""
    assert _SKILL.exists(), "skills/md2star/SKILL.md is missing"
    text = _SKILL.read_text(encoding="utf-8")
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    assert "\nname: md2star" in text
    assert "description:" in text
    # Progressive-disclosure reference files the body points to.
    for ref in ("cli-reference.md", "surfaces.md", "triggers.md"):
        assert (_SKILL.parent / "references" / ref).exists(), f"missing reference: {ref}"


def test_triggers_fully_covered() -> None:
    """The trigger checker reports zero uncovered buckets (goal 6 enforced)."""
    checker = _load_checker()
    failures = checker.check()
    assert failures == [], f"trigger coverage gaps: {failures}"
