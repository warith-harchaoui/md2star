#!/usr/bin/env python3
"""Compile md2star's ``.po`` catalogues into the ``.mo`` files gettext reads.

The format work lives in :mod:`os_helper.gettext_utils`, shared across the AI
Helpers suite; this is the command-line face of it for this package. It used
to carry its own ``.po`` parser and ``.mo`` writer — a second copy of the same
two hundred lines, which is exactly what moving md2star onto
:class:`os_helper.Catalog` was meant to retire.

GNU gettext's ``msgfmt`` would do the same job, and requiring it would mean a
translated interface could only be built on a machine where somebody had
installed the gettext tools — on macOS, a Homebrew package. The ``.mo`` format
is a header, two offset tables and a blob of strings, so the suite writes it
rather than depending on that. The thing is small; the dependency is not.

Usage
-----
::

    python scripts/compile_catalogs.py            # compile every .po in place
    python scripts/compile_catalogs.py --check    # fail if any .mo is stale

``--check`` is what CI wants: it recompiles in memory and compares, so a
translation edited without recompiling cannot reach a release looking live.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
import os_helper as osh

#: Re-exported so anything that imported them from here keeps working.
build_mo = osh.build_mo
parse_po = osh.parse_po

# ``-h`` beside ``--help``: md2star's own command line answers to both
# (md2star/cli.py), and a helper script that only knows the long spelling is a
# script people type twice.
_CONTEXT: dict[str, object] = {"help_option_names": ["-h", "--help"]}


@click.command("compile_catalogs", context_settings=_CONTEXT)
@click.option(
    "--check",
    is_flag=True,
    help="do not write; exit 1 if any .mo differs from its .po",
)
@click.option(
    "--root",
    default="md2star/data/locales",
    help="directory holding <lang>/LC_MESSAGES/*.po",
)
def cli(check: bool, root: str) -> int:
    """Compile (or check) every catalogue under --root.

    \f

    Everything past the form feed is for readers of the source: click
    truncates --help there. Without it the numpydoc block below would be
    reflowed into the user's help output, "Parameters ----------" and all.

    Parameters
    ----------
    check : bool
        Recompile in memory and compare instead of writing, so a translation
        edited without recompiling cannot reach a release looking live.
    root : str
        Directory holding ``<lang>/LC_MESSAGES/*.po``.

    Returns
    -------
    int
        ``0`` when every ``.mo`` is in step with its ``.po``. ``1`` when
        ``--check`` found one stale or missing, or when the root holds no
        ``.po`` at all — a silent success there would let a packaging mistake
        look like a finished build.
    """
    root_dir = Path(root)
    if not sorted(root_dir.glob("*/LC_MESSAGES/*.po")):
        print(f"compile_catalogs: no .po under {root_dir}", file=sys.stderr)
        return 1

    touched = osh.compile_catalogs(root_dir, check=check)

    if check:
        if touched:
            for path in touched:
                print(f"stale: {path}", file=sys.stderr)
            print(
                f"compile_catalogs: {len(touched)} catalogue(s) out of date; "
                "run `python scripts/compile_catalogs.py`",
                file=sys.stderr,
            )
            return 1
        print("compile_catalogs: every catalogue is up to date ✓")
        return 0

    for path in touched:
        print(f"wrote {path} ({len(osh.parse_po(path.with_suffix('.po')))} entries)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return its exit code instead of exiting.

    ``standalone_mode=False`` is what keeps this an ordinary function returning
    an int: ``tests/test_i18n.py`` asserts ``main(["--check", "--root", ...])
    == 0``, which a click command that called :func:`sys.exit` itself could
    not answer.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns
    -------
    int
        The code :func:`cli` returned, or click's own (2) for a usage error.
    """
    try:
        return int(cli.main(args=argv, prog_name="compile_catalogs", standalone_mode=False) or 0)
    except click.ClickException as exc:
        # Render click's own formatted message, then hand back its code rather
        # than letting the exception escape to a traceback.
        exc.show()
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
