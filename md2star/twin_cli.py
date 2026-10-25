"""``md2star twin``: read any document back into an editable Markdown twin.

The forward path turns Markdown into a polished DOCX/PPTX/PDF. This is the
inverse *as a document*, not just as text: given a PDF (or anything LibreOffice
can convert to one), it recovers prose + GFM tables, scrapes every embedded
raster back out as PNGs, and (with ``--diagrams``) re-authors node-and-edge
figures as Mermaid via the target-matching eyeball loop. The result is a
``<stem>.md`` plus an ``assets/`` folder you can edit and re-render.

Thin adapter over :func:`md2star.reverse.to_markdown_twin` and
:func:`md2star.reverse_diagrams.make_diagram_handler`; kept out of
:mod:`md2star.cli` so the reverse feature imports lazily and the ``md2star
twin`` command stays a one-liner. The flags are parsed by click, there, once —
this module receives them typed.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

from pathlib import Path

from .errors import Md2starError
from .logging import configure as configure_logging
from .logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)


def run(
    input_path: str,
    *,
    out_dir: str | None = None,
    no_images: bool = False,
    diagrams: bool = False,
    model: str | None = None,
    max_iterations: int = 3,
    verbose: bool = False,
    quiet: bool = False,
) -> int:
    """Recover *input_path* as an editable Markdown twin. Returns an exit code.

    Parameters
    ----------
    input_path : str
        Document to recover: a PDF, or anything LibreOffice can print to one.
    out_dir : str or None, optional
        Where ``<stem>.md`` + ``assets/`` are written. An output *folder*
        rather than a file, because the twin is two things. ``None`` puts them
        next to the input.
    no_images : bool, optional
        Recover prose + tables only, dropping the scraped rasters.
    diagrams : bool, optional
        Re-author figures through the local VLM eyeball loop — node-and-edge
        diagrams as Mermaid, other vector figures as SVG. The one option that
        pulls in the AI stack, hence off by default.
    model : str or None, optional
        Vision model tag for *diagrams*. ``None`` lets best-engine-ai-helper
        pick per host.
    max_iterations : int, optional
        Cap on render→compare→revise cycles, so a stubborn diagram cannot spin
        forever.
    verbose, quiet : bool, optional
        Logging threshold, wired through the shared configuration.

    Returns
    -------
    int
        ``0`` and the twin's path on stdout; ``2`` for a missing input, ``127``
        for a missing system tool, ``1`` for any other recovery failure.
    """
    # First statement, before any step can emit a diagnostic, so -v/-q apply
    # to the whole recovery rather than to whatever happens after this line.
    configure_logging(verbose=verbose, quiet=quiet)

    # Not resolved: a relative input keeps the name the user typed in the
    # "report.md written next to report.pdf" message below.
    src = Path(input_path)
    # Default the output next to the input so a bare ``md2star twin report.pdf``
    # drops ``report.md`` + ``assets/`` right where the source lives.
    out = Path(out_dir) if out_dir else (src.parent if src.parent != Path("") else Path("."))

    # Only build the AI handler when --diagrams is requested; without it the twin
    # is fully deterministic and needs neither Ollama nor best-engine.
    image_handler = None
    if diagrams:
        from .reverse_diagrams import diagrams_available, make_diagram_handler

        if not diagrams_available(model):
            # Don't fail the whole run — warn and continue with plain PNGs, since
            # the deterministic twin is still valuable without reconstruction.
            logger.warning(
                "md2star twin: --diagrams requested but the AI stack is unavailable "
                "(Ollama not installed/running, or the model isn't pulled); "
                "keeping scraped images as PNGs."
            )
        else:
            image_handler = make_diagram_handler(model=model, max_iterations=max_iterations)

    # Imported here rather than at module scope: `reverse` pulls in Kreuzberg
    # (a Rust core plus OCR models), and `md2star twin --help` must not.
    try:
        from .reverse import to_markdown_twin

        md_path = to_markdown_twin(
            src,
            out,
            extract_images=not no_images,
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
