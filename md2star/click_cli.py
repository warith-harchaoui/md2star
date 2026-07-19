"""Click front-end for md2star — a modern alternative to the argparse CLI.

md2star's primary command-line surface is argparse-based (``md2docx`` /
``md2pptx`` / ``md2pdf`` / ``md2star …``), which is what forwards unknown flags
straight to Pandoc. This module adds a **click** front-end over the *same*
conversion pipeline for users who prefer click's grouped-command ergonomics and
rich ``--help``. It is a thin adapter: every command reconstructs the flag list
and delegates to :func:`md2star.cli._convert` (and the existing GUI / doctor
dispatch), so there is exactly one implementation of the conversion logic and
the two front-ends can never drift.

Installed as the ``md2star-x`` console script::

    md2star-x docx report.md --author "Ada Lovelace"
    md2star-x pptx slides.md --reference-doc deck.pptx
    md2star-x pdf paper.md --bib refs.bib
    md2star-x gui --port 9000
    md2star-x doctor --json

``click`` is a light, ubiquitous dependency; it is declared in the core
requirements so ``md2star-x`` is always available alongside the argparse CLI.


Author
------
[Warith Harchaoui](https://www.linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import sys

import click

from . import __version__
from .cli import _convert

# Formats the click group exposes as subcommands, mapped 1:1 onto the argparse
# CLI's format parsers. Kept as data so adding a format is a one-line change.
_FORMATS = ("docx", "pptx", "pdf")


def _argv_from_options(inp: str, opts: dict[str, object]) -> list[str]:
    """Rebuild the argparse-style argv that :func:`_convert` expects.

    click parses the options for us; ``_convert`` re-parses an argv list, so we
    translate the collected click values back into ``[input, --flag, value, …]``.
    Only supplied options are appended, so unset ones fall through to the
    template / ``metadata.yaml`` defaults exactly like the argparse CLI.

    Parameters
    ----------
    inp : str
        Path to the input Markdown file (the positional argument).
    opts : dict
        The click option values (``output``, ``author``, ``bib``, …).

    Returns
    -------
    list of str
        The argv list to hand to :func:`md2star.cli._convert`.
    """
    argv: list[str] = [inp]

    # Value-bearing options: append ``--flag value`` only when the user set them.
    # The keys mirror the argparse ``dest`` names so the mapping is obvious.
    value_flags = {
        "output": "--output",
        "author": "--author",
        "bib": "--bib",
        "bibliography_name": "--bibliography-name",
        "lang": "--lang",
        "date": "--date",
        "reference_doc": "--reference-doc",
        "skip_phase": "--skip-phase",
    }
    for key, flag in value_flags.items():
        val = opts.get(key)
        if val:
            argv += [flag, str(val)]

    # Boolean switches: emit the bare flag when true. ``lint`` is tri-state
    # (None = unspecified) so we can forward both --lint and --no-lint.
    if opts.get("offline"):
        argv.append("--offline")
    if opts.get("no_remote_templates"):
        argv.append("--no-remote-templates")
    if opts.get("allow_remote_images"):
        argv.append("--allow-remote-images")
    if opts.get("verbose"):
        argv.append("--verbose")
    if opts.get("quiet"):
        argv.append("--quiet")
    lint = opts.get("lint")
    if lint is True:
        argv.append("--lint")
    elif lint is False:
        argv.append("--no-lint")

    return argv


def _shared_options(func):
    """Attach the full set of conversion options shared by docx/pptx/pdf.

    A single decorator keeps the three format commands in lock-step — the same
    flags, help text and defaults — without repeating the option list thrice.
    """
    # Declared in reverse of display order because click stacks decorators
    # bottom-up; the resulting --help lists them top-down as written here.
    options = [
        click.option("-o", "--output", type=click.Path(), help="Output path."),
        click.option("--author", help="Document author metadata."),
        click.option("--bib", type=click.Path(exists=True), help="BibTeX file for [@key] citations."),
        click.option("--bibliography-name", help="Heading for the references section."),
        click.option("--lang", help="Language code (e.g. en, fr); auto-detected if unset."),
        click.option("--date", help="Document date metadata."),
        click.option("--reference-doc", type=click.Path(exists=True), help="Brand output with a template.docx/.pptx."),
        click.option("--skip-phase", help="Skip one preprocessing phase by name."),
        click.option("--lint/--no-lint", default=None, help="Opt-in local-LLM syntax + alt-text pass (off by default)."),
        click.option("--offline", is_flag=True, help="Never touch the network."),
        click.option("--no-remote-templates", is_flag=True, help="Do not fetch the default remote template."),
        click.option("--allow-remote-images", is_flag=True, help="Download http(s) images for embedding."),
        click.option("-v", "--verbose", is_flag=True, help="Verbose logging."),
        click.option("-q", "--quiet", is_flag=True, help="Quiet logging."),
    ]
    for opt in reversed(options):
        func = opt(func)
    return func


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="md2star-x")
def cli() -> None:
    """md2star (click front-end) — Markdown → DOCX / PPTX / PDF.

    A modern alternative to the argparse CLI; both drive the same pipeline.
    """
    # Body intentionally empty: click dispatches to the subcommands registered
    # below. ``-h``/``--help`` is enabled group-wide via context_settings, and
    # the version is single-sourced from the package __version__.


def _make_format_command(fmt: str):
    """Build a click command that converts Markdown to *fmt* via ``_convert``.

    A factory (rather than three near-identical functions) keeps docx/pptx/pdf
    defined once; *fmt* is captured in the closure so each command targets its
    own format while sharing the option set and delegation logic.
    """
    # ``exists=True`` makes click reject a missing input with a usage error (2)
    # before we ever call the pipeline — matching the argparse CLI's behaviour.
    @click.command(name=fmt, help=f"Convert a Markdown file to .{fmt}.")
    @click.argument("input", type=click.Path(exists=True))
    @_shared_options
    def _cmd(input: str, **opts: object) -> None:  # noqa: A002 - click arg name
        # Delegate to the single source of truth; propagate its exit code so
        # scripts and CI see the same status the argparse CLI would return.
        rc = _convert(fmt, _argv_from_options(input, opts))
        if rc:
            raise SystemExit(rc)

    return _cmd


# Register docx / pptx / pdf from the data-driven list above.
for _fmt in _FORMATS:
    cli.add_command(_make_format_command(_fmt))


@cli.command(name="gui")
@click.option("--port", type=int, default=8765, help="Preferred port.")
@click.option("--no-browser", is_flag=True, help="Do not auto-open the browser.")
@click.option("--bind", default="127.0.0.1", help="Bind address (localhost by default).")
def gui(port: int, no_browser: bool, bind: str) -> None:
    """Launch the local Markdown → PDF preview GUI."""
    # Reuse the exact argparse GUI entry so behaviour (and the LAN-bind warning
    # banner) is identical across both front-ends.
    from .gui_server import main as gui_main

    argv = ["--port", str(port), "--bind", bind]
    if no_browser:
        argv.append("--no-browser")
    raise SystemExit(gui_main(argv))


@cli.command(name="doctor")
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def doctor(as_json: bool) -> None:
    """Report the environment (Python, Pandoc, LibreOffice, Node, Ollama)."""
    from .doctor import main as doctor_main

    raise SystemExit(doctor_main(["--json"] if as_json else []))


def main(argv: list[str] | None = None) -> int:
    """Console entry point for ``md2star-x``.

    click normally manages its own process exit; we wrap it so the function is
    callable in tests and returns an int like the argparse ``main``.
    """
    # ``standalone_mode=False`` stops click from calling sys.exit() itself, so we
    # can capture the outcome and return an int (the commands raise SystemExit
    # with the pipeline's exit code; click raises ClickException on usage errors).
    try:
        cli.main(args=argv if argv is not None else sys.argv[1:], standalone_mode=False)
    except SystemExit as exc:  # commands raise SystemExit carrying the code
        return int(exc.code or 0)
    except click.ClickException as exc:
        # Render click's own formatted error message, then hand back its code.
        exc.show()
        return exc.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
