"""``md2star twin`` — read any document back into an editable Markdown twin.

The forward path turns Markdown into a polished DOCX/PPTX/PDF. This is the
inverse *as a document*, not just as text: given a PDF (or anything LibreOffice
can convert to one), it recovers prose + GFM tables, scrapes every embedded
raster back out as PNGs, and — with ``--diagrams`` — re-authors node-and-edge
figures as Mermaid via the target-matching eyeball loop. The result is a
``<stem>.md`` plus an ``assets/`` folder you can edit and re-render.

Thin argparse adapter over :func:`md2star.reverse.to_markdown_twin` and
:func:`md2star.reverse_diagrams.make_diagram_handler`; kept out of
:mod:`md2star.cli` so the reverse feature imports lazily and the dispatcher
stays small.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import Md2starError
from .logging import configure as configure_logging
from .logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the ``md2star twin`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="md2star twin",
        description="Read a document back into an editable Markdown twin "
        "(prose + tables + scraped images; optional Mermaid diagrams).",
    )
    # The single positional: any PDF, or a format LibreOffice can print to PDF.
    parser.add_argument("input", help="Document to recover (PDF, or convertible to one).")
    # Output folder rather than a file: the twin is a .md *plus* an assets/ dir,
    # so callers point at a directory and we own the two names inside it.
    parser.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help="Output folder for <stem>.md + assets/ (default: the input's folder).",
    )
    # Escape hatch to the classic text-only recovery (no rasters written).
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Recover prose + tables only; drop scraped rasters.",
    )
    # The one flag that pulls in the AI stack; off by default so the twin stays
    # deterministic and dependency-light unless the user asks for reconstruction.
    parser.add_argument(
        "--diagrams",
        action="store_true",
        help="Re-author figures via the local VLM eyeball loop — node-and-edge "
        "diagrams as Mermaid, other vector figures as SVG (needs the [ai] stack "
        "+ a running Ollama).",
    )
    # Model override; when absent the suite picker (best-engine) chooses per host.
    parser.add_argument(
        "--model",
        metavar="TAG",
        default=None,
        help="Vision model tag for --diagrams (default: the suite picker's choice).",
    )
    # Cap on render→compare→revise cycles so a stubborn diagram can't spin forever.
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        metavar="N",
        help="Eyeball-loop budget per diagram (default: 3).",
    )
    # Standard verbosity pair, wired through the shared logging configuration.
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Warnings and errors only.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Console entry point for ``md2star twin``. Returns a process exit code."""
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    src = Path(args.input)
    # Default the output next to the input so a bare ``md2star twin report.pdf``
    # drops ``report.md`` + ``assets/`` right where the source lives.
    out_dir = Path(args.out) if args.out else (src.parent if src.parent != Path("") else Path("."))

    # Only build the AI handler when --diagrams is requested; without it the twin
    # is fully deterministic and needs neither Ollama nor best-engine.
    image_handler = None
    if args.diagrams:
        from .reverse_diagrams import diagrams_available, make_diagram_handler

        if not diagrams_available(args.model):
            # Don't fail the whole run — warn and continue with plain PNGs, since
            # the deterministic twin is still valuable without reconstruction.
            logger.warning(
                "md2star twin: --diagrams requested but the AI stack is unavailable "
                "(Ollama not installed/running, or the model isn't pulled); "
                "keeping scraped images as PNGs."
            )
        else:
            image_handler = make_diagram_handler(
                model=args.model, max_iterations=args.max_iterations
            )

    try:
        from .reverse import to_markdown_twin

        md_path = to_markdown_twin(
            src,
            out_dir,
            extract_images=not args.no_images,
            image_handler=image_handler,
        )
    except FileNotFoundError as exc:
        logger.error("md2star twin: %s", exc)
        return 2
    except Md2starError as exc:
        # Typed errors (e.g. LibreOffice missing for a non-native input) carry a
        # headline + hint; surface both without a traceback.
        logger.error("md2star twin: %s", exc)
        if getattr(exc, "hint", None):
            logger.error("  %s", exc.hint)
        return 127
    except RuntimeError as exc:
        logger.error("md2star twin: %s", exc)
        return 1
    else:
        # Program output → stdout so the path is pipeable; logs went to stderr.
        print(md_path)
        return 0


if __name__ == "__main__":  # pragma: no cover - module executed via md2star twin
    sys.exit(main())
