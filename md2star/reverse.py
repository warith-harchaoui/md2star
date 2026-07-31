"""
Reverse conversion: DOCX / PPTX / PDF → Markdown.

md2star's main direction is Markdown → polished document. This module is the
*other* direction: take an existing ``.docx``, ``.pptx`` or ``.pdf`` and read
it back into Markdown, so a user can drop a finished document into the GUI and
recover an editable Markdown source of truth.

The extraction is delegated to `Kreuzberg <https://github.com/Goldziher/kreuzberg>`_,
a document-understanding engine that already backs md2star's round-trip OCR
test. Kreuzberg can emit Markdown directly
(``ExtractionConfig(output_format=OutputFormat.MARKDOWN)``), including OCR of
scanned/image-only PDFs, so md2star adds only a thin, well-guarded wrapper.

Kreuzberg is an **optional** runtime dependency (heavy: a Rust core plus OCR).
It is not in md2star's base install; enable this feature with::

    pip install 'md2star[ocr]'

Every entry point degrades gracefully when it is absent: :func:`reverse_available`
returns ``False`` and :func:`to_markdown` raises a clear :class:`ReverseUnavailable`
with the install hint, so callers (CLI, API, GUI) can surface a helpful message
instead of crashing.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

from pathlib import Path

from .logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# The document formats we can read back. Kreuzberg handles many more, but md2star
# only advertises the three that mirror its forward outputs (docx/pptx/pdf), so
# the reverse direction is a true inverse of what the tool produces.
SUPPORTED_REVERSE_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pptx", ".pdf"})

# One line, reused everywhere the optional dependency is missing, so the install
# hint is identical across the CLI, API and GUI surfaces.
_INSTALL_HINT = "install the reverse-conversion extra: pip install 'md2star[ocr]'"


class ReverseUnavailable(RuntimeError):
    """Raised when reverse conversion is requested but Kreuzberg is not installed."""


def reverse_available() -> bool:
    """Return ``True`` when the optional Kreuzberg engine can be imported.

    Cheap and side-effect-free: it only checks importability (no extraction, no
    subprocess), so callers can use it to show/hide the feature in a UI or in
    ``doctor`` output without paying Kreuzberg's runtime cost.
    """
    # ``find_spec`` avoids importing the (heavy) package just to test presence.
    from importlib.util import find_spec

    return find_spec("kreuzberg") is not None


def is_supported(path: str | Path) -> bool:
    """Return ``True`` when *path*'s extension is one md2star reads back."""
    return Path(path).suffix.lower() in SUPPORTED_REVERSE_EXTENSIONS


def to_markdown(path: str | Path) -> str:
    """Extract *path* (a DOCX/PPTX/PDF) to Markdown text.

    Parameters
    ----------
    path : str or Path
        The document to read back. Its extension must be one of
        :data:`SUPPORTED_REVERSE_EXTENSIONS`.

    Returns
    -------
    str
        The document's content rendered as Markdown (headings, bold/italic,
        lists and tables preserved as far as Kreuzberg can recover them).

    Raises
    ------
    ReverseUnavailable
        When the optional Kreuzberg dependency is not installed.
    FileNotFoundError
        When *path* does not exist.
    ValueError
        When *path*'s extension is not a supported input format.
    RuntimeError
        When Kreuzberg fails to extract the document.
    """
    src = Path(path)

    # Fail fast and specifically before touching the heavy engine, so the caller
    # gets a precise error rather than an opaque extraction failure.
    if not src.is_file():
        raise FileNotFoundError(f"no such file: {src}")
    if not is_supported(src):
        supported = ", ".join(sorted(SUPPORTED_REVERSE_EXTENSIONS))
        raise ValueError(f"unsupported input {src.suffix!r}; expected one of {supported}")

    try:
        # Imported lazily: the base install has no Kreuzberg, and even when it is
        # present the import is heavy enough to keep off the module load path.
        import kreuzberg as kz
    except ImportError as exc:
        raise ReverseUnavailable(
            f"reverse conversion needs Kreuzberg — {_INSTALL_HINT}"
        ) from exc

    logger.info("md2star: reading %s back to Markdown via Kreuzberg", src.name)

    # Ask Kreuzberg for Markdown output directly; ``result.content`` then carries
    # the Markdown string (not plain text), so no post-formatting is needed.
    config = kz.ExtractionConfig(output_format=kz.OutputFormat.MARKDOWN)
    try:
        result = kz.extract_file_sync(str(src), config=config)
    except Exception as exc:  # noqa: BLE001 — normalize any engine error into one type
        # Kreuzberg raises a family of its own exceptions (OCR, parsing, missing
        # system deps like Tesseract); collapse them into a single, actionable
        # RuntimeError so every caller handles one failure type.
        raise RuntimeError(f"Kreuzberg could not extract {src.name}: {exc}") from exc

    # ``content`` is the unified Markdown body; guarantee a trailing newline so
    # the text drops cleanly into an editor buffer or a written .md file.
    markdown = (result.content or "").rstrip("\n")
    return markdown + "\n" if markdown else ""
