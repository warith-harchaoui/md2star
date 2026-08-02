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

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import os_helper as osh

from .errors import MissingDependencyError
from .logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# The document formats we read back *directly* through Kreuzberg. They mirror
# md2star's forward outputs (docx/pptx/pdf), so this trio is the true inverse of
# what the tool produces and needs no format conversion before extraction.
SUPPORTED_REVERSE_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pptx", ".pdf"})

# Anything else the user throws at the *twin* path — an ODT, an RTF, a legacy
# .doc, a spreadsheet, an HTML export — is first normalized to PDF through
# headless LibreOffice, so every non-native input funnels into the same
# Kreuzberg+OCR pipeline ("any document plausibly convertible to a PDF"). These
# are the suffixes LibreOffice reliably opens and prints; the list is
# permissive on purpose — an unknown suffix still *tries* soffice and fails with
# a clear message rather than being rejected up front.
SOFFICE_CONVERTIBLE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".odt",
        ".rtf",
        ".doc",
        ".ppt",
        ".odp",
        ".xls",
        ".xlsx",
        ".ods",
        ".html",
        ".htm",
        ".epub",
        ".txt",
        ".csv",
        ".fodt",
        ".fodp",
        ".wpd",
    }
)

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
        raise ReverseUnavailable(f"reverse conversion needs Kreuzberg — {_INSTALL_HINT}") from exc

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


# ─────────────────────────────────────────────────────────────────────────
# Markdown *twin* — the richer reverse path
# ─────────────────────────────────────────────────────────────────────────
#
# ``to_markdown`` above recovers *text*. The twin recovers an editable
# *document*: prose + GFM tables (Kreuzberg), plus every raster the document
# carries, scraped back out and re-linked so the Markdown is a first-class
# source you can re-render through md2star's forward path. Diagram
# reconstruction (photo-vs-figure classification, Mermaid/SVG re-authoring) is
# layered on top via the pluggable :data:`image_handler` seam so this module
# stays free of the AI stack and remains testable offline.


@dataclass
class TwinImage:
    """One raster scraped from the source document.

    Mirrors the dict Kreuzberg returns for an extracted image, typed so callers
    (and the :data:`ImageHandler` seam) get attribute access and editor tooling.
    """

    data: bytes
    format: str  # noqa: A003 — mirrors Kreuzberg's own field name
    image_index: int
    page_number: int = 0
    width: int = 0
    height: int = 0
    colorspace: str = ""

    @property
    def suggested_name(self) -> str:
        """Deterministic, collision-free asset filename for this image.

        Keyed on page + index so two runs over the same document produce the
        same asset paths (stable git diffs — the whole point of the twin).
        """
        ext = (self.format or "png").lower().lstrip(".")
        return f"img-p{self.page_number}-{self.image_index}.{ext}"


@dataclass
class TwinExtraction:
    """Raw result of reading a document back: Markdown body + scraped images.

    This is the *pre-assembly* view — the Markdown still carries Kreuzberg's
    ``![](image_N.ext)`` placeholders. :func:`to_markdown_twin` resolves those
    against :attr:`images` and the active image handler.
    """

    markdown: str
    images: list[TwinImage] = field(default_factory=list)


# An image handler turns one scraped raster into the Markdown that should stand
# in for it — by default a plain ``![](assets/…png)`` link, but the P2 AI layer
# swaps in a classifier + Ralph-Eyeball reconstructor that may return a
# ```mermaid``` block or an inline SVG instead. It receives the image and the
# assets directory (already created) and returns a Markdown snippet; writing any
# asset bytes it needs (the PNG, a fallback) is the handler's own job.
ImageHandler = Callable[["TwinImage", Path], str]


# Kreuzberg injects image references into its Markdown as ``![](image_<idx>.<ext>)``.
# We match the whole image span (any alt text, the exact placeholder target) so a
# handler can replace it with a multi-line snippet (e.g. a Mermaid block), not
# just swap the URL.
def _placeholder_re(img: TwinImage) -> re.Pattern[str]:
    ext = re.escape((img.format or "png").lower().lstrip("."))
    return re.compile(rf"!\[[^\]]*\]\(image_{img.image_index}\.{ext}\)")


def _find_soffice() -> str | None:
    """Locate the ``soffice`` binary, reusing the CLI's resolver to stay DRY.

    Imported lazily so the (heavy-ish) CLI module never loads just because
    something imported :mod:`md2star.reverse`; there is no import cycle today
    (``cli`` does not import ``reverse``), and the fallback keeps this module
    working even if that ever changes.
    """
    try:
        from .cli import _find_soffice as _cli_find_soffice

        return _cli_find_soffice()
    except Exception:  # noqa: BLE001 — a resolver problem must never crash extraction
        # Minimal inline fallback mirroring the CLI's search order.
        path = shutil.which("soffice") or shutil.which("libreoffice")
        if path:
            return path
        mac_app = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        return mac_app if os.path.exists(mac_app) else None


def _soffice_to_pdf(src: Path, out_dir: Path) -> Path:
    """Render *src* to a PDF in *out_dir* via headless LibreOffice; return it.

    This is the "plausibly convertible to a PDF" on-ramp: any office/markup
    format LibreOffice can open is normalized to PDF first, so every non-native
    input funnels into the same Kreuzberg+OCR extraction path as a real PDF.
    """
    soffice = _find_soffice()
    if soffice is None:
        raise MissingDependencyError(
            f"reading {src.suffix} back to Markdown needs LibreOffice (`soffice`)",
            hint=(
                "Install it to convert this format to PDF first:\n"
                "  macOS:   brew install --cask libreoffice\n"
                "  Ubuntu:  sudo apt install libreoffice\n"
                "  Windows: winget install --id TheDocumentFoundation.LibreOffice\n"
                "  other:   https://www.libreoffice.org/download/"
            ),
        )

    # soffice writes a sibling ``<stem>.pdf`` in --outdir and gives us no control
    # over the name, so we point it at *out_dir* and pick up the known filename.
    cmd = [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(src)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"LibreOffice timed out converting {src.name} to PDF") from exc
    produced = out_dir / (src.stem + ".pdf")
    if proc.returncode != 0 or not produced.exists():
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"LibreOffice could not convert {src.name} to PDF: {stderr}")
    return produced


def _normalize_to_readable(src: Path, workdir: Path) -> Path:
    """Return a path Kreuzberg reads directly — converting via soffice if needed.

    The docx/pptx/pdf trio is handed to Kreuzberg as-is; anything else is routed
    through :func:`_soffice_to_pdf` so the caller only ever extracts from a
    native format.
    """
    if is_supported(src):
        return src
    logger.info("md2star: normalizing %s to PDF via LibreOffice first", src.name)
    return _soffice_to_pdf(src, workdir)


def extract_twin(path: str | Path) -> TwinExtraction:
    """Read *path* back into Markdown **plus** its scraped rasters.

    Unlike :func:`to_markdown`, this asks Kreuzberg to extract embedded images
    (with in-text placeholders) and to recover document structure, so tables come
    back as GFM pipe tables and every figure is available for re-embedding or
    reconstruction. Non-native inputs are normalized to PDF first.

    Parameters
    ----------
    path : str or Path
        Any PDF, or a document LibreOffice can convert to one.

    Returns
    -------
    TwinExtraction
        The Markdown body (still carrying ``![](image_N.ext)`` placeholders) and
        the list of :class:`TwinImage` rasters.

    Raises
    ------
    ReverseUnavailable
        When the optional Kreuzberg dependency is not installed.
    FileNotFoundError
        When *path* does not exist.
    MissingDependencyError
        When a non-native input needs LibreOffice and it is absent.
    RuntimeError
        When Kreuzberg (or the soffice pre-convert) fails.
    """
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"no such file: {src}")

    try:
        import kreuzberg as kz
    except ImportError as exc:
        raise ReverseUnavailable(f"reverse conversion needs Kreuzberg — {_INSTALL_HINT}") from exc

    # One scratch folder holds any soffice-produced PDF; it is removed on exit,
    # so image bytes must be read out of the result before we leave the block.
    with osh.temporary_folder(prefix="md2star-twin-") as tmp:
        readable = _normalize_to_readable(src, Path(tmp))
        logger.info("md2star: reading %s back to a Markdown twin via Kreuzberg", src.name)
        config = kz.ExtractionConfig(
            output_format=kz.OutputFormat.MARKDOWN,
            # Scrape embedded rasters and leave ``![](image_N.ext)`` markers in
            # place so we can re-link (or reconstruct) each one precisely.
            images=kz.ImageExtractionConfig(extract_images=True, inject_placeholders=True),
            include_document_structure=True,
        )
        try:
            result = kz.extract_file_sync(str(readable), config=config)
        except Exception as exc:  # noqa: BLE001 — normalize any engine error into one type
            raise RuntimeError(f"Kreuzberg could not extract {src.name}: {exc}") from exc

        markdown = (result.content or "").rstrip("\n")
        markdown = markdown + "\n" if markdown else ""

        # Kreuzberg hands images back as plain dicts; adapt them into typed
        # TwinImage rows, tolerating missing optional keys across versions.
        images: list[TwinImage] = []
        for raw in result.images or []:
            images.append(
                TwinImage(
                    data=raw["data"],
                    format=raw.get("format", "png"),
                    image_index=raw.get("image_index", len(images)),
                    page_number=raw.get("page_number", 0),
                    width=raw.get("width", 0),
                    height=raw.get("height", 0),
                    colorspace=raw.get("colorspace", ""),
                )
            )
        return TwinExtraction(markdown=markdown, images=images)


def _default_image_handler(img: TwinImage, assets_dir: Path) -> str:
    """Write the scraped raster to *assets_dir* and return a Markdown link.

    The deterministic, AI-free default: every image is preserved verbatim as a
    PNG under ``assets/`` with an *empty* alt (which md2star's forward
    ``--lint`` alt-text pass can later fill). The P2 layer replaces this handler
    to classify and, for diagrams, reconstruct Mermaid/SVG.
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / img.suggested_name
    dest.write_bytes(img.data)
    # Relative link so the twin folder is portable (move the .md + assets/ as a unit).
    return f"![]({assets_dir.name}/{dest.name})"


def to_markdown_twin(
    path: str | Path,
    out_dir: str | Path,
    *,
    extract_images: bool = True,
    image_handler: ImageHandler | None = None,
    assets_dirname: str = "assets",
) -> Path:
    """Write *path*'s Markdown twin (``<stem>.md`` + ``assets/``) into *out_dir*.

    Parameters
    ----------
    path : str or Path
        The document to recover — a PDF or anything convertible to one.
    out_dir : str or Path
        Destination folder. Created if absent; the ``.md`` and the assets
        directory are written directly inside it.
    extract_images : bool, default True
        When False, scraped rasters are dropped and only prose + tables are kept
        (equivalent to the classic text-only reverse, but via the twin config).
    image_handler : ImageHandler, optional
        Override how each scraped raster becomes Markdown. Defaults to
        :func:`_default_image_handler` (write PNG + link). The AI diagram layer
        injects its classifier/reconstructor here.
    assets_dirname : str, default "assets"
        Name of the sub-folder that holds scraped/reconstructed image assets.

    Returns
    -------
    Path
        The written ``<stem>.md`` file.
    """
    src = Path(path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    assets_dir = out / assets_dirname
    handler = image_handler or _default_image_handler

    extraction = extract_twin(src)
    markdown = extraction.markdown

    if extract_images and extraction.images:
        markdown = _resolve_images(markdown, extraction.images, assets_dir, handler)
    else:
        # No images wanted (or none present): strip any dangling placeholders so
        # the twin never references assets that were not written.
        markdown = _strip_placeholders(markdown, extraction.images)

    md_path = out / f"{src.stem}.md"
    md_path.write_text(markdown, encoding="utf-8")
    logger.info(
        "md2star: wrote twin %s (%d image(s)) ",
        md_path.name,
        len(extraction.images) if extract_images else 0,
    )
    return md_path


def _resolve_images(
    markdown: str, images: list[TwinImage], assets_dir: Path, handler: ImageHandler
) -> str:
    """Replace each image placeholder with the handler's Markdown snippet.

    Placeholders present in the body are substituted in place; any image without
    a matching placeholder is appended under an "Extracted figures" section so no
    scraped raster is silently lost.
    """
    orphans: list[str] = []
    for img in images:
        snippet = handler(img, assets_dir)
        pattern = _placeholder_re(img)
        if pattern.search(markdown):
            # ``\g<0>`` is avoided: we replace the whole span with the snippet,
            # and count=1 guards against an accidental duplicate placeholder.
            markdown = pattern.sub(lambda _m, s=snippet: s, markdown, count=1)
        else:
            orphans.append(snippet)

    if orphans:
        markdown = (
            markdown.rstrip("\n") + "\n\n## Extracted figures\n\n" + "\n\n".join(orphans) + "\n"
        )
    return markdown


def _strip_placeholders(markdown: str, images: list[TwinImage]) -> str:
    """Remove Kreuzberg image placeholders (used when images are not extracted)."""
    for img in images:
        markdown = _placeholder_re(img).sub("", markdown)
    # Collapse the blank lines a removed placeholder can leave behind.
    return re.sub(r"\n{3,}", "\n\n", markdown)
