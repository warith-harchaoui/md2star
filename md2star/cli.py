"""md2star command-line interface.

This module replaces the legacy heredoc'd shell wrappers (``scripts/install.sh``
used to write ``~/.local/bin/md2docx`` and ``~/.local/bin/md2pptx`` directly).
Now there is exactly one source of truth — this file — and four console
entry points (registered in ``pyproject.toml`` ``[project.scripts]``):

* ``md2docx <input.md> [options...]``     → :func:`md2docx_main`
* ``md2pptx <input.md> [options...]``     → :func:`md2pptx_main`
* ``md2pdf  <input.md> [options...]``     → :func:`md2pdf_main`
* ``md2star <subcommand> [options...]``   → :func:`main`

The subcommand form (``md2star docx`` / ``md2star pptx`` / ``md2star pdf``)
is the canonical spelling; the ``md2docx`` / ``md2pptx`` / ``md2pdf`` aliases
exist so users do not have to relearn anything.

The CLI is intentionally thin: it parses md2star-specific flags, forwards
everything else verbatim to pandoc, and orchestrates the four-step pipeline:

1. **Preprocess** the input Markdown via :func:`md2star.preprocess_markdown`.
2. **Resolve the reference template**: prefer ``template.{docx,pptx}`` next
   to the input file, then the legacy ``.pandoc-reference.{docx,pptx}``,
   then the XDG cache, then (the default since v2.5.0) a one-shot fetch
   from ``deraison.ai`` cached under XDG, and finally the bundled template.
   ``--no-remote-templates`` / ``--offline`` skip the fetch.
3. **Invoke pandoc** with the bundled Lua filter, metadata defaults, and
   resolved reference doc.
4. **Postprocess** (DOCX only) — re-inject the ``MyTable`` / ``MyTableSmall``
   table styles that Pandoc strips when rewriting ``word/styles.xml``.

The PDF format is implemented as a wrapper: it produces the DOCX first
(so all the md2star polish — mermaid, table styles, slide-aware tweaks —
applies) and then asks headless LibreOffice (``soffice --headless
--convert-to pdf``) to render that DOCX to PDF. This guarantees the PDF
visually matches the DOCX you would ship.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

import os_helper as osh

from . import __version__
from .cache import cache_dir, clear_cache
from .errors import (
    InvalidInputError,
    Md2starError,
    MissingDependencyError,
)
from .logging import configure as configure_logging
from .logging import get_logger
from .postprocess import inject_table_styles, strip_table_normal_for_pdf
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
            f"md2star: '.pandoc-reference.{fmt}' is deprecated; "
            f"rename it to 'template.{fmt}'."
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
            logger.info(
                f"md2star: cached default template from {url} → {cached}"
            )
            return cached
        except Exception as exc:
            # Leave no partial file behind.
            cached.unlink(missing_ok=True)
            logger.warning(
                f"md2star: template download failed ({exc}); "
                "falling back to the bundled default."
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
        "-o", str(output),
        "-t", fmt,
        "--lua-filter", str(_data_path("filters", "md2star.lua")),
        "--metadata-file", str(_data_path("metadata.yaml")),
    ]
    if reference_doc is not None:
        # The user can override us via --reference-doc in extra_args; pandoc
        # uses the last value, so we always put ours first.
        cmd.extend(["--reference-doc", str(reference_doc)])
    # Verbatim pandoc pass-through comes last so users can override anything.
    cmd.extend(extra_args)
    return subprocess.call(cmd)


# ─────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────


_FORMAT_HELP = {
    "docx": "Microsoft Word (.docx)",
    "pptx": "Microsoft PowerPoint (.pptx)",
    "pdf":  "Portable Document Format (.pdf, via headless LibreOffice)",
}


def _make_format_parser(fmt: str) -> argparse.ArgumentParser:
    """Build the per-format parser used by ``md2docx`` / ``md2pptx``."""
    parser = argparse.ArgumentParser(
        prog=f"md2{fmt}",
        description=f"Markdown → {_FORMAT_HELP[fmt]} via md2star + Pandoc.",
        epilog=(
            "Unknown flags are forwarded to pandoc verbatim. "
            "Run `pandoc --help` for the full list."
        ),
        add_help=True,
    )
    # ── Positional + output ───────────────────────────────────────────
    parser.add_argument("input", help="Path to the input .md file.")
    parser.add_argument(
        "-o", "--output",
        help="Output path (default: <input>.<fmt>).",
    )
    # ── Document metadata forwarded to Pandoc ─────────────────────────
    parser.add_argument("--author", help="Document author (Pandoc metadata).")
    parser.add_argument(
        "--bib",
        help="Bibliography file (BibTeX). Enables --citeproc automatically.",
    )
    parser.add_argument(
        "--bibliography-name",
        default=None,    # resolved below to the language-detected value
        help=("Heading inserted before the bibliography. When omitted, "
              "md2star uses the localized default for the document's "
              "language ('Bibliography' / 'Bibliographie' / 'Bibliografía' "
              "/ 'Literatur' / 'Bibliografia' / 'Bibliografie' / "
              "'Библиография' / fallback 'Bibliography')."),
    )
    parser.add_argument("--lang", help="Document language metadata (BCP 47, e.g. en-US).")
    parser.add_argument(
        "--date",
        help=("Override the auto-generated date in the subtitle. The string "
              "you pass is used verbatim (e.g. '21 juin 2026', '2026-Q2', "
              "'submitted 14 March'). When omitted, md2star formats today's "
              "date via the language-aware `date_format` metadata."),
    )

    # ── Lint toggle (mutually exclusive so --lint/--no-lint can't clash) ─
    lint_group = parser.add_mutually_exclusive_group()
    lint_group.add_argument(
        "--lint", action="store_true",
        help=(
            "Opt in to the Ollama LLM linter (off by default). Also fills "
            "empty image alt text with a vision-model description, using the "
            "model chosen by best-engine-ai-helper (override: "
            "MD2STAR_ALT_TEXT_MODEL)."
        ),
    )
    lint_group.add_argument(
        "--no-lint", action="store_true",
        help="Explicit no-op (same as the default).",
    )

    parser.add_argument(
        "--skip-phase", action="append", default=[], metavar="NAME",
        help=(
            "Skip a preprocessing phase. Repeatable. Known phases: "
            "lint, remote_images, html_tables, html_images, absolutize, "
            "image_assets, language, line_pass, table_resize, "
            "table_normalize, image_widths, pptx_isolation."
        ),
    )
    parser.add_argument(
        "--reference-doc",
        help="Override the auto-detected reference template.",
    )

    # ── Network policy (offline-by-default since v1.2.0) ──────────
    parser.add_argument(
        "--offline", action="store_true",
        help=("Forbid every network-touching phase (overrides "
              "--allow-remote-*). Useful for air-gapped runs and to "
              "make the refusal explicit in scripts."),
    )
    parser.add_argument(
        "--no-remote-templates", action="store_true",
        help=("Opt OUT of the deraison.ai default template. Since "
              "v2.5.0 md2star fetches https://deraison.ai/template."
              "{docx,pptx} whenever no local template.{docx,pptx} is "
              "found, caching it under XDG. Pass this (or --offline) "
              "to skip the fetch and use the bundled template."),
    )
    parser.add_argument(
        # Back-compat no-op: remote templates are now the default, so the
        # old opt-in flag has nothing left to enable. Accepted silently so
        # existing scripts/CI that still pass it don't error out.
        "--allow-remote-templates", action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--allow-remote-images", action="store_true",
        help=("Opt in to downloading ``![](https://...)`` images "
              "referenced in the markdown. Off by default — the "
              "preprocessor leaves remote refs in place and warns "
              "once on stderr when any were skipped."),
    )
    # ── Verbosity (routes md2star's own diagnostics through logging) ──
    # Mutually exclusive: --verbose lowers the threshold to DEBUG, --quiet
    # raises it to ERROR. The default (neither) is INFO, which preserves the
    # pre-logging behaviour where every diagnostic printed unconditionally.
    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "-v", "--verbose", action="store_true",
        help="Show debug-level diagnostics on stderr.",
    )
    verbosity_group.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress info + warnings; only errors reach stderr.",
    )

    parser.add_argument(
        "-V", "--version", action="version",
        version=f"md2star {__version__}",
    )
    return parser


def _split_known(parser: argparse.ArgumentParser, argv: list[str]):
    """Parse known args, return ``(namespace, extras_for_pandoc)``."""
    return parser.parse_known_args(argv)


# ─────────────────────────────────────────────────────────────────────
# Per-format entry points
# ─────────────────────────────────────────────────────────────────────


def _convert(fmt: str, argv: list[str]) -> int:
    """Run the full Markdown → .docx/.pptx/.pdf pipeline. Returns the exit code."""
    parser = _make_format_parser(fmt)
    args, pandoc_extras = _split_known(parser, argv)

    # Wire the logging surface first, before any resolver/preprocess step can
    # emit a diagnostic, so --verbose/--quiet take effect for the whole run.
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    in_path = Path(args.input).expanduser().resolve()
    if not in_path.exists():
        raise InvalidInputError(
            f"md2{fmt}: input file not found: {in_path}",
            hint="md2star accepts a single .md / .markdown file as the first argument.",
        )

    out_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else in_path.with_suffix(f".{fmt}")
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

    # Build the pandoc metadata / flag list from our high-level options. Each
    # is appended only when supplied, so unset options fall back to the
    # template / metadata.yaml defaults rather than injecting empty values.
    if args.author:
        pandoc_extras.extend(["--metadata", f"author={args.author}"])
    if args.lang:
        pandoc_extras.extend(["--metadata", f"lang={args.lang}"])
    if args.date:
        # The Lua filter checks meta.date_override before falling back
        # to the auto-localized date_format path; using our own key
        # avoids colliding with Pandoc's own ``date`` metadata.
        pandoc_extras.extend(["--metadata", f"date_override={args.date}"])
    if args.bib:
        pandoc_extras.extend(["--citeproc", "--bibliography", args.bib])

    # Reference doc: explicit override > auto-detection.
    # For PDF we look up the DOCX template since that is what feeds soffice.
    reference_doc: Path | None
    if args.reference_doc:
        reference_doc = Path(args.reference_doc).expanduser().resolve()
    else:
        # Remote templates are the default since v2.5.0; --no-remote-templates
        # (and the hard --offline switch, handled inside the resolver) opt out.
        reference_doc = _resolve_reference_doc(
            in_path, docx_fmt,
            allow_remote_templates=not args.no_remote_templates,
            offline=args.offline,
        )

    # 1. Preprocess
    raw = in_path.read_text(encoding="utf-8")
    processed = preprocess_markdown(
        raw,
        base_dir=str(in_path.parent),
        lint_enabled=args.lint,
        skip_phases=args.skip_phase,
        allow_remote_images=args.allow_remote_images,
        offline=args.offline,
    )

    # 2. Append the bibliography heading if requested. We do this on the
    #    preprocessed text rather than the source so the user's source file
    #    is never mutated. The heading text defaults to the localized
    #    "Bibliography" for the document's detected language (or the
    #    explicit --lang) — `args.bibliography_name` is None unless the
    #    user supplied it.
    if args.bib:
        heading = args.bibliography_name or _localized_bibliography_heading(
            raw, args.lang,
        )
        processed = f"{processed}\n\n# {heading}\n"

    # 3. Write the preprocessed Markdown to a temp file in the SAME dir as
    #    the input so any relative image paths still resolve. os_helper's
    #    temporary_filename(directory=...) owns creation + cleanup of the file.
    with osh.temporary_filename(
        suffix=".md", prefix=".preprocessed_", directory=str(in_path.parent)
    ) as temp_name:
        temp_path = Path(temp_name)
        Path(temp_path).write_text(processed, encoding="utf-8")

        # 4. Run pandoc → DOCX (always, even for PDF).
        rc = _run_pandoc(docx_fmt, temp_path, docx_path, reference_doc, pandoc_extras)
        if rc != 0:
            return rc

    # 5. DOCX-only postprocess: re-inject MyTable / MyTableSmall styles.
    if docx_fmt == "docx":
        try:
            inject_table_styles(str(docx_path))
        except Exception as exc:
            logger.warning(
                f"md2star warning: postprocess failed ({exc}); "
                "the .docx is otherwise complete."
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

    print(f"Wrote: {out_path}")
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
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", workdir,
            str(docx_path),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=120, check=False,
            )
        except subprocess.TimeoutExpired:
            logger.error("md2pdf: LibreOffice timed out after 120s.")
            return 1
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            logger.error(
                f"md2pdf: LibreOffice exited {proc.returncode}: {stderr}"
            )
            return proc.returncode

        produced = Path(workdir) / (docx_path.stem + ".pdf")
        if not produced.exists():
            logger.error(
                f"md2pdf: LibreOffice did not produce {produced.name}. "
                f"stderr: {proc.stderr.decode(errors='replace')!r}"
            )
            return 1
        osh.make_directory(str(pdf_path.parent))
        shutil.move(str(produced), str(pdf_path))
    return 0


def _render_error(exc: Md2starError) -> None:
    """Pretty-print a typed exception to stderr — headline + indented hint.

    Replaces the raw Python traceback with a two-block message:

        md2star: <headline error>
          <hint, indented and word-wrapped at the natural newlines>

    Called by the top-level handler in each ``md2{docx,pptx,pdf}_main``
    so users see actionable text instead of a traceback when the
    failure mode is something we already anticipated (see
    :mod:`md2star.errors`).
    """
    # Headline goes at error level; each hint line is emitted separately so
    # the "%(message)s" formatter keeps the original two-block, indented
    # layout (no per-line "md2star:" prefix on the wrapped hint).
    logger.error(f"md2star: {exc}")
    if exc.hint:
        for line in exc.hint.splitlines():
            logger.error(f"  {line}")


def _run_format(fmt: str, argv: list[str] | None) -> int:
    """Top-level wrapper around :func:`_convert` for the four console entries.

    Catches every :class:`Md2starError` subclass and renders it via
    :func:`_render_error`, returning a non-zero exit code. Anything
    that doesn't subclass :class:`Md2starError` is left to bubble up
    as a Python traceback — that's a real bug we want users to file.
    """
    try:
        return _convert(fmt, list(sys.argv[1:] if argv is None else argv))
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


def md2docx_main(argv: list[str] | None = None) -> int:
    """Console entry point: ``md2docx``."""
    return _run_format("docx", argv)


def md2pptx_main(argv: list[str] | None = None) -> int:
    """Console entry point: ``md2pptx``."""
    return _run_format("pptx", argv)


def md2pdf_main(argv: list[str] | None = None) -> int:
    """Console entry point: ``md2pdf``."""
    return _run_format("pdf", argv)


# ─────────────────────────────────────────────────────────────────────
# Top-level ``md2star`` entry point
# ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Console entry point: ``md2star <subcommand>``.

    Subcommands:

    * ``docx`` / ``pptx`` / ``pdf`` — convert (same flags as the standalone
      aliases ``md2docx`` / ``md2pptx`` / ``md2pdf``).
    * ``gui`` — launch the local Overleaf-style Markdown → PDF editor.
    * ``doctor`` — print an environment diagnostic.
    * ``cache-dir`` — print the resolved cache directory path.
    * ``clear-cache`` — wipe the cache directory.
    """
    argv = list(sys.argv[1:] if argv is None else argv)

    # Install the logging handler with defaults so the dispatch-level paths
    # below (unknown subcommand, etc.) have a stderr sink. The conversion
    # subcommands re-invoke configure() with their parsed --verbose/--quiet;
    # configure() is idempotent, so that just updates the level.
    configure_logging()

    # No args or -h → help; -V → version. Both are terminal, exit 0.
    if not argv or argv[0] in ("-h", "--help"):
        _print_top_level_help()
        return 0
    if argv[0] in ("-V", "--version"):
        # Version is program output → stdout via print, not the logger.
        print(f"md2star {__version__}")
        return 0

    # First token selects the subcommand; the rest is its own argv.
    sub, rest = argv[0], argv[1:]

    # Conversion subcommands delegate to the same entry points the standalone
    # md2docx/md2pptx/md2pdf console scripts use — one code path, no drift.
    if sub == "docx":
        return md2docx_main(rest)
    if sub == "pptx":
        return md2pptx_main(rest)
    if sub == "pdf":
        return md2pdf_main(rest)
    # Non-conversion subcommands import lazily so a plain ``md2docx`` run never
    # pays the import cost of doctor/templates it won't use.
    if sub == "doctor":
        from .doctor import main as doctor_main
        return doctor_main(rest)
    if sub == "templates":
        from .templates import main as templates_main
        return templates_main(rest)
    if sub == "twin":
        # Reverse direction: any document → an editable Markdown twin. Lazy
        # import so a plain forward conversion never loads Kreuzberg/AI code.
        from .twin_cli import main as twin_main
        return twin_main(rest)
    if sub == "gui":
        # The GUI ships its ~4 MB vendored frontend (PDF.js, CodeMirror,
        # Tailwind, fonts) inside md2star/data/gui/. Import is lazy so a
        # plain md2docx run never pays for the http.server machinery.
        from .gui_server import main as gui_main
        return gui_main(rest)
    # cache-dir / clear-cache both emit their result to stdout (script-friendly).
    if sub == "cache-dir":
        print(cache_dir())
        return 0
    if sub == "clear-cache":
        freed = clear_cache()
        print(f"md2star: cleared cache ({freed / 1024:.1f} KiB freed)")
        return 0

    logger.error(f"md2star: unknown subcommand {sub!r}")
    # Help text (not a diagnostic) still goes straight to stderr via print.
    _print_top_level_help(file=sys.stderr)
    return 2


def _print_top_level_help(file=sys.stdout) -> None:
    """Print the top-level usage banner for the ``md2star`` dispatcher.

    Parameters
    ----------
    file : TextIO, optional
        Stream the banner is written to. Defaults to ``sys.stdout``; the
        error path passes ``sys.stderr`` so the help does not contaminate a
        piped stdout payload.
    """
    print(
        f"md2star {__version__} — Markdown → DOCX/PPTX/PDF bridge\n\n"
        "Usage:\n"
        "  md2star docx <input.md> [options...]\n"
        "  md2star pptx <input.md> [options...]\n"
        "  md2star pdf  <input.md> [options...]\n"
        "  md2star gui  [--port N] [--no-browser] [--bind ADDR]\n"
        "  md2star twin <input.(pdf|docx|pptx|...)> [--out DIR] [--diagrams]\n"
        "  md2star doctor [--json]\n"
        "  md2star templates {list,path} [...]\n"
        "  md2star cache-dir\n"
        "  md2star clear-cache\n\n"
        "Shorthand aliases:\n"
        "  md2docx <input.md> [options...]\n"
        "  md2pptx <input.md> [options...]\n"
        "  md2pdf  <input.md> [options...]\n\n"
        "Run `md2docx --help` (or md2pptx/md2pdf) for full per-format options.",
        file=file,
    )


if __name__ == "__main__":
    sys.exit(main())
