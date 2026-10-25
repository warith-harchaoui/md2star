#!/usr/bin/env python3
"""Comment-density auditor for md2star (house coding-standard rule 4).

Module summary
--------------
Rule 4 of the project's coding standard asks for a *comment density* — the
ratio of in-code comment lines to code lines — of roughly 25-30 %, with a
hard floor of 15 % (≈ one comment per six code lines). This script measures
that ratio per file and fails (non-zero exit) when any non-glue source file
sits below the floor, so it can gate a pre-commit hook or a CI job.

Why a bespoke script instead of ``cloc``: ``cloc`` counts a Python triple-
quoted docstring as a comment. That inflates the number and hides files that
are fully docstringed yet have zero in-body narration — exactly the case rule
4 targets. We therefore exclude docstrings using the :mod:`ast` module and
count only ``#`` comments via :mod:`tokenize`.

Usage example
-------------
>>> # Audit the package, failing below the 15 % floor:
>>> #   python scripts/audit_comments.py md2star
>>> # Advisory run against the 25 % target (never fails the build):
>>> #   python scripts/audit_comments.py --advisory md2star

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

import click

# Rule-4 thresholds, expressed as comment_lines / code_lines. 0.25 is the
# "target" (~1 comment per 4 code lines); 0.15 is the hard floor below which a
# file is treated like one with missing tests.
TARGET: float = 0.25
FLOOR: float = 0.15

# Glue files are explicitly allowed below the floor by rule 4 (they still need
# a module docstring, checked separately). We match by file *name* so the rule
# applies at any depth in the tree.
#
# ``gui.py`` is a static-asset module: its body is a single triple-quoted HTML
# string served verbatim at ``GET /gui`` (the house-standard minimal bench,
# mirroring ``audio_helper/gui.py``). The naive line counter treats each HTML
# line as "code", so the *Python* comment ratio is meaningless here — the HTML
# carries its own ``<!-- … -->`` comments and the module docstring explains the
# whole file. It is glue, not logic.
_GLUE_NAMES: frozenset[str] = frozenset({"__init__.py", "__main__.py", "gui.py"})


def _docstring_line_numbers(src: str) -> set[int]:
    """Return every physical line number occupied by a docstring in *src*.

    Parameters
    ----------
    src : str
        Full source text of a Python module.

    Returns
    -------
    set[int]
        1-based line numbers that belong to a module/class/function docstring.
        These are excluded from the density ratio (see the module docstring).
    """
    lines: set[int] = set()
    tree = ast.parse(src)
    # Only these node types can legally carry a docstring as their first stmt.
    doc_nodes = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, doc_nodes):
            continue
        # A docstring is a bare string-constant expression opening the body.
        body = getattr(node, "body", [])
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            const = first.value
            # Mark the whole span the literal covers (it may be multi-line).
            for ln in range(const.lineno, (const.end_lineno or const.lineno) + 1):
                lines.add(ln)
    return lines


def analyze(path: Path) -> dict[str, object]:
    """Compute comment-density statistics for a single file.

    Parameters
    ----------
    path : Path
        Path to a ``.py`` file.

    Returns
    -------
    dict[str, object]
        Keys: ``file`` (str), ``code`` (int), ``comments`` (int),
        ``density`` (float), ``glue`` (bool).
    """
    src = path.read_text(encoding="utf-8")
    doc_lines = _docstring_line_numbers(src)

    # Collect the physical lines that carry a '#' comment. tokenize is the
    # reliable way to do this — a naive '#' search would trip on '#' inside
    # string literals.
    comment_line_nums: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            comment_line_nums.add(tok.start[0])

    # Count code lines: any non-blank line that is neither a docstring line nor
    # a comment-only line. A line with a trailing '# ...' still counts as code.
    code_line_nums: set[int] = set()
    for i, raw in enumerate(src.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue  # blank
        if i in doc_lines:
            continue  # inside a docstring
        if i in comment_line_nums and stripped.startswith("#"):
            continue  # comment-only line
        code_line_nums.add(i)

    comments = len(comment_line_nums)
    code = len(code_line_nums)
    # Guard against div-by-zero for empty/degenerate files.
    density = comments / code if code else 0.0
    return {
        "file": str(path),
        "code": code,
        "comments": comments,
        "density": density,
        "glue": path.name in _GLUE_NAMES,
    }


def _iter_py_files(paths: list[str]) -> list[Path]:
    """Expand *paths* (files or directories) into a sorted list of ``.py`` files."""
    out: list[Path] = []
    for p in paths:
        root = Path(p)
        # Directories are walked recursively; a file is taken as-is.
        out.extend(root.rglob("*.py") if root.is_dir() else [root])
    return sorted(set(out))


# ``-h`` beside ``--help``, as everywhere else in md2star's command lines.
_CONTEXT: dict[str, object] = {"help_option_names": ["-h", "--help"]}


@click.command("audit_comments", context_settings=_CONTEXT)
@click.argument("paths", nargs=-1)
@click.option("--floor", type=float, default=FLOOR, help="Hard floor ratio.")
@click.option("--target", type=float, default=TARGET, help="Advisory target ratio.")
@click.option(
    "--advisory",
    is_flag=True,
    help="Report only; always exit 0 (use while ratcheting a codebase up).",
)
def cli(paths: tuple[str, ...], floor: float, target: float, advisory: bool) -> int:
    """md2star comment-density audit (rule 4).

    PATHS are the files or directories to audit; with none given, md2star/.

    \f

    Everything past the form feed is for readers of the source: click
    truncates --help there. The PATHS line above stands in for an argparse
    `help=` on the positional — click has no per-argument help, so the
    command description is the only place left to say what it accepts.

    Parameters
    ----------
    paths : tuple of str
        Files or directories to audit; empty means ``md2star``.
    floor : float
        Hard floor ratio; a non-glue file below it fails the audit.
    target : float
        Advisory target ratio; below it a file is reported, never failed.
    advisory : bool
        Report only, always exit 0.

    Returns
    -------
    int
        ``0`` when every non-glue file meets the floor (or in ``--advisory``
        mode); ``1`` when at least one non-glue file is below the floor.
    """
    rows = [analyze(p) for p in _iter_py_files(list(paths) or ["md2star"])]
    # Sort worst-first so the biggest offenders are easy to spot at the top.
    rows.sort(key=lambda r: r["density"])  # type: ignore[arg-type,return-value]

    below_floor: list[dict[str, object]] = []
    print(f"{'file':44} {'code':>5} {'cmt':>4} {'dens%':>6}  status")
    print("-" * 74)
    for r in rows:
        density = float(r["density"])
        # Glue files below the floor are allowed (rule 4) — flag but don't fail.
        if r["glue"] and density < floor:
            status = "glue-exempt"
        elif density < floor:
            status = "FLOOR-FAIL"
            below_floor.append(r)
        elif density < target:
            status = "below-target"
        else:
            status = "ok"
        print(f"{r['file']:44} {r['code']:>5} {r['comments']:>4} {density * 100:>5.1f}%  {status}")

    print("-" * 74)
    tot_code = sum(int(r["code"]) for r in rows) or 1
    tot_cmt = sum(int(r["comments"]) for r in rows)
    print(f"{'TOTAL':44} {tot_code:>5} {tot_cmt:>4} {tot_cmt / tot_code * 100:>5.1f}%")

    # Gate: fail only on floor violations, and only outside advisory mode.
    if below_floor and not advisory:
        print(f"\n{len(below_floor)} file(s) below the {floor:.0%} floor — see rule 4.")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return its exit code instead of exiting.

    ``standalone_mode=False`` keeps the ``main(argv) -> int`` contract: this
    script gates a CI job through the ``__main__`` guard below, and a caller
    importing it gets a code rather than a :class:`SystemExit`.

    Parameters
    ----------
    argv : list[str] | None
        Argument vector (defaults to ``sys.argv[1:]``).

    Returns
    -------
    int
        :func:`cli`'s code, or click's own (2) for a usage error.
    """
    try:
        return int(cli.main(args=argv, prog_name="audit_comments", standalone_mode=False) or 0)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
