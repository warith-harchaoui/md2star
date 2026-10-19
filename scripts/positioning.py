#!/usr/bin/env python3
"""Rebuild the LANDSCAPE / PAYSAGE positioning maps from their CSV tables.

`assets/landscape.csv` and `assets/paysage.csv` hold the same ratings as the
star tables in `LANDSCAPE.md` / `PAYSAGE.md` (kept in step by
`tests/test_landscape.py`). This script turns them into the two committed
figures with [standpoint](https://github.com/warith-harchaoui/standpoint), the
sibling tool that does the correlation PCA and draws the quadrant.

**Why not just call the `standpoint` CLI?** Because that names the four poles
with a local model, and a comparison document maintained by hand over years
needs its axes to mean the same thing from one release to the next. The
geometry is deterministic either way; only the labels would wander. So the
poles live here, as a constant, chosen to match the loadings they summarise —
and a regeneration after a ratings edit moves the dots without renaming the
map. Everything the model would have been asked for is supplied below, so this
script needs **no Ollama and no network at all**.

Usage
-----
``standpoint`` installs as its own tool, so run this with its interpreter::

    ~/.local/pipx/venvs/standpoint/bin/python scripts/positioning.py

Add ``--keep-svg`` to also keep the interactive SVG companions, which the
repository does not track. Re-read the poles below whenever a criterion is
added or removed: the names are only honest as long as they still describe
what loads on each axis (the YAML the tool writes lists those loadings).

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import argparse
import os
import sys

#: One entry per committed figure: the CSV it reads, the stem it writes, and
#: the four pole labels in standpoint's own order (left, right, bottom, top).
#:
#: The poles are two readings of the same geometry, one per language, because
#: both maps are drawn from the same ratings. Horizontally, the negative side
#: loads on maths and citations and the positive side on template fit, the
#: self-check, branding and Office output: scholarship against design.
#: Vertically, every loading is positive, highest for the reverse path, working
#: offline, the one-command CLI and citations, and near zero for template fit
#: and branding: a complete toolchain against a purely visual one.
FIGURES: dict[str, dict[str, object]] = {
    "landscape": {
        "csv": "assets/landscape.csv",
        "poles": ["Scholarly", "Designed", "Visual", "Comprehensive"],
        "noun": ("Markdown conversion", "Markdown conversions"),
        "lang": "en",
    },
    "paysage": {
        "csv": "assets/paysage.csv",
        "poles": ["Académique", "Design", "Visuel", "Complet"],
        "noun": ("Conversion Markdown", "Conversions Markdown"),
        "lang": "fr",
    },
}

#: The row that must land top-right. Named rather than positional so reordering
#: the table cannot silently re-anchor the map on somebody else's tool.
REFERENCE = "md2star"


def build(stem: str, spec: dict, outdir: str, *, keep_svg: bool) -> list[str]:
    """Draw one positioning map and write it to *outdir*.

    Parameters
    ----------
    stem : str
        Basename of the output files, e.g. ``"landscape"``.
    spec : dict
        One :data:`FIGURES` entry: its CSV, poles, noun forms and language.
    outdir : str
        Directory to write into; created if missing.
    keep_svg : bool
        Keep every companion standpoint writes beside the figure — the
        interactive SVG, and the white-background pair meant for dark
        surfaces. The repository tracks only ``<stem>.png``, so an untracked
        file left in ``assets/`` is litter; they are deleted by default.

    Returns
    -------
    list of str
        The paths actually kept, in the order written.
    """
    import standpoint as sp

    left, right, bottom, top = spec["poles"]
    singular, plural = spec["noun"]

    # Deterministic half of standpoint's own pipeline, in its own order: parse,
    # resolve which criteria are lower-is-better, PCA, then roles and colours.
    frame = sp.parse_table(spec["csv"])
    frame, lower = sp.resolve_polarity(frame, None)
    result = sp.analyze(frame, reference=REFERENCE, lower_is_better=list(lower))
    roles = sp.assign_roles(result)

    positioning = sp.Positioning(
        frame,
        result,
        roles,
        [left, right, bottom, top],
        [f"{left} ↔ {right}", f"{bottom} ↔ {top}"],
        sp.gradient_colors(result, roles),
        singular,
        plural,
        # The localized figure title, from standpoint's own template, so the
        # French map reads "… dans le quadrant" and not the English phrasing.
        sp.i18n(spec["lang"])["title_template"].format(plural=plural),
    )

    os.makedirs(outdir, exist_ok=True)
    target = os.path.join(outdir, stem)
    written = positioning.figure(target)
    if keep_svg:
        return written
    # figure() writes a transparent and a white PNG/SVG pair; the documents
    # embed the transparent PNG and nothing else.
    kept = []
    for path in written:
        if path == f"{target}.png":
            kept.append(path)
        else:
            os.remove(path)
    return kept


def main(argv: list[str] | None = None) -> int:
    """Rebuild every figure named on the command line (default: all of them)."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # No `choices=` with `nargs="*"`: argparse validates the default list
    # against them too, and a list is never one of its own elements.
    parser.add_argument(
        "figures", nargs="*", help=f"which to rebuild (default: all of {{{', '.join(FIGURES)}}})"
    )
    parser.add_argument("--outdir", default="assets", help="where to write (default: assets/)")
    parser.add_argument("--keep-svg", action="store_true", help="keep the SVG companions too")
    args = parser.parse_args(argv)

    try:
        import standpoint  # noqa: F401
    except ImportError:
        # standpoint is a sibling tool, not a dependency of this package: it is
        # installed on its own and this script is run with its interpreter.
        print(
            "standpoint is not importable here. Install it (`pipx install standpoint`)\n"
            "and run this with its interpreter:\n"
            "  ~/.local/pipx/venvs/standpoint/bin/python scripts/positioning.py",
            file=sys.stderr,
        )
        return 127

    unknown = [name for name in args.figures if name not in FIGURES]
    if unknown:
        parser.error(f"unknown figure(s): {', '.join(unknown)} (known: {', '.join(FIGURES)})")

    for stem in args.figures or list(FIGURES):
        for path in build(stem, FIGURES[stem], args.outdir, keep_svg=args.keep_svg):
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
