"""md2star's command line, built with click.

One parser, one surface. Until 3.10.0 this module held an argparse front-end
*and* the conversion engine, while a second module (``click_cli.py``) offered a
click façade that rebuilt an argv string list and handed it back here to be
re-parsed. Two parsers for one command line meant two places to add a flag —
and by the end, five commands and nine options existed on only one of them.

Now the parsing happens once, here, and the engine lives in
:mod:`md2star.pipeline` behind a typed :class:`~md2star.pipeline.ConvertOptions`.

Console entry points (``[project.scripts]`` in ``pyproject.toml``):

* ``md2star <command> [...]``          → :func:`main`
* ``md2docx <input.md> [options...]``  → :func:`md2docx_main`
* ``md2pptx <input.md> [options...]``  → :func:`md2pptx_main`
* ``md2pdf  <input.md> [options...]``  → :func:`md2pdf_main`

The three ``md2<fmt>`` entries are not aliases of a single command: they are the
*same* click command object, reachable either as ``md2star docx`` or as
``md2docx``, so a flag can never exist on one spelling and not the other.

The Pandoc passthrough
----------------------
md2star's defining behaviour is that **flags it does not recognise go straight
to Pandoc**. argparse did that with ``parse_known_args``; click is strict by
default, so each converter is declared with
``context_settings={"ignore_unknown_options": True}`` and swallows everything
into one ``nargs=-1, type=click.UNPROCESSED`` argument, which
:func:`_split_input` then separates into "the input file" and "Pandoc's
problem". See that function for why the split is positional rather than clever.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

import click

from . import __version__
from .cache import cache_dir, clear_cache
from .errors import (
    InvalidInputError,
    Md2starError,
    MissingDependencyError,
)
from .i18n import gettext as _
from .logging import configure as configure_logging
from .logging import get_logger
from .pipeline import ConvertOptions, convert

# Module logger — a dotted child of the root "md2star" logger, so it inherits
# the handler + level installed by ``configure_logging`` at CLI startup.
logger = get_logger(__name__)

# ``-h`` as well as ``--help`` everywhere: a CLI that answers only to the long
# spelling is a CLI people type twice.
_CONTEXT: dict[str, object] = {"help_option_names": ["-h", "--help"]}

# The converters add one setting: unknown options are not an error, they are
# Pandoc's. This single dict is what keeps md2star's headline feature alive
# under click.
_PASSTHROUGH_CONTEXT: dict[str, object] = {**_CONTEXT, "ignore_unknown_options": True}

# Shown under each converter's --help. It names the collision rule because the
# alternative is a user discovering by accident that ``-V`` is md2star's version
# flag and not Pandoc's ``--variable``.
_PASSTHROUGH_EPILOG = (
    "Unknown flags are forwarded to pandoc verbatim, after md2star's own, so "
    "they win: `md2docx report.md --toc --metadata=subject:Q3`. Run `pandoc "
    "--help` for the full list. The few short flags md2star defines itself "
    "(-o, -v, -q, -V) are md2star's; spell pandoc's long form to forward it "
    "(--variable, not -V)."
)

# Per-format one-liners, reused in each converter's help so the three stay
# phrased alike.
_FORMAT_HELP = {
    "docx": "Microsoft Word (.docx)",
    "pptx": "Microsoft PowerPoint (.pptx)",
    "pdf": "Portable Document Format (.pdf, via headless LibreOffice)",
}


# ─────────────────────────────────────────────────────────────────────
# Shared plumbing
# ─────────────────────────────────────────────────────────────────────


class _OrderedGroup(click.Group):
    """A group whose ``--help`` lists commands as declared, not alphabetically.

    click sorts by default, which would open md2star's help with ``audit`` and
    ``cache-dir`` and bury the three conversions the tool exists for.
    """

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Return the command names in insertion order."""
        return list(self.commands)


def _version_option() -> click.Option:
    """``-V`` / ``--version``, as an Option object rather than a decorator.

    The converters declare their parameters as an explicit list (see
    :func:`_format_command`) so the ``--help`` order is the order written, and
    ``click.version_option`` is a decorator, not an object. Building it by hand
    also lets the message stay exactly what the argparse CLI printed —
    ``md2star 3.9.0`` — which is what scripts parsing it already expect.

    ``-V`` is capital because ``-v`` is ``--verbose``.

    Returns
    -------
    click.Option
        An eager, non-exposed flag that prints the version and exits 0.
    """

    def _show(ctx: click.Context, param: click.Parameter, value: bool) -> None:
        # `resilient_parsing` is set while click builds shell completions; a
        # version banner printed there would end up inside the completion.
        if not value or ctx.resilient_parsing:
            return
        click.echo(f"md2star {__version__}")
        ctx.exit()

    return click.Option(
        ["-V", "--version"],
        is_flag=True,
        expose_value=False,
        is_eager=True,
        callback=_show,
        help="Show the version and exit.",
    )


def _split_input(tokens: Sequence[str]) -> tuple[str | None, list[str]]:
    """Separate the input file from the flags bound for Pandoc.

    The rule is the simplest one that is also *faithful*: the first token that
    does not look like an option is the input; everything else, in order, is
    Pandoc's. It was chosen by checking what ``parse_known_args`` actually did
    rather than by taste, and it agrees with argparse on every shape measured —
    including the one they both get wrong. ``--metadata key:val in.md`` makes
    ``key:val`` the input under both, because no parser can know that an
    unknown option takes a value. (``--metadata=key:val`` is unambiguous and
    works; so does putting the input first, which every example does.)

    Parameters
    ----------
    tokens : sequence of str
        Everything click could not account for, in command-line order.

    Returns
    -------
    input_path : str or None
        The input file, or ``None`` when every token looked like an option.
    pandoc_args : list of str
        The remaining tokens, order preserved, to append to the pandoc call.
    """
    for index, token in enumerate(tokens):
        # A bare "-" is a filename-shaped token (stdin, conventionally), not an
        # option, so it is a candidate input like any other word.
        if not token.startswith("-") or token == "-":
            return token, [*tokens[:index], *tokens[index + 1 :]]
    return None, list(tokens)


def _render_error(exc: Md2starError) -> None:
    """Pretty-print a typed exception to stderr — headline + indented hint.

    Replaces the raw Python traceback with a two-block message:

        md2star: <headline error>
          <hint, indented and word-wrapped at the natural newlines>

    Called by :func:`_run_conversion` so users see actionable text instead of a
    traceback when the failure mode is something we already anticipated (see
    :mod:`md2star.errors`).
    """
    # Headline goes at error level; each hint line is emitted separately so
    # the "%(message)s" formatter keeps the original two-block, indented
    # layout (no per-line "md2star:" prefix on the wrapped hint).
    logger.error(f"md2star: {exc}")
    if exc.hint:
        for line in exc.hint.splitlines():
            logger.error(f"  {line}")


def _run_conversion(fmt: str, opts: ConvertOptions, pandoc_args: Sequence[str]) -> int:
    """Call the engine and turn its typed failures into exit codes.

    Catches every :class:`~md2star.errors.Md2starError` subclass and renders it
    via :func:`_render_error`. Anything that does not subclass it is left to
    bubble up as a Python traceback — that is a real bug we want users to file.
    """
    try:
        return convert(fmt, opts, pandoc_args)
    except KeyboardInterrupt:
        # Ctrl-C during a long conversion (Pandoc, a Mermaid render, a
        # LibreOffice PDF pass) should read as a clean stop, not a scary
        # traceback. 130 = shell 128 + SIGINT(2), the conventional exit
        # code so callers/scripts can distinguish an interrupt from a
        # real failure.
        logger.warning("md2star: interrupted.")
        return 130
    except Md2starError as exc:
        _render_error(exc)
        # Exit code conventions: 127 for missing system deps (mirrors
        # the shell convention), 2 for invalid CLI input, 1 otherwise.
        if isinstance(exc, MissingDependencyError):
            return 127
        if isinstance(exc, InvalidInputError):
            return 2
        return 1


def _dispatch(command: click.Command, argv: Sequence[str] | None, prog_name: str) -> int:
    """Run *command* and return an exit code instead of exiting the process.

    ``standalone_mode=False`` stops click from calling :func:`sys.exit` itself,
    which is what lets every console entry point here be an ordinary function
    returning an int — callable from a test, and from
    ``[project.scripts]``, which wraps it in ``sys.exit(...)`` anyway.

    Parameters
    ----------
    command : click.Command
        The group or command to run.
    argv : sequence of str or None
        Arguments, excluding the program name. ``None`` reads ``sys.argv``.
    prog_name : str
        How the command names itself in usage and error messages.

    Returns
    -------
    int
        0 on success, the command's own code otherwise, or click's exit code
        (2) for a usage error.
    """
    try:
        result = command.main(
            args=list(sys.argv[1:] if argv is None else argv),
            prog_name=prog_name,
            standalone_mode=False,
        )
    except click.ClickException as exc:
        # Render click's own formatted message (usage errors, bad option
        # values), then hand back its code rather than raising through.
        exc.show()
        return exc.exit_code
    except click.Abort:
        # click converts KeyboardInterrupt/EOF into Abort. The conversion path
        # catches Ctrl-C itself; this covers an interrupt during parsing.
        return 130
    # Commands signal failure with ``ctx.exit(rc)``, which `main` returns here;
    # a command that simply finished returns None.
    return int(result or 0)


# ─────────────────────────────────────────────────────────────────────
# The three converters
# ─────────────────────────────────────────────────────────────────────


def _shared_params() -> list[click.Parameter]:
    """The conversion options every format accepts, in ``--help`` order.

    Returned as a fresh list per call because a :class:`click.Parameter` is
    bound to the command that owns it; sharing one instance across the three
    converters would make them share state.
    """
    return [
        # `click.Path()` and not `writable=True`: the destination usually does
        # not exist yet, and the engine owns the "input is also the output"
        # refusal that a path check cannot express.
        click.Option(["-o", "--output"], type=click.Path(), help="Output path."),
        click.Option(["--author"], help="Document author (Pandoc metadata)."),
        # `exists=True` here on purpose: a missing .bib otherwise surfaces as a
        # citeproc error from inside pandoc, several screens from the typo.
        click.Option(
            ["--bib"],
            type=click.Path(exists=True, dir_okay=False),
            help="Bibliography file (BibTeX). Enables --citeproc automatically.",
        ),
        click.Option(
            ["--bibliography-name"],
            # None, not "Bibliography": the engine resolves the heading from the
            # document's language, and a default here would hide that.
            help=(
                "Heading inserted before the bibliography. When omitted, "
                "md2star uses the localized default for the document's language."
            ),
        ),
        click.Option(["--lang"], help="Document language metadata (BCP 47, e.g. en-US)."),
        click.Option(
            ["--date"],
            help=(
                "Override the auto-generated date in the subtitle; used verbatim "
                "(e.g. '21 juin 2026', '2026-Q2')."
            ),
        ),
        click.Option(
            ["--lint/--no-lint"],
            default=False,
            help=(
                "Opt in to the local LLM linter (off by default). Also fills empty "
                "image alt text with a vision-model description. Backend and model "
                "come from md2star's llm.brief.yaml via best-engine-ai-helper."
            ),
        ),
        # `multiple=True` is argparse's `action="append"`: click collects a
        # tuple, which is what ConvertOptions.skip_phase is typed as.
        click.Option(
            ["--skip-phase"],
            multiple=True,
            metavar="NAME",
            help=(
                "Skip a preprocessing phase. Repeatable. Known phases: lint, "
                "remote_images, html_tables, html_images, absolutize, image_assets, "
                "language, line_pass, table_resize, table_normalize, image_widths, "
                "pptx_isolation."
            ),
        ),
        click.Option(
            ["--reference-doc"],
            type=click.Path(exists=True),
            help="Override the auto-detected reference template.",
        ),
        click.Option(
            ["--offline"],
            is_flag=True,
            help=(
                "Forbid every network-touching phase (overrides --allow-remote-*). "
                "Useful for air-gapped runs and to make the refusal explicit."
            ),
        ),
        click.Option(
            ["--no-remote-templates"],
            is_flag=True,
            help=(
                "Opt OUT of the deraison.ai default template. Since v2.5.0 md2star "
                "fetches https://deraison.ai/template.{docx,pptx} whenever no local "
                "template is found, caching it under XDG."
            ),
        ),
        click.Option(
            # Back-compat no-op: remote templates are the default since v2.5.0,
            # so the old opt-in flag has nothing left to enable. Accepted (and
            # hidden, and never exposed to the callback) so existing scripts and
            # CI that still pass it keep working instead of erroring out.
            ["--allow-remote-templates"],
            is_flag=True,
            expose_value=False,
            hidden=True,
        ),
        click.Option(
            ["--allow-remote-images"],
            is_flag=True,
            help=(
                "Opt in to downloading ![](https://...) images referenced in the "
                "markdown. Off by default — the preprocessor leaves remote refs in "
                "place and warns once on stderr."
            ),
        ),
        # Two booleans rather than click's `count=True`: the logging layer has
        # three levels (DEBUG / INFO / ERROR), so -vv would mean nothing. The
        # pair is mutually exclusive, enforced in the callback.
        click.Option(
            ["-v", "--verbose"], is_flag=True, help="Show debug-level diagnostics on stderr."
        ),
        click.Option(
            ["-q", "--quiet"], is_flag=True, help="Suppress info + warnings; errors only."
        ),
        # Last, so --help ends on the two flags nobody needs to read about.
        _version_option(),
    ]


def _smart_layout_params() -> list[click.Parameter]:
    """The pptx-only, template-intelligent options.

    Kept off docx/pdf because they describe a path that bypasses Pandoc
    entirely (see :func:`md2star.pipeline._convert_smart_layout`); offering
    them where they cannot work would be a promise the tool breaks.
    """
    return [
        click.Option(
            ["--smart-layout"],
            is_flag=True,
            help=(
                "Map each slide onto a real designer PowerPoint template's own named "
                "layouts (AI layout selection, python-pptx assembly) instead of "
                "Pandoc's ~7 generic ones. Requires --template; needs "
                "`pip install 'md2star[pptx]'` and a resolvable LLM+VLM engine."
            ),
        ),
        click.Option(
            ["--template"],
            # Deliberately not click.Path(exists=True): the engine raises its own
            # translated "template not found" error, which says which path it
            # looked at and that it wants the *designer's* file.
            help="Designer .pptx template for --smart-layout (its own file, not md2star's).",
        ),
        click.Option(
            ["--reference-slides"],
            is_flag=True,
            help=(
                "--smart-layout only: clone the designer's own example slide for each "
                "layout (their decorative shapes and typography, not just their "
                "background) and replace its text with yours."
            ),
        ),
        click.Option(
            ["--no-visual-confirm"],
            is_flag=True,
            help=(
                "--smart-layout only: skip the VLM visual tie-break stage "
                "(cheaper, text-only layout selection)."
            ),
        ),
        click.Option(
            ["--eyeball-iterations"],
            type=int,
            default=0,
            metavar="N",
            help=(
                "--smart-layout only: run the target-matching Ralph Eyeball Loop for "
                "N bounded revision passes after assembly (0 = off; each pass "
                "re-renders the deck and costs one VLM call per slide)."
            ),
        ),
    ]


def _format_command(fmt: str) -> click.Command:
    """Build the converter command for *fmt*.

    One command object serves two spellings — ``md2star docx`` and ``md2docx``
    — so the flag set cannot drift between them. Parameters are passed as an
    explicit list rather than stacked decorators because decorator order and
    ``--help`` order are reverses of each other, which is how an option ends up
    documented three screens from its neighbours.
    """

    @click.pass_context
    def _callback(ctx: click.Context, tokens: tuple[str, ...], **values: object) -> None:
        source, pandoc_args = _split_input(tokens)
        if source is None:
            # Nothing that could be a filename: argparse called this a usage
            # error and so do we, with the name of what is missing.
            raise click.UsageError("missing INPUT.md — the Markdown file to convert", ctx=ctx)
        if values["verbose"] and values["quiet"]:
            # argparse enforced this with a mutually-exclusive group; click has
            # no equivalent, so the check is explicit and the code stays 2.
            raise click.UsageError("--verbose and --quiet cannot be combined", ctx=ctx)
        # Every remaining click value is named exactly like a ConvertOptions
        # field, so the options reach the engine typed and whole rather than as
        # an argv the engine has to parse a second time.
        rc = _run_conversion(fmt, ConvertOptions(input=source, **values), pandoc_args)
        if rc:
            ctx.exit(rc)

    # The variadic argument comes first so click fills it from the leftover
    # args in command-line order — which is what `_split_input` then relies on.
    params: list[click.Parameter] = [
        click.Argument(
            ["tokens"],
            nargs=-1,
            type=click.UNPROCESSED,
            metavar="INPUT.md [PANDOC_ARGS]...",
        ),
        *_shared_params(),
    ]
    # Only pptx gets the template-intelligent flags. On docx/pdf they fall
    # through to the passthrough instead, where pandoc rejects them — a
    # refusal, rather than a flag that is accepted and quietly ignored.
    if fmt == "pptx":
        params.extend(_smart_layout_params())

    return click.Command(
        name=fmt,
        callback=_callback,
        params=params,
        context_settings=_PASSTHROUGH_CONTEXT,
        short_help=f"Markdown → {_FORMAT_HELP[fmt]}.",
        help=f"Convert a Markdown file to {_FORMAT_HELP[fmt]} via md2star + Pandoc.",
        epilog=_PASSTHROUGH_EPILOG,
    )


#: The three converters, built once and shared by the group and the ``md2<fmt>``
#: console scripts. Keyed by format so the entry points below stay one-liners.
_CONVERTERS: dict[str, click.Command] = {
    fmt: _format_command(fmt) for fmt in ("docx", "pptx", "pdf")
}


# ─────────────────────────────────────────────────────────────────────
# The ``md2star`` group
# ─────────────────────────────────────────────────────────────────────


@click.group(cls=_OrderedGroup, context_settings=_CONTEXT)
@click.version_option(__version__, "-V", "--version", message="md2star %(version)s")
def cli() -> None:
    """Markdown → DOCX / PPTX / PDF, and back again.

    A Pandoc wrapper with curated templates, BibTeX citations, Mermaid
    rendering, math and remote-image embedding — plus "twin", which reads a
    finished document back into editable Markdown, and "audit", which measures
    a deck for overlapping or unreadable text.

    md2docx, md2pptx and md2pdf are installed as shorthands for the three
    conversions; they are the same commands, with the same flags.
    """
    # Install the logging handler with defaults so any subcommand that reports
    # before it has parsed -v/-q has a stderr sink. configure() is idempotent;
    # the converters re-invoke it with the parsed verbosity.
    configure_logging()


# Registered rather than re-declared: `cli.commands["docx"]` and the object
# behind `md2docx` are the same Command, which is what makes "a flag can only
# be added once" structurally true instead of a convention.
for _converter in _CONVERTERS.values():
    cli.add_command(_converter)


@cli.command(name="gui", context_settings=_CONTEXT)
@click.option("--port", type=int, default=8765, help="Preferred port (auto-falls-back if in use).")
@click.option("--no-browser", is_flag=True, help="Do not auto-open the browser (URL is printed).")
@click.option(
    "--bind",
    default="127.0.0.1",
    help="Bind address (localhost only by default; 0.0.0.0 exposes it to the LAN, unauthenticated).",
)
@click.pass_context
def gui(ctx: click.Context, port: int, no_browser: bool, bind: str) -> None:
    """Launch the local Markdown editor with a live PDF preview."""
    # Lazy import: the GUI ships a ~4 MB vendored frontend and the http.server
    # machinery, which a plain conversion must never pay for.
    from .gui_server import serve

    ctx.exit(serve(port=port, no_browser=no_browser, bind=bind))


@cli.command(name="twin", context_settings=_CONTEXT)
@click.argument("input_path", metavar="INPUT", type=click.Path())
@click.option("--out", "out_dir", metavar="DIR", help="Output folder (default: the input's).")
@click.option("--no-images", is_flag=True, help="Prose + tables only; drop scraped rasters.")
@click.option(
    "--diagrams",
    is_flag=True,
    help="Re-author figures via the local VLM eyeball loop — node-and-edge diagrams "
    "as Mermaid, other vector figures as SVG.",
)
@click.option("--model", metavar="TAG", help="Vision model tag for --diagrams.")
@click.option(
    "--max-iterations", type=int, default=3, metavar="N", help="Eyeball-loop budget per diagram."
)
@click.option("-v", "--verbose", is_flag=True, help="Debug logging.")
@click.option("-q", "--quiet", is_flag=True, help="Warnings and errors only.")
@click.pass_context
def twin(
    ctx: click.Context,
    input_path: str,
    out_dir: str | None,
    no_images: bool,
    diagrams: bool,
    model: str | None,
    max_iterations: int,
    verbose: bool,
    quiet: bool,
) -> None:
    """Read a document back into an editable Markdown twin (prose + tables + images)."""
    # Lazy import so a plain forward conversion never loads Kreuzberg / the AI
    # reconstruction stack.
    from .twin_cli import run as twin_run

    ctx.exit(
        twin_run(
            input_path,
            out_dir=out_dir,
            no_images=no_images,
            diagrams=diagrams,
            model=model,
            max_iterations=max_iterations,
            verbose=verbose,
            quiet=quiet,
        )
    )


@cli.command(name="audit", context_settings=_CONTEXT)
@click.argument("deck", metavar="DECK.pptx", type=click.Path())
@click.option("--json", "as_json", is_flag=True, help="Machine-readable findings.")
@click.option(
    "--strict", is_flag=True, help="Also fail on `overrun`, which is otherwise an observation."
)
@click.pass_context
def audit(ctx: click.Context, deck: str, as_json: bool, strict: bool) -> None:
    """Report overlaps, off-canvas shapes and unreadable type in any .pptx.

    Works on decks md2star did not build: everything it checks is read off the
    OOXML. Deterministic — no model, no render, no network.
    """
    try:
        # Lazy, and guarded: the auditor needs python-pptx, an opt-in extra.
        from .pptx_audit import run as audit_run
    except ImportError as exc:
        logger.error("md2star audit needs python-pptx: pip install 'md2star[pptx]' (%s)", exc)
        ctx.exit(2)
    else:
        ctx.exit(audit_run(deck, as_json=as_json, strict=strict))


# The only translated help text in this module, and deliberately so: these two
# strings were translated when `doctor` owned an argparse parser, and dropping
# the `_()` call would have served a French reader English for no reason other
# than a refactor. The rest of the CLI's help has always been English-only
# (`md2star --help` is as much a machine interface as a human one — see
# md2star/i18n.py on why the CLI answers to MD2STAR_LANG and nothing else).
#
# One consequence of a decorator: the lookup happens at import, so MD2STAR_LANG
# has to be set before the process starts. For help text that is exactly how it
# is read anyway; the diagnostics the engine raises are looked up when raised.
@cli.command(
    name="doctor",
    context_settings=_CONTEXT,
    help=_("Print a diagnostic summary of the environment md2star runs in."),
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help=_("Emit the report as JSON instead of human-readable text."),
)
@click.pass_context
def doctor(ctx: click.Context, as_json: bool) -> None:
    """Report the environment md2star runs in (Python, Pandoc, LibreOffice, Node)."""
    from .doctor import run as run_doctor

    ctx.exit(run_doctor(as_json=as_json))


@cli.group(name="templates", cls=_OrderedGroup, context_settings=_CONTEXT)
def templates() -> None:
    """Inspect bundled / cached / per-project templates without converting."""
    # Dispatch-only: the two subcommands below do the work.


@templates.command(name="list", context_settings=_CONTEXT)
@click.option(
    "--dir",
    "directory",
    type=click.Path(),
    help="Treat this directory as the per-project root (default: the cwd).",
)
@click.pass_context
def templates_list(ctx: click.Context, directory: str | None) -> None:
    """Show every resolution candidate (per-project / cached / bundled)."""
    from .templates import cmd_list

    ctx.exit(cmd_list(directory))


# `required=False` on the positional: without an input file the command
# resolves against the current directory, which is the common case ("which
# template would a conversion here pick up?").
@templates.command(name="path", context_settings=_CONTEXT)
@click.option(
    "--fmt",
    type=click.Choice(["docx", "pptx"]),
    default="docx",
    show_default=True,
    help="Output format whose template to resolve.",
)
@click.argument("source", metavar="[INPUT.md]", type=click.Path(), required=False)
@click.pass_context
def templates_path(ctx: click.Context, fmt: str, source: str | None) -> None:
    """Print the absolute path of the active template for a given format."""
    from .templates import cmd_path

    ctx.exit(cmd_path(fmt, source))


@cli.command(name="cache-dir", context_settings=_CONTEXT)
def cache_dir_command() -> None:
    """Print the resolved cache directory path."""
    # stdout, not the logger: this is the value a script captures.
    click.echo(str(cache_dir()))


@cli.command(name="clear-cache", context_settings=_CONTEXT)
def clear_cache_command() -> None:
    """Wipe the cache directory (templates, resized rasters, mermaid renders)."""
    # The freed figure is the point of the message: a cache wipe that reports
    # nothing leaves the user unsure whether anything was there.
    freed = clear_cache()
    click.echo(f"md2star: cleared cache ({freed / 1024:.1f} KiB freed)")


# ─────────────────────────────────────────────────────────────────────
# Console entry points
# ─────────────────────────────────────────────────────────────────────


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point: ``md2star <command> [...]``."""
    return _dispatch(cli, argv, "md2star")


def md2docx_main(argv: Sequence[str] | None = None) -> int:
    """Console entry point: ``md2docx <input.md> [options...]``."""
    return _dispatch(_CONVERTERS["docx"], argv, "md2docx")


def md2pptx_main(argv: Sequence[str] | None = None) -> int:
    """Console entry point: ``md2pptx <input.md> [options...]``."""
    return _dispatch(_CONVERTERS["pptx"], argv, "md2pptx")


def md2pdf_main(argv: Sequence[str] | None = None) -> int:
    """Console entry point: ``md2pdf <input.md> [options...]``."""
    return _dispatch(_CONVERTERS["pdf"], argv, "md2pdf")


if __name__ == "__main__":
    sys.exit(main())
