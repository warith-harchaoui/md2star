"""md2star's conversion engine: Markdown → DOCX / PPTX / PDF.

This module is the pipeline, not the command line. It used to live in
``md2star/cli.py`` next to an argparse front-end, which meant the engine was
reachable only by handing it an ``argv`` list that it re-parsed — the GUI
server and the FastAPI surface both built fake command lines for that reason.
Since 3.10.0 the single command line is click (see :mod:`md2star.cli`), the
parsing happens there once, and every caller hands this module a typed
:class:`ConvertOptions` instead of a string list.

:func:`convert` orchestrates the four steps:

1. **Preprocess** the input Markdown via :func:`md2star.preprocess_markdown`.
2. **Resolve the reference template**: prefer ``template.{docx,pptx}`` next
   to the input file, then the legacy ``.pandoc-reference.{docx,pptx}``,
   then the XDG cache, then (the default since v2.5.0) a one-shot fetch
   from ``deraison.ai`` cached under XDG, and finally the bundled template.
   ``--no-remote-templates`` / ``--offline`` skip the fetch.
3. **Invoke pandoc** with the bundled Lua filter, metadata defaults, and
   resolved reference doc. Everything in ``pandoc_args`` — the flags md2star
   does not know — is appended verbatim, last, so a user can override any
   choice md2star made.
4. **Postprocess** (DOCX only), re-inject the ``MyTable`` / ``MyTableSmall``
   table styles that Pandoc strips when rewriting ``word/styles.xml``.

The PDF format is implemented as a wrapper: it produces the DOCX first
(so all of md2star's polish, from mermaid diagrams to table styles to
slide-aware tweaks, is already applied) and then asks headless LibreOffice
(``soffice --headless --convert-to pdf``) to render that DOCX to PDF. This
guarantees the PDF visually matches the DOCX you would ship.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import os_helper as osh

from .cache import cache_dir
from .errors import (
    InvalidInputError,
    Md2starError,
    MissingDependencyError,
)
from .i18n import gettext as _
from .logging import configure as configure_logging
from .logging import get_logger
from .postprocess import (
    center_standalone_images,
    inject_table_styles,
    strip_table_normal_for_pdf,
)
from .preprocessing import preprocess_markdown

# Module logger — a dotted child of the root "md2star" logger, so it inherits
# the handler + level installed by ``configure_logging`` at CLI startup.
logger = get_logger(__name__)

# Per-format default reference template URL. Kept user-facing — when the URL
# changes you also want to update the README / CHANGELOG / install docs.
_TEMPLATE_URLS: dict[str, str] = {
    "docx": "https://deraison.ai/template.docx",
    "pptx": "https://deraison.ai/template.pptx",
}


# ─────────────────────────────────────────────────────────────────────
# Data-file resolution (Lua filter, defaults YAMLs, templates, mermaid cfg)
# ─────────────────────────────────────────────────────────────────────


def _data_path(*parts: str) -> Path:
    """Return an absolute filesystem path to a file under ``md2star/data/``.

    ``importlib.resources.files()`` returns a ``Traversable`` that resolves
    to a real path for unzipped wheel installs and for editable installs;
    on zipped installs we'd fall back to extracting via ``as_file()``, but
    hatchling ships md2star as an unzipped wheel so direct resolution is
    fine.

    Components are joined one at a time: Python 3.10's
    ``MultiplexedPath.joinpath`` only accepts a single argument per call,
    so the ``joinpath("filters", "md2star.lua")`` form blows up there.
    """
    ref = resources.files("md2star.data")
    for part in parts:
        ref = ref.joinpath(part)
    return Path(str(ref))


def _bundled_template(fmt: str) -> Path:
    """Return the absolute path to the bundled ``template.<fmt>`` shipped in the wheel."""
    return _data_path(f"template.{fmt}")


# ─────────────────────────────────────────────────────────────────────
# Reference template auto-detection
# ─────────────────────────────────────────────────────────────────────


def _resolve_reference_doc(
    input_path: Path,
    fmt: str,
    *,
    allow_remote_templates: bool = True,
    offline: bool = False,
) -> Path | None:
    """Resolve the per-project reference template for *input_path*.

    Resolution order (highest priority first):

    1. ``template.<fmt>`` next to the input file (committable, visible).
       The "zero-config per-project branding" path.
    2. ``.pandoc-reference.<fmt>`` next to the input file (legacy name;
       still honoured with a deprecation notice).
    3. ``$XDG_CACHE_HOME/md2star/templates/template.<fmt>`` — silently
       reused once cached.
    4. **(default)** Download from ``https://deraison.ai/template.<fmt>``
       into the XDG cache. Since v2.5.0 this is the *default* branding
       whenever no local template (steps 1-3) is found: the deraison.ai
       template wins over the bundled fallback. Turn it off with
       ``--no-remote-templates`` (or the hard ``--offline`` kill-switch),
       which drops straight to the bundled default. A failed download
       (no network, 404, timeout) also falls back to bundled, so a
       conversion never breaks just because deraison.ai is unreachable.
    5. Bundled package template (``md2star/data/template.<fmt>``) — the
       always-available offline fallback. Conversion always succeeds.

    Returns ``None`` only if even the bundled template is missing (an
    install bug), in which case the caller lets pandoc fall back to its
    own built-in styling.
    """
    in_dir = input_path.parent.resolve()

    preferred = in_dir / f"template.{fmt}"
    if preferred.exists():
        return preferred

    legacy = in_dir / f".pandoc-reference.{fmt}"
    if legacy.exists():
        # Still honoured, but nudge the user toward the current name.
        logger.warning(
            f"md2star: '.pandoc-reference.{fmt}' is deprecated; rename it to 'template.{fmt}'."
        )
        return legacy

    cached = cache_dir("templates") / f"template.{fmt}"
    if cached.exists():
        return cached

    url = _TEMPLATE_URLS.get(fmt)
    if url is not None and allow_remote_templates and not offline:
        try:
            # os_helper streams the download straight to disk (flat memory,
            # progress bar auto-suppressed off-TTY); progress=False keeps the
            # CLI quiet since this is a small one-shot template fetch.
            osh.download_file(url, str(cached), progress=False)
            # Informational: confirm the (default) network fetch happened.
            # INFO so it stays visible by default but --quiet can hide it.
            logger.info(f"md2star: cached default template from {url} → {cached}")
            return cached
        except Exception as exc:
            # Leave no partial file behind.
            cached.unlink(missing_ok=True)
            logger.warning(
                f"md2star: template download failed ({exc}); falling back to the bundled default."
            )

    bundled = _bundled_template(fmt)
    return bundled if bundled.exists() else None


# ─────────────────────────────────────────────────────────────────────
# Pandoc invocation
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# Localized bibliography heading
# ─────────────────────────────────────────────────────────────────────


# Per-language default heading for the bibliography section md2star
# appends when --bib is passed. The keys match the two-letter language
# prefix used elsewhere in md2star (see md2star/preprocessing/language.py
# and the Lua filter's locale_dicts). When the detected / explicit
# language isn't in this dict, we fall back to English. Translations
# verified against the standard heading used in academic style guides
# for each language.
_BIBLIOGRAPHY_HEADING_BY_LANG: dict[str, str] = {
    "en": "Bibliography",
    "fr": "Bibliographie",
    "es": "Bibliografía",
    "de": "Literatur",
    "it": "Bibliografia",
    "pt": "Bibliografia",
    "nl": "Bibliografie",
    "ru": "Библиография",
}


def _localized_bibliography_heading(content: str, explicit_lang: str | None) -> str:
    """Return the per-language default heading for the appended bibliography.

    Precedence:
        1. Explicit ``--lang`` flag (CLI override).
        2. ``langdetect`` on the markdown body (best-effort).
        3. English fallback ("Bibliography").

    The function is intentionally side-effect-free so callers can wrap
    it in tests without monkeypatching anything; the language detection
    falls back silently when ``langdetect`` is not installed.
    """
    lang_prefix = ""
    if explicit_lang:
        lang_prefix = explicit_lang.split("-")[0].lower()
    else:
        try:
            from .preprocessing.language import get_language_metadata

            meta = get_language_metadata(content)
            if meta and meta.get("lang"):
                lang_prefix = meta["lang"].split("-")[0].lower()
        except Exception:
            pass
    return _BIBLIOGRAPHY_HEADING_BY_LANG.get(lang_prefix, "Bibliography")


def _raw_byte(exc: UnicodeDecodeError) -> int:
    """The offending byte from a decode error, for a message that names it.

    ``exc.object[exc.start]`` is the byte the codec choked on; reporting it
    with its offset is what turns "not valid UTF-8" into something the user
    can locate in their file.
    """
    return exc.object[exc.start]


def _require_pandoc() -> str:
    """Return the path to ``pandoc``, or exit with a clear message."""
    path = shutil.which("pandoc")
    if path is None:
        raise MissingDependencyError(
            "pandoc not found on PATH",
            hint=(
                "Install it from https://pandoc.org/installing.html "
                "(macOS: `brew install pandoc`, Ubuntu: "
                "`sudo apt install pandoc`, Windows: "
                "`winget install --id JohnMacFarlane.Pandoc`). "
                "Then re-run; `md2star doctor` confirms the install."
            ),
        )
    return path


def _run_pandoc(
    fmt: str,
    preprocessed_md: Path,
    output: Path,
    reference_doc: Path | None,
    extra_args: list[str],
) -> int:
    """Spawn pandoc with our Lua filter + metadata, return its exit code."""
    # _require_pandoc raises MissingDependencyError (→ exit 127) if absent.
    pandoc = _require_pandoc()
    # Base invocation: our bundled Lua filter + metadata defaults are always on.
    cmd = [
        pandoc,
        str(preprocessed_md),
        "-o",
        str(output),
        "-t",
        fmt,
        "--lua-filter",
        str(_data_path("filters", "md2star.lua")),
        "--metadata-file",
        str(_data_path("metadata.yaml")),
    ]
    if reference_doc is not None:
        # The user can override us via --reference-doc in extra_args; pandoc
        # uses the last value, so we always put ours first.
        cmd.extend(["--reference-doc", str(reference_doc)])
    # Verbatim pandoc pass-through comes last so users can override anything.
    cmd.extend(extra_args)
    return subprocess.call(cmd)


# ─────────────────────────────────────────────────────────────────────
# The parsed options, as data
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConvertOptions:
    """Everything :func:`convert` needs, already parsed and typed.

    This replaces the argparse ``Namespace`` the engine used to receive. The
    difference is not cosmetic: a ``Namespace`` is whatever the parser that
    built it happened to set, so the engine read five of these fields through
    ``getattr(args, name, False)`` because the pptx-only flags simply did not
    exist on the docx parser. Three in-tree callers (the CLI, the GUI server,
    the FastAPI app) each had to know the exact flag spellings to build an
    argv the engine would then re-parse, and nothing checked that they agreed.

    A frozen dataclass makes the contract explicit and total: every field is
    present for every format, with the same default the CLI advertises, and a
    caller that forgets one gets a ``TypeError`` rather than a silent False.

    Attributes
    ----------
    input : str
        Path to the source ``.md`` file. The only required field.
    output : str or None
        Destination path. ``None`` means "next to the input, with the target
        format's extension".
    author, lang, date : str or None
        Pandoc metadata overrides. ``date`` is passed as ``date_override`` so
        it does not collide with Pandoc's own ``date``.
    bib : str or None
        BibTeX file; its presence turns on ``--citeproc``.
    bibliography_name : str or None
        Heading for the appended references section. ``None`` resolves to the
        localized default for the document's language.
    lint : bool
        Run the opt-in local-LLM syntax + alt-text pass.
    skip_phase : tuple of str
        Preprocessing phases to skip, by name. Repeatable on the CLI.
    reference_doc : str or None
        Explicit template, overriding the whole resolution chain.
    offline : bool
        Hard kill-switch for every network-touching phase.
    no_remote_templates : bool
        Opt out of the deraison.ai default template only.
    allow_remote_images : bool
        Opt in to downloading ``![](https://…)`` images.
    verbose, quiet : bool
        Logging threshold: DEBUG / ERROR, default INFO.
    smart_layout : bool
        pptx only — map slides onto a designer template's own named layouts.
    template : str or None
        The designer ``.pptx`` that ``smart_layout`` maps onto.
    reference_slides : bool
        ``smart_layout`` only — clone the template's own example pages.
    no_visual_confirm : bool
        ``smart_layout`` only — skip the VLM visual tie-break.
    eyeball_iterations : int
        ``smart_layout`` only — bounded revision passes after assembly.
    """

    input: str
    output: str | None = None
    author: str | None = None
    bib: str | None = None
    bibliography_name: str | None = None
    lang: str | None = None
    date: str | None = None
    lint: bool = False
    skip_phase: tuple[str, ...] = ()
    reference_doc: str | None = None
    offline: bool = False
    no_remote_templates: bool = False
    allow_remote_images: bool = False
    verbose: bool = False
    quiet: bool = False
    # pptx-only, and harmless on the other two formats: `convert` refuses
    # smart_layout for docx/pdf explicitly rather than ignoring it.
    smart_layout: bool = False
    template: str | None = None
    reference_slides: bool = False
    no_visual_confirm: bool = False
    eyeball_iterations: int = 0


# ─────────────────────────────────────────────────────────────────────
# The conversion itself
# ─────────────────────────────────────────────────────────────────────


def convert(fmt: str, opts: ConvertOptions, pandoc_args: Sequence[str] = ()) -> int:
    """Run the full Markdown → .docx/.pptx/.pdf pipeline. Returns the exit code.

    Parameters
    ----------
    fmt : {"docx", "pptx", "pdf"}
        Target format. ``pdf`` renders a DOCX first and hands it to soffice.
    opts : ConvertOptions
        The parsed md2star options. See the dataclass for each field.
    pandoc_args : sequence of str, optional
        Flags md2star does not know, forwarded to Pandoc **verbatim and last**
        so they override anything md2star chose. This is the feature the whole
        tool is built around — ``md2docx report.md --toc`` has to reach Pandoc
        as ``--toc`` — so it is a plain list here rather than something parsed.

    Returns
    -------
    int
        ``0`` on success; a non-zero code (Pandoc's, or soffice's) otherwise.
    """
    # A fresh list: callers pass tuples, and the metadata flags below are
    # appended to it before `_run_pandoc` sees it.
    pandoc_extras = list(pandoc_args)

    # Wire the logging surface first, before any resolver/preprocess step can
    # emit a diagnostic, so --verbose/--quiet take effect for the whole run.
    configure_logging(verbose=opts.verbose, quiet=opts.quiet)

    in_path = Path(opts.input).expanduser().resolve()
    if not in_path.exists():
        raise InvalidInputError(
            _("md2%(fmt)s: input file not found: %(path)s") % {"fmt": fmt, "path": in_path},
            hint="md2star accepts a single .md / .markdown file as the first argument.",
        )

    out_path = (
        Path(opts.output).expanduser().resolve() if opts.output else in_path.with_suffix(f".{fmt}")
    )

    # The destination must not be the source. `md2docx doc.md -o doc.md`
    # replaced a 37-byte Markdown file with a 16 kB DOCX and printed
    # "Wrote: doc.md" as though that were a success: the document the user was
    # converting is gone, and nothing says so. Both paths are already
    # `.resolve()`d above, so `==` settles `doc.md` against `./doc.md` too.
    #
    # The sidecar logic below already avoids stomping an unrelated `.docx` the
    # user might own; this is the same care turned on the input itself.
    if out_path == in_path:
        raise InvalidInputError(
            _("md2%(fmt)s: %(path)s is both the input and the output")
            % {"fmt": fmt, "path": in_path},
            hint=_(
                "Writing the converted file over its own source would destroy "
                "the document. Pass a different --output, or drop --output to "
                "write next to the source with the right extension."
            ),
        )

    # PDF detours through DOCX. The temp DOCX lives next to the requested
    # PDF output so the user's source dir stays clean. We always use a
    # sidecar `.md2star.tmp.docx` name when generating a PDF so we never
    # stomp on a real .docx the user may already have. (An earlier
    # version computed the sidecar only when `out_path.with_suffix(".docx")`
    # already existed, but `Path.samefile(out_path)` raises FileNotFoundError
    # when the PDF doesn't exist yet — a bug only the first invocation
    # would hit.)
    docx_fmt = "docx" if fmt == "pdf" else fmt
    if fmt == "pdf":
        docx_path = out_path.with_suffix(".md2star.tmp.docx")
    else:
        docx_path = out_path

    # 1. Preprocess
    try:
        raw = in_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # Typed, not a traceback: a Latin-1 or UTF-16 source is the user's
        # file, not a bug in md2star, and this module's contract is that a
        # traceback means "please file this". Exit 2 says invalid input.
        raise InvalidInputError(
            _("md2%(fmt)s: %(path)s is not valid UTF-8 (byte %(byte)#04x at offset %(pos)d)")
            % {"fmt": fmt, "path": in_path, "byte": _raw_byte(exc), "pos": exc.start},
            hint=(
                "md2star reads Markdown as UTF-8. Convert the file first, e.g. "
                "`iconv -f latin1 -t utf-8 in.md > out.md`, or re-save it as "
                "UTF-8 from your editor."
            ),
        ) from exc
    processed = preprocess_markdown(
        raw,
        base_dir=str(in_path.parent),
        lint_enabled=opts.lint,
        skip_phases=list(opts.skip_phase),
        allow_remote_images=opts.allow_remote_images,
        offline=opts.offline,
    )

    # 1b. Template-intelligent PPTX detour: bypasses Pandoc AND the whole
    #     reference-doc/metadata block below entirely (checked here, before
    #     either does any work, so --smart-layout never triggers a wasted
    #     remote-template fetch it would just discard). The CLI only offers
    #     --smart-layout/--template on `md2star pptx`; the fields exist for
    #     every format so this reads as a plain attribute, and
    #     _convert_smart_layout refuses a non-pptx fmt out loud.
    if opts.smart_layout:
        return _convert_smart_layout(fmt, in_path, out_path, processed, opts)
    if opts.reference_slides:
        # Said out loud rather than ignored: the Pandoc path has no notion of
        # the template's example pages, so a run that asked for them and got a
        # perfectly ordinary deck would look like the flag did nothing.
        raise InvalidInputError(
            "md2pptx: --reference-slides only applies to --smart-layout",
            hint="Add --smart-layout --template <designer.pptx>, or drop --reference-slides.",
        )

    # Build the pandoc metadata / flag list from our high-level options. Each
    # is appended only when supplied, so unset options fall back to the
    # template / metadata.yaml defaults rather than injecting empty values.
    if opts.author:
        pandoc_extras.extend(["--metadata", f"author={opts.author}"])
    if opts.lang:
        pandoc_extras.extend(["--metadata", f"lang={opts.lang}"])
    if opts.date:
        # The Lua filter checks meta.date_override before falling back
        # to the auto-localized date_format path; using our own key
        # avoids colliding with Pandoc's own ``date`` metadata.
        pandoc_extras.extend(["--metadata", f"date_override={opts.date}"])
    if opts.bib:
        pandoc_extras.extend(["--citeproc", "--bibliography", opts.bib])

    # Reference doc: explicit override > auto-detection.
    # For PDF we look up the DOCX template since that is what feeds soffice.
    reference_doc: Path | None
    if opts.reference_doc:
        reference_doc = Path(opts.reference_doc).expanduser().resolve()
    else:
        # Remote templates are the default since v2.5.0; --no-remote-templates
        # (and the hard --offline switch, handled inside the resolver) opt out.
        reference_doc = _resolve_reference_doc(
            in_path,
            docx_fmt,
            allow_remote_templates=not opts.no_remote_templates,
            offline=opts.offline,
        )

    # 2. Append the bibliography heading if requested. We do this on the
    #    preprocessed text rather than the source so the user's source file
    #    is never mutated. The heading text defaults to the localized
    #    "Bibliography" for the document's detected language (or the
    #    explicit --lang) — `opts.bibliography_name` is None unless the
    #    user supplied it.
    if opts.bib:
        heading = opts.bibliography_name or _localized_bibliography_heading(
            raw,
            opts.lang,
        )
        processed = f"{processed}\n\n# {heading}\n"

    # 3. Write the preprocessed Markdown to a temp file in the SAME dir as
    #    the input so any relative image paths still resolve. os_helper's
    #    temporary_filename(directory=...) owns creation + cleanup of the file.
    # Entered through an ExitStack rather than a plain `with` so the failure
    # to *create* the file can be told apart from anything pandoc raises
    # inside the block — only the former means "this directory is read-only".
    stack = contextlib.ExitStack()
    try:
        temp_name = stack.enter_context(
            osh.temporary_filename(
                suffix=".md", prefix=".preprocessed_", directory=str(in_path.parent)
            )
        )
    except OSError as exc:
        raise InvalidInputError(
            _("md2%(fmt)s: cannot write a working file next to %(path)s (%(reason)s)")
            % {"fmt": fmt, "path": in_path.name, "reason": exc.strerror or exc},
            hint=(
                "The preprocessed Markdown is written beside the input so "
                "relative image paths keep resolving, which needs a writable "
                "source directory. Copy the Markdown somewhere writable and "
                "convert it there."
            ),
        ) from exc
    with stack:
        temp_path = Path(temp_name)
        Path(temp_path).write_text(processed, encoding="utf-8")

        # 4. Run pandoc → DOCX (always, even for PDF).
        rc = _run_pandoc(docx_fmt, temp_path, docx_path, reference_doc, pandoc_extras)
        if rc != 0:
            return rc

    # 5. DOCX-only postprocess: re-inject MyTable / MyTableSmall styles, then
    #    centre standalone (non-table) images — Pandoc leaves them left-aligned.
    #    Both run for the DOCX and the PDF (which builds from this same DOCX).
    if docx_fmt == "docx":
        try:
            inject_table_styles(str(docx_path))
        except Exception as exc:
            logger.warning(
                f"md2star warning: postprocess failed ({exc}); the .docx is otherwise complete."
            )
        try:
            center_standalone_images(str(docx_path))
        except Exception as exc:
            logger.warning(
                f"md2star warning: image-centring pass failed ({exc}); "
                "images will render left-aligned."
            )

    # 6. PDF-only: shell out to headless LibreOffice. The intermediate
    #    DOCX is correct as-is for Word, but the bundled template's
    #    ``TableNormal0`` style triggers a soffice render bug where
    #    cells leak out of the table. We mutate the intermediate
    #    DOCX (zip-level) to drop ``TableNormal0`` so soffice falls
    #    back to its default table rendering. The user's actual DOCX
    #    output (md2docx) is never touched. Documented in
    #    CHANGELOG v1.1.1 + v2.0.0.
    if fmt == "pdf":
        try:
            strip_table_normal_for_pdf(str(docx_path))
        except Exception as exc:
            logger.warning(
                f"md2star warning: TableNormal0 strip failed ({exc}); "
                "PDF tables may render with empty cells."
            )
        rc = _convert_docx_to_pdf(docx_path, out_path)
        # Always remove the intermediate DOCX — the user asked for a PDF.
        docx_path.unlink(missing_ok=True)
        if rc != 0:
            return rc

    print(_("Wrote: %(path)s") % {"path": out_path})
    return 0


def _mermaid_renderer(out_dir: Path):
    """Build a ``str -> Path | None`` Mermaid renderer for the smart-layout
    assembler, or ``None`` when the Mermaid toolchain module can't be
    imported (never fatal — Mermaid slides then degrade to title-only)."""
    try:
        from .preprocessing.mermaid import render_mermaid_local  # noqa: PLC0415
    except ImportError:
        return None

    def _render(src: str) -> Path | None:
        try:
            return Path(render_mermaid_local(src, out_dir=str(out_dir)))
        except Exception as exc:  # noqa: BLE001 — degrade to title-only slide
            logger.debug("smart-layout: mermaid render failed: %s", exc)
            return None

    return _render


def _convert_smart_layout(
    fmt: str, in_path: Path, out_path: Path, processed: str, opts: ConvertOptions
) -> int:
    """Route ``md2pptx --smart-layout`` through the AI layout assembler.

    Bypasses Pandoc and the whole reference-doc pipeline: ``--template``
    (the designer's own PPTX) plays the role a Pandoc reference-doc normally
    plays. See :mod:`md2star.pptx_layout` / :mod:`md2star.pptx_assemble` for
    the catalog/selection/assembly/eyeball-loop stages this wires together.
    """
    if fmt != "pptx":
        raise InvalidInputError(
            _("md2%(fmt)s: --smart-layout is only valid for pptx") % {"fmt": fmt}
        )
    if not opts.template:
        raise InvalidInputError(
            "md2pptx --smart-layout: --template <designer.pptx> is required",
            hint="Point --template at the designer's own PPTX, not md2star's bundled template.",
        )
    template = Path(opts.template).expanduser().resolve()
    if not template.exists():
        raise InvalidInputError(_("md2pptx: template not found: %(path)s") % {"path": template})

    try:
        import pptx  # noqa: F401, PLC0415 — optional dep, probed here for a clear error
    except ImportError as exc:
        raise Md2starError(
            "md2pptx --smart-layout needs python-pptx: pip install 'md2star[pptx]'"
        ) from exc

    from .pptx_assemble import assemble, eyeball_slides  # noqa: PLC0415
    from .pptx_layout import (  # noqa: PLC0415
        build_catalog,
        segment,
        select_layouts,
        smart_layout_available,
        visual_confirm,
    )

    if not smart_layout_available():
        raise Md2starError(
            "md2pptx --smart-layout needs a resolved LLM+VLM engine; run "
            '`best-engine-ai-helper report --task "..."` or check '
            "md2star/llm.engine.yaml for what best-engine-ai-helper resolved."
        )

    slides = segment(processed)
    if not slides:
        raise InvalidInputError(_("md2pptx: no slides found in %(path)s") % {"path": in_path})

    logger.info("smart-layout: cataloging %s", template)
    catalog = build_catalog(template)
    logger.info("smart-layout: selecting layouts for %d slides", len(slides))
    # The template gives the canvas for the compositional checks; the source
    # directory is where relative image paths resolve, so the aspect check can
    # read real dimensions rather than guess from a count.
    select_layouts(slides, catalog, template=template, image_base_dir=in_path.parent)
    if not opts.no_visual_confirm:
        logger.info("smart-layout: visual tie-break")
        visual_confirm(slides, catalog, template=template)

    render_mermaid = _mermaid_renderer(out_path.parent)
    reference_slides = opts.reference_slides
    if opts.eyeball_iterations > 0:
        result = eyeball_slides(
            slides,
            catalog,
            template,
            out_path,
            max_iterations=opts.eyeball_iterations,
            image_base_dir=in_path.parent,
            render_mermaid=render_mermaid,
            reference_slides=reference_slides,
        )
    else:
        result = assemble(
            slides,
            catalog,
            template,
            out_path,
            image_base_dir=in_path.parent,
            render_mermaid=render_mermaid,
            reference_slides=reference_slides,
        )
    # Never `_("")`: the empty msgid is a catalogue's own metadata header, and
    # translating it would hand the user the Content-Type of the .mo file.
    note = (
        _(", %(cloned)d from the template's own pages") % {"cloned": result.cloned}
        if result.cloned
        else ""
    )
    print(
        _("Wrote: %(path)s (%(placed)d/%(total)d slides%(note)s)")
        % {
            "path": result.pptx_path,
            "placed": result.placed,
            "total": result.total,
            "note": note,
        }
    )
    if reference_slides and not result.cloned:
        # Asked for and silently not delivered is the worst outcome here: the
        # flag is only ever as good as the template's example pages, and a
        # template distributed as layouts alone has none to clone.
        logger.warning(
            "--reference-slides: no example page in %s could carry a slide; "
            "every slide was built on its bare layout",
            template.name,
        )
    # Deterministic last word on the deck we just wrote. Runs whatever the AI
    # stages did or could not do — no model, no render — so a conversion on a
    # machine with no VLM still reports whether anything overlaps, bleeds off
    # the canvas, or needs type nobody can read. See md2star/pptx_audit.py.
    from .pptx_audit import audit, log_findings, summarise  # noqa: PLC0415

    findings = audit(result.pptx_path)
    log_findings(findings)
    print(summarise(findings, slides=result.total))
    return 0


# ─────────────────────────────────────────────────────────────────────
# PDF helper — headless LibreOffice (soffice) bridge
# ─────────────────────────────────────────────────────────────────────


def _find_soffice() -> str | None:
    """Return the absolute path to ``soffice``, or None if not found.

    Looks first on ``PATH`` (covers Homebrew / Linux package installs),
    then in the standard macOS LibreOffice.app bundle location.
    """
    path = shutil.which("soffice") or shutil.which("libreoffice")
    if path:
        return path
    mac_app = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.exists(mac_app):
        return mac_app
    return None


def _soffice_profile() -> Path:
    """The LibreOffice user profile md2star converts under.

    LibreOffice keeps one profile per ``UserInstallation`` and locks it. A
    second ``soffice`` told to use a profile that is already held does not
    fail loudly — it **exits 0, writes no document and prints nothing**
    (measured), which is the least debuggable outcome available. Since the
    default profile is the one the user's own LibreOffice holds whenever it
    is open, converting under it means every PDF depends on whether the user
    happens to have the app running.

    So we convert under our own, kept in the cache rather than created per
    run: a fresh profile costs about 1.4s to bootstrap (measured, roughly
    doubling a 1.5s conversion), and the GUI's live preview pays that on
    every render. Two concurrent md2star runs can still meet on this one,
    which is what the throwaway-profile retry in :func:`_convert_docx_to_pdf`
    is for.
    """
    return cache_dir("soffice-profile")


def _convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> int:
    """Render *docx_path* to *pdf_path* via headless LibreOffice. Returns rc."""
    soffice = _find_soffice()
    if soffice is None:
        raise MissingDependencyError(
            "md2pdf: LibreOffice (`soffice`) not found",
            hint=(
                "Install it to enable PDF output:\n"
                "  macOS:   brew install --cask libreoffice\n"
                "  Ubuntu:  sudo apt install libreoffice\n"
                "  Windows: winget install --id TheDocumentFoundation.LibreOffice\n"
                "  other:   https://www.libreoffice.org/download/"
            ),
        )

    # soffice writes a sibling file next to the input — we cannot control
    # the exact output name, only its directory. We render into a tempdir
    # and move the result to the user's requested path so the API stays
    # "input → output" with no surprises.
    with osh.temporary_folder(prefix="md2pdf-") as workdir:
        # First attempt uses md2star's own persistent profile (see
        # _soffice_profile); the second a throwaway one, which cannot be
        # contended by definition. Contention does not announce itself the
        # same way twice — measured, it is either "exit 0, no document, no
        # message" or a DeploymentException on exit 1 — so the retry is keyed
        # on the only thing that matters, whether a PDF exists.
        produced = Path(workdir) / (docx_path.stem + ".pdf")
        last_rc, last_stderr = 1, ""
        for attempt, profile in enumerate((_soffice_profile(), Path(workdir) / "profile")):
            cmd = [
                soffice,
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                workdir,
                str(docx_path),
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                # Not retried: a second 120s wait to reach the same verdict
                # helps nobody.
                logger.error("md2pdf: LibreOffice timed out after 120s.")
                return 1
            last_rc = proc.returncode
            last_stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            if last_rc == 0 and produced.exists():
                break
            if attempt == 0:
                # Debug, not warning: the retry normally wins, and a line about
                # LibreOffice internals on a conversion that then succeeded is
                # noise. It is here at all because this silence is what made
                # the symptom unreadable before.
                logger.debug(
                    "md2pdf: LibreOffice produced no %s (exit %d); "
                    "retrying in a throwaway profile.",
                    produced.name,
                    last_rc,
                )

        if not produced.exists():
            if last_rc != 0:
                logger.error(f"md2pdf: LibreOffice exited {last_rc}: {last_stderr}")
                return last_rc
            logger.error(
                f"md2pdf: LibreOffice did not produce {produced.name}, "
                f"even in a private profile. stderr: {last_stderr!r}"
            )
            return 1

        osh.make_directory(str(pdf_path.parent))
        shutil.move(str(produced), str(pdf_path))
    return 0
