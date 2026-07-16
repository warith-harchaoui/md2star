"""``md2star templates {list,path}`` — inspect bundled / cached / per-project templates.

Module summary
--------------
A diagnostic CLI verb that mirrors the resolution order of
``md2star.cli._resolve_reference_doc`` without actually converting
anything. Two sub-verbs:

* ``md2star templates list`` — prints a table of every template
  resolution candidate (per-project / cached / bundled) and
  whether it exists. Distinguishes ``docx`` from ``pptx`` rows so
  you can see at a glance which format is missing its template.

* ``md2star templates path [--fmt {docx,pptx}] [INPUT]`` — prints
  the absolute filesystem path of the template that md2star WOULD
  use for the given input (default: current directory + ``docx``).
  One line, parseable by shell scripts.

The motivation is the recurring "why isn't my branding applied?"
debug loop. Before this command, users had to read the
``_resolve_reference_doc`` docstring and re-derive the priority
order in their head. Now they ``md2star templates path file.md``
and md2star tells them.

Usage
-----
>>> # From the shell:
>>> #   md2star templates list
>>> #   md2star templates path report.md --fmt docx
>>> # gives you the per-format resolution table and the resolved
>>> # path that `md2docx report.md` would pick up.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .cache import cache_dir
from .logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Candidate enumeration — mirrors `_resolve_reference_doc` priority
# ─────────────────────────────────────────────────────────────────────


def _bundled_template_path(fmt: str) -> Path:
    """Return the absolute path to the bundled ``template.<fmt>``.

    Duplicates :func:`md2star.cli._bundled_template` so this module
    does not have to import from :mod:`md2star.cli` (which would
    pull in argparse + every preprocessor phase just to print a
    table).
    """
    from importlib import resources
    # joinpath one component at a time: Python 3.10's MultiplexedPath only
    # accepts a single arg per call, so the multi-arg form would break there.
    ref = resources.files("md2star.data")
    for part in (f"template.{fmt}",):
        ref = ref.joinpath(part)
    return Path(str(ref))


def _candidates(input_dir: Path, fmt: str) -> list[tuple[str, Path]]:
    """Return ``[(label, candidate_path), ...]`` in resolution order.

    Mirrors the resolution chain in :func:`md2star.cli._resolve_reference_doc`
    so the user-visible "which template wins" answer stays in sync
    with the actual conversion path.
    """
    # Highest priority first: a template committed next to the source, then the
    # legacy dotfile name, then the XDG cache, then the always-present bundled
    # copy. _first_existing() walks this list top-down to pick the winner.
    #
    # Note: between "cached" and "bundled" the real resolver
    # (`_resolve_reference_doc`) fetches https://deraison.ai/template.<fmt> by
    # default (v2.5.0+) and writes it into the "cached" slot. This diagnostic is
    # a filesystem-only view, so it cannot show that network step directly — it
    # surfaces as a populated "cached" row after the first online run.
    return [
        ("per-project (template)", input_dir / f"template.{fmt}"),
        ("per-project (legacy)",   input_dir / f".pandoc-reference.{fmt}"),
        ("cached",                 cache_dir("templates") / f"template.{fmt}"),
        ("bundled",                _bundled_template_path(fmt)),
    ]


def _first_existing(candidates: list[tuple[str, Path]]) -> tuple[str, Path] | None:
    """Return the first ``(label, path)`` whose path exists, or ``None``."""
    # Order is priority (see _candidates): the first hit is the active template.
    for label, path in candidates:
        if path.exists():
            return label, path
    return None


# ─────────────────────────────────────────────────────────────────────
# `md2star templates list` — table of every candidate
# ─────────────────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    """Print a per-format resolution table to stdout.

    Walks the same candidate chain as the conversion path, marks
    each existing file with ``✓``, marks the first existing one
    as the active winner with ``→``. No conversion, no network.
    """
    # Resolve relative to --dir if given, else the current directory — the same
    # anchor the real conversion uses for per-project templates.
    input_dir = Path(args.dir).expanduser().resolve() if args.dir else Path.cwd()

    # This is program OUTPUT (a report the user reads), so it goes to stdout via
    # print, not the logging surface.
    print(f"md2star templates — resolution from {input_dir}\n")
    for fmt in ("docx", "pptx"):
        print(f"  [{fmt}]")
        candidates = _candidates(input_dir, fmt)
        # The winner is the first existing candidate; mark it distinctly below.
        winner = _first_existing(candidates)
        winner_path = winner[1] if winner else None
        for label, path in candidates:
            # → active winner, ✓ present-but-shadowed, space = absent.
            mark = "→" if path == winner_path else ("✓" if path.exists() else " ")
            size_note = ""
            if path.exists():
                size = path.stat().st_size
                size_note = f"  ({size:,} bytes)"
            print(f"    {mark}  {label:<25}  {path}{size_note}")
        print()
    return 0


# ─────────────────────────────────────────────────────────────────────
# `md2star templates path` — script-friendly resolved path
# ─────────────────────────────────────────────────────────────────────


def cmd_path(args: argparse.Namespace) -> int:
    """Print the absolute path of the active template for ``fmt``.

    Useful for shell scripts that want to operate on the template
    md2star is currently using (e.g. opening it in Word for
    branding). Exits with code 2 + a stderr message if no template
    exists at any of the candidate locations (an install bug).
    """
    input_dir = (
        Path(args.input).expanduser().resolve().parent
        if args.input
        else Path.cwd()
    )

    winner = _first_existing(_candidates(input_dir, args.fmt))
    if winner is None:
        # No template anywhere is an install bug — diagnostic to stderr.
        logger.error(
            f"md2star: no template.{args.fmt} found at any candidate path "
            f"(per-project / cached / bundled). Reinstall md2star."
        )
        return 2

    # The resolved path itself is program OUTPUT (scripts capture it), so it
    # stays on stdout via print — not the logging surface.
    print(winner[1])
    return 0


# ─────────────────────────────────────────────────────────────────────
# Entry point — wired into `md2star.cli.main` as the `templates`
# subcommand dispatcher.
# ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Console entry point: ``md2star templates {list,path}``."""
    parser = argparse.ArgumentParser(
        prog="md2star templates",
        description=(
            "Inspect bundled / cached / per-project templates without "
            "running a conversion. Mirrors the resolution priority "
            "used by md2docx / md2pptx / md2pdf."
        ),
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    p_list = subparsers.add_parser(
        "list",
        help="Show every resolution candidate (per-project / cached / bundled).",
    )
    p_list.add_argument(
        "--dir",
        help=(
            "Treat this directory as the per-project root (i.e. the "
            "directory that would contain `template.docx`). Defaults "
            "to the current working directory."
        ),
    )

    p_path = subparsers.add_parser(
        "path",
        help="Print the absolute path of the active template for a given format.",
    )
    p_path.add_argument(
        "--fmt",
        choices=("docx", "pptx"),
        default="docx",
        help="Output format whose template to resolve (default: docx).",
    )
    p_path.add_argument(
        "input",
        nargs="?",
        help=(
            "Optional input markdown file — its containing directory "
            "becomes the per-project root. Without it, the current "
            "working directory is used."
        ),
    )

    args = parser.parse_args(argv)

    if args.action == "list":
        return cmd_list(args)
    if args.action == "path":
        return cmd_path(args)
    parser.error(f"unknown action: {args.action!r}")
    return 2  # pragma: no cover — argparse.error never returns


if __name__ == "__main__":
    sys.exit(main())
