"""Trigger-coverage checker for the md2star Claude / OpenCode skill.

Goal 6 of the project's agent-surface work asks that the skill's triggers be
*exhaustive and enforced*. A host model only ever sees the ``description:``
field of ``skills/md2star/SKILL.md`` before deciding whether to load the skill,
so that string — not the reference docs — is what must carry the triggers.

This script parses the YAML frontmatter of ``SKILL.md`` and asserts that the
``description`` mentions at least one token from every required trigger bucket
(each format, each wrapper command, branding, citations, diagrams, math, the
preview surfaces) *and* contains an explicit SKIP clause so the skill does not
over-fire. It is deliberately dependency-free (stdlib only) so it can run in the
same CI lane as ``audit_comments.py`` without installing anything.

Run it directly or via ``pytest tests/test_skill.py``::

    python scripts/check_triggers.py            # exit 0 = every bucket covered
    python scripts/check_triggers.py --list     # print the buckets and verdicts


Author
------
[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Resolve SKILL.md relative to the repo root (this script lives in scripts/),
# so the checker works regardless of the caller's current directory.
_SKILL_MD = Path(__file__).resolve().parent.parent / "skills" / "md2star" / "SKILL.md"

# Each bucket is (human label, [accepted lowercase tokens]). Coverage means the
# description contains ANY token in the bucket — synonyms are alternatives, not
# all-required — so paraphrases still count while every capability stays named.
_REQUIRED_BUCKETS: list[tuple[str, list[str]]] = [
    ("DOCX / Word", ["docx", "word"]),
    ("PPTX / PowerPoint", ["pptx", "powerpoint", "slides", "deck"]),
    ("PDF", ["pdf"]),
    ("wrapper commands", ["md2docx", "md2pptx", "md2pdf"]),
    ("branding / templates", ["template", "reference-doc", "branded", "corporate"]),
    ("citations / bibliography", ["bibtex", "citation", "citeproc", ".bib"]),
    ("diagrams", ["mermaid"]),
    ("math", ["math", "latex"]),
    ("preview / GUI", ["gui", "overleaf", "preview", "editor"]),
    ("install / doctor", ["install", "doctor", "md2star"]),
]

# A negative-trigger clause is mandatory: without a documented SKIP the skill
# over-fires on extraction / raw-pandoc / website requests.
_SKIP_MARKERS = ["skip when", "do not fire", "skip:"]


def _extract_description(text: str) -> str:
    """Return the ``description:`` value from a SKILL.md YAML frontmatter block.

    Parameters
    ----------
    text : str
        Full contents of ``SKILL.md``.

    Returns
    -------
    str
        The description text, lowercased and whitespace-collapsed. Empty string
        if no frontmatter / description was found (treated as a failure upstream).
    """
    # Grab the first ``--- ... ---`` frontmatter block. DOTALL so the block can
    # span many lines; non-greedy so we stop at the first closing fence.
    fm = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not fm:
        return ""
    block = fm.group(1)

    # Match ``description:`` and everything up to the next top-level YAML key
    # (a line starting with a non-space, non-dash character). This tolerates the
    # ``>-`` folded-scalar style used in SKILL.md, where the value is indented.
    desc = re.search(
        r"^description:\s*(.*?)(?=\n[A-Za-z_][\w-]*:\s|\Z)",
        block,
        re.DOTALL | re.MULTILINE,
    )
    if not desc:
        return ""
    # Collapse the folded scalar into one lowercase line for token matching.
    return re.sub(r"\s+", " ", desc.group(1)).strip().lower()


def check(verbose: bool = False) -> list[str]:
    """Return the list of coverage failures (empty list = fully enforced).

    Parameters
    ----------
    verbose : bool, optional
        When True, print every bucket with a ✓/✗ verdict to stdout.

    Returns
    -------
    list of str
        One human-readable message per uncovered bucket or missing SKIP clause.
    """
    if not _SKILL_MD.exists():
        return [f"SKILL.md not found at {_SKILL_MD}"]

    description = _extract_description(_SKILL_MD.read_text(encoding="utf-8"))
    if not description:
        return ["could not parse a `description:` field from SKILL.md frontmatter"]

    failures: list[str] = []
    # Every capability bucket must be represented by at least one token.
    for label, tokens in _REQUIRED_BUCKETS:
        hit = any(tok in description for tok in tokens)
        if verbose:
            print(f"  {'✓' if hit else '✗'} {label}: {tokens}")
        if not hit:
            failures.append(f"trigger bucket not covered in description: {label} ({tokens})")

    # The SKIP clause guards against over-firing; its absence is a failure.
    has_skip = any(marker in description for marker in _SKIP_MARKERS)
    if verbose:
        print(f"  {'✓' if has_skip else '✗'} SKIP clause present")
    if not has_skip:
        failures.append("no SKIP / negative-trigger clause found in description")

    return failures


def main(argv: list[str] | None = None) -> int:
    """Console entry point. Exit 0 when every bucket is covered, 1 otherwise."""
    args = argv if argv is not None else sys.argv[1:]
    verbose = "--list" in args

    failures = check(verbose=verbose)
    if failures:
        # Surface every gap at once so a maintainer fixes them in one pass.
        print("md2star skill triggers INCOMPLETE:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("md2star skill triggers: all buckets covered + SKIP clause present ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
