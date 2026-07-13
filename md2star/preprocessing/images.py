"""Image-related Markdown transformations.

Three concerns live here:

1. **Size capping** — bare ``![](...)`` images get an aspect-ratio-aware
   ``{width=…cm}`` or ``{height=…cm}`` block appended so the image fits an
   A4 page in *both* dimensions. URL/data refs and unreadable files fall
   back to ``{width=100%}``.
2. **In-cell resize** — images embedded inside pipe-table cells are physically
   downscaled to a small pixel ceiling. Pandoc's ``{width=100%}`` attribute
   refers to the *full page width*, not the cell width, so a hard resize is
   the only reliable way to keep cell images from overflowing.
3. **Remote download** — HTTP(S) image URLs are fetched to local temp files
   so Pandoc can embed them in the OOXML output (it does not reliably embed
   network URLs).

All on-disk artifacts (downloaded images, downscaled rasters, cell-fitted
copies, rendered SVGs) live in the user-level XDG cache directory provided
by :mod:`md2star.cache` so the user's source tree stays clean.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import urllib.request

from PIL import Image

from ..cache import cache_dir
from ..logging import get_logger
from .regexes import PIPE_TABLE_ROW_RE

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# A4 content area (portrait, ~25 mm margins) is ≈ 160 × 247 mm. We cap each
# image at a slightly tighter box so the rendered file also fits inside a
# 16:9 PPTX slide (33.87 × 19.05 cm) with room for a title — one constant
# set serves DOCX, PDF and PPTX outputs.
_MAX_WIDTH_CM = 15.0
_MAX_HEIGHT_CM = 17.0

# Matches ``![alt](src)`` inside a single cell, with optional trailing attrs.
_CELL_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)(?:\{[^}]*\})?")

# Matches a Markdown image with NO trailing attribute block. Group 1 is the
# ``![alt]`` prefix, group 2 is the ``src`` between parens; we keep them
# separate so callers can inspect the src (e.g. read its dimensions).
_IMAGE_NO_ATTR_RE = re.compile(r"(!\[[^\]]*\])\(([^)]+)\)(?!\s*\{)")

# Matches ``![alt](URL)`` with optional trailing ``{attrs}`` for remote images.
_REMOTE_IMG_RE = re.compile(
    r"(!\[[^\]]*\])\((https?://[^)]+)\)(\{[^}]*\})?"
)

# Captures the path between the parens of any ``![alt](path)`` reference.
_IMG_PATH_RE = re.compile(r"(!\[[^\]]*\]\()([^)]+)(\))")

# Schemes we must never touch when absolutizing — they are not filesystem paths.
_URL_PREFIXES = ("http://", "https://", "//", "data:", "file://")


def _hash_path(path: str) -> str:
    """Stable 12-char hex digest of an absolute path; used as a cache key."""
    return hashlib.md5(os.fspath(path).encode("utf-8")).hexdigest()[:12]


def resize_image_for_cell(src: str, base_dir: str, max_px: int = 400) -> str:
    """Physically downscale a local image so it fits inside a pipe-table cell.

    URL-based and missing files are returned unchanged; Pillow is the only
    backend (returns the original on any failure). Output is written to the
    XDG cache dir (``cell/<src-hash><ext>``), not next to the input file.
    """
    # Only local files can be opened + resized; remote/data URIs pass through.
    if src.startswith(("http://", "https://", "//", "data:")):
        return src

    # Resolve relative srcs against the document dir, then normalise.
    abs_src = src if os.path.isabs(src) else os.path.join(base_dir, src)
    abs_src = os.path.abspath(abs_src)

    if not os.path.exists(abs_src):
        return src

    try:
        from PIL import Image  # type: ignore[import-untyped]

        with Image.open(abs_src) as img:
            w, h = img.size
            # Already small enough → don't spend cycles re-encoding it.
            if w <= max_px and h <= max_px:
                return abs_src

            ext = os.path.splitext(abs_src)[1] or ".png"
            out_path = str(cache_dir("cell") / f"{_hash_path(abs_src)}{ext}")
            # Reuse a cached thumbnail unless the source is newer (mtime check),
            # so editing the image invalidates the stale downscale.
            if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(abs_src):
                return out_path

            # thumbnail() downscales in place preserving aspect ratio; LANCZOS
            # is the high-quality resampling filter.
            img.thumbnail((max_px, max_px), Image.LANCZOS)
            img.save(out_path)
        return out_path
    except Exception:
        # Any Pillow failure (unknown format, truncated file) → use the
        # original; a too-big cell image is better than a broken conversion.
        return abs_src


def image_size_attr(src: str) -> str:
    """Return a Pandoc attribute block that caps *src* inside an A4 page.

    Reads the image's pixel dimensions and emits the *single* binding
    constraint — ``{width=15cm}`` for wide images, ``{height=17cm}`` for
    tall ones — so Pandoc preserves the aspect ratio across DOCX, PDF,
    HTML and PPTX. Without this, a plain ``{width=100%}`` constrains only
    the horizontal extent and lets tall images run past the bottom margin.

    Falls back to ``{width=100%}`` for URL/data refs and any image that
    Pillow cannot open — preserving the historical behaviour for sources
    we can't physically measure.
    """
    if src.startswith(_URL_PREFIXES):
        return "{width=100%}"
    try:
        with Image.open(src) as img:
            width_px, height_px = img.size
    except (FileNotFoundError, OSError, ValueError):
        return "{width=100%}"

    # Degenerate dimensions (corrupt header) → safe historical fallback.
    if width_px <= 0 or height_px <= 0:
        return "{width=100%}"

    # Pick the single binding constraint by comparing the image's aspect ratio
    # to the box's: a "wide" image is limited by width, a "tall" one by height.
    # Emitting only one keeps Pandoc's aspect-ratio preservation intact.
    if width_px / height_px >= _MAX_WIDTH_CM / _MAX_HEIGHT_CM:
        return f"{{width={_MAX_WIDTH_CM:g}cm}}"
    return f"{{height={_MAX_HEIGHT_CM:g}cm}}"


def fix_image_widths(content: str) -> str:
    """Append an A4-fitting attribute block to every bare ``![](…)`` image.

    Each image is sized by aspect ratio (see :func:`image_size_attr`) so it
    never overflows an A4 page in either dimension — width *and* height are
    bounded, unlike the historical ``{width=100%}`` injection which left
    tall images running past the bottom margin.

    Images already inside pipe-table rows are skipped — those get physically
    resized via :func:`resize_images_in_markdown_tables` instead. Applying a
    page-wide cap inside a cell would still overflow the cell.
    """
    def _attach(match: re.Match) -> str:
        prefix, src = match.group(1), match.group(2)
        return f"{prefix}({src}){image_size_attr(src)}"

    result_lines: list[str] = []
    for line in content.split("\n"):
        # Skip table rows: a page-wide cap inside a cell would still overflow
        # the cell, so those images are physically resized elsewhere.
        if PIPE_TABLE_ROW_RE.match(line):
            result_lines.append(line)
        else:
            result_lines.append(_IMAGE_NO_ATTR_RE.sub(_attach, line))
    return "\n".join(result_lines)


def resize_images_in_markdown_tables(content: str, base_dir: str = ".") -> str:
    """Replace image references in pipe-table cells with paths to resized copies.

    URL-based images and images that cannot be located on disk are left as-is.
    """
    result_lines: list[str] = []
    for line in content.split("\n"):
        # Only rewrite inside pipe-table rows — everything else keeps its
        # normal (page-sized) image handling.
        if PIPE_TABLE_ROW_RE.match(line):
            def _resize_match(m: re.Match) -> str:
                alt = m.group(1)
                src = m.group(2)
                resized = resize_image_for_cell(src, base_dir)
                return f"![{alt}]({resized})"

            line = _CELL_IMG_RE.sub(_resize_match, line)
        result_lines.append(line)
    return "\n".join(result_lines)


def absolutize_image_paths(content: str, base_dir: str) -> str:
    """Rewrite relative ``![](path)`` refs to absolute paths against *base_dir*.

    URLs (``http(s)://``, ``//``, ``data:``, ``file://``) and paths that are
    already absolute pass through untouched. Fenced code blocks are skipped
    so example snippets are not mutated. Making the preprocessed Markdown
    self-contained means Pandoc resolves every image regardless of its cwd,
    which is what users expect when they run ``md2docx subdir/file.md``.
    """
    abs_base = os.path.abspath(base_dir)

    def _rewrite(match: re.Match) -> str:
        prefix, src, suffix = match.group(1), match.group(2), match.group(3)
        # Leave URLs and already-absolute paths alone; only relatives need work.
        if src.startswith(_URL_PREFIXES) or os.path.isabs(src):
            return match.group(0)
        # normpath collapses ../ and duplicate separators for a clean abs path.
        return f"{prefix}{os.path.normpath(os.path.join(abs_base, src))}{suffix}"

    # Track fenced code so example snippets with relative paths aren't rewritten.
    out_lines: list[str] = []
    in_code = False
    for line in content.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out_lines.append(line)
            continue
        if in_code:
            out_lines.append(line)
            continue
        out_lines.append(_IMG_PATH_RE.sub(_rewrite, line))
    return "\n".join(out_lines)


# HTML wrapper (``<p>``, ``<div>``, ``<center>``, ``<figure>``) whose content
# is whitespace + exactly one ``<img>``. Pandoc's DOCX writer drops raw HTML
# blocks entirely, so an image wrapped like that would otherwise vanish even
# after we rewrite its src.
_WRAPPED_HTML_IMG_RE = re.compile(
    r"<(?P<tag>p|div|center|figure)\b[^>]*>\s*"
    r"(?P<img><img\s[^>]*?>)\s*"
    r"</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)

# Bare ``<img …>`` tag (no surrounding wrapper match). Used after the wrapper
# stripping pass to rewrite anything left as Markdown image syntax.
_BARE_HTML_IMG_RE = re.compile(r"<img\s[^>]*?>", re.IGNORECASE)

# Attribute key/value pair inside an HTML tag (handles single or double
# quotes, tolerates whitespace around the ``=``).
_HTML_ATTR_RE = re.compile(
    r"""(?P<name>[A-Za-z_:][\w:.-]*)\s*=\s*(?P<q>['"])(?P<value>[^'"]*)(?P=q)"""
)


def _html_img_to_markdown(img_tag: str) -> str:
    """Convert a single ``<img …>`` tag into Markdown image syntax.

    Preserves ``alt``, ``src``, and ``width``; anything else is dropped on
    purpose so the produced Markdown stays portable across Pandoc writers.
    A missing ``src`` falls through as the original tag (nothing to convert).
    """
    # Parse all key="value" attrs (lower-cased keys) into a dict for lookup.
    attrs = {
        m.group("name").lower(): m.group("value")
        for m in _HTML_ATTR_RE.finditer(img_tag)
    }
    # No src → not a real image tag; hand it back unchanged.
    src = attrs.get("src")
    if not src:
        return img_tag
    # Carry over only the portable attributes (alt, src, optional width).
    alt = attrs.get("alt", "")
    width = attrs.get("width", "")
    out = f"![{alt}]({src})"
    if width:
        out += f"{{width={width}}}"
    return out


def html_images_to_markdown(content: str) -> str:
    """Flatten HTML ``<img>`` tags (and benign wrappers) into Markdown images.

    Two passes:

    1. ``<p|div|center|figure>…<img>…</tag>`` collapses to just the
       Markdown image (the wrapper is discarded so Pandoc doesn't drop
       the whole HTML block when writing DOCX/PPTX).
    2. Any remaining bare ``<img>`` tag is converted in place.

    Fenced code blocks are temporarily stashed under ``\\x00`` placeholder
    tokens so example snippets that *show* HTML are preserved verbatim —
    the NUL byte is effectively never present in real Markdown sources.
    """
    placeholders: dict[str, str] = {}

    def _stash(match: re.Match) -> str:
        token = f"\x00CODE_{len(placeholders)}\x00"
        placeholders[token] = match.group(0)
        return token

    stashed = re.sub(
        r"```[^\n]*\n.*?\n```", _stash, content, flags=re.DOTALL
    )
    stashed = _WRAPPED_HTML_IMG_RE.sub(
        lambda m: _html_img_to_markdown(m.group("img")), stashed
    )
    stashed = _BARE_HTML_IMG_RE.sub(
        lambda m: _html_img_to_markdown(m.group(0)), stashed
    )
    for token, block in placeholders.items():
        stashed = stashed.replace(token, block)
    return stashed


def _svg_to_png(svg_path: str, max_px: int) -> str | None:
    """Render *svg_path* to a cached PNG at ``max_px`` on the longest side.

    Tries ``rsvg-convert`` first (CLI, no Python deps; comes from ``librsvg``
    on Linux/macOS), then ``cairosvg`` (pure-Python after install, but needs
    the cairo native lib). Returns the absolute path to the PNG on success
    or ``None`` if no backend could render it — in which case the caller
    leaves the original SVG reference in place.

    Cached by mtime: re-running the preprocessor on an unchanged SVG reuses
    the existing PNG instead of re-rendering.
    """
    svg_path = os.path.abspath(svg_path)
    if not os.path.exists(svg_path):
        return None
    out_path = str(cache_dir("resized") / f"{_hash_path(svg_path)}_max{max_px}.png")

    if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(svg_path):
        return out_path

    rsvg = shutil.which("rsvg-convert")
    if rsvg is not None:
        try:
            subprocess.run(
                [rsvg, "-w", str(max_px), "-o", out_path, svg_path],
                check=True,
                timeout=30,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            return out_path
        except Exception as e:
            # rsvg failed — fall through to the cairosvg / warn-and-keep path.
            logger.warning(
                f"md2star warning: rsvg-convert failed on {svg_path}: {e}"
            )

    try:
        import cairosvg  # type: ignore[import-untyped]

        cairosvg.svg2png(url=svg_path, write_to=out_path, output_width=max_px)
        return out_path
    except Exception:
        pass

    # Neither backend available: keep the original SVG and tell the user how
    # to enable conversion.
    logger.warning(
        f"md2star warning: cannot convert SVG {svg_path} — install "
        "`librsvg` (brew install librsvg / apt install librsvg2-bin) "
        "or `cairosvg` (pip) to enable SVG support. Original kept."
    )
    return None


def _resize_raster(img_path: str, max_px: int) -> str:
    """Downscale *img_path* so its longest side ≤ ``max_px`` (in pixels).

    Anti-aliased: when the downscale ratio exceeds 2× we first apply a
    Gaussian low-pass with ``σ = (scale - 1) / 2`` to suppress high
    frequencies that would otherwise fold back into the resampled image.
    For scale ≤ 2, Lanczos-3 alone is a sharp enough anti-aliasing filter
    so we skip the blur and avoid a tiny softness penalty.

    Returns the path to a sibling ``<stem>_max<N><ext>`` file in the XDG
    cache, keyed by source-path hash so reruns are cheap. On any failure
    (Pillow missing, unreadable file, save error) the original path is
    returned unchanged.
    """
    try:
        from PIL import Image, ImageFilter  # type: ignore[import-untyped]
    except ImportError:
        return img_path

    img_path = os.path.abspath(img_path)
    if not os.path.exists(img_path):
        return img_path

    try:
        with Image.open(img_path) as probe:
            w, h = probe.size
    except Exception:
        return img_path

    longest = max(w, h)
    if longest <= max_px:
        return img_path

    scale = longest / max_px  # > 1
    ext = os.path.splitext(img_path)[1] or ".png"
    out_path = str(cache_dir("resized") / f"{_hash_path(img_path)}_max{max_px}{ext}")
    if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(img_path):
        return out_path

    try:
        with Image.open(img_path) as img:
            if scale > 2.0:
                sigma = (scale - 1.0) / 2.0
                img = img.filter(ImageFilter.GaussianBlur(radius=sigma))
            new_w = max(1, int(round(w / scale)))
            new_h = max(1, int(round(h / scale)))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            # Pillow can't save an RGBA frame as JPEG; coerce when needed.
            if ext.lower() in (".jpg", ".jpeg") and img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.save(out_path)
        return out_path
    except Exception as e:
        # Resizing is best-effort: on any failure keep the original image.
        logger.warning(
            f"md2star warning: cannot resize {img_path}: {e}"
        )
        return img_path


# HTML ``<img src="…">`` (single or double quoted). Group 3 is the src value.
_HTML_IMG_RE = re.compile(
    r"(<img\s[^>]*?src=)(['\"])([^'\"]+)(\2)([^>]*>)",
    re.IGNORECASE,
)


def process_image_assets(content: str, base_dir: str, max_px: int = 1600) -> str:
    """Convert SVG → PNG and downscale oversized rasters in every image ref.

    Walks every Markdown ``![alt](src)`` and HTML ``<img src="src">`` outside
    fenced code blocks. For each local file:

    * ``.svg`` → render to a cached PNG (via rsvg-convert or cairosvg) and
      rewrite the reference to point at the PNG.
    * Other raster formats above ``max_px`` on the longest side → downscale
      to a cached ``<hash>_max<N>.<ext>`` via :func:`_resize_raster`.
    * URLs, ``data:`` URIs, and missing files pass through unchanged.

    Pandoc's DOCX/PPTX writers don't render SVG reliably across Office
    versions, and embedding a 4000-px hero image into a docx blows the file
    size up for no visible gain — so this pass is a defensive normalisation
    before Pandoc sees the document.
    """
    def _process_src(src: str) -> str:
        if src.startswith(_URL_PREFIXES):
            return src
        path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if not os.path.exists(path):
            return src
        ext = os.path.splitext(path)[1].lower()
        if ext == ".svg":
            png = _svg_to_png(path, max_px)
            return png if png else src
        return _resize_raster(path, max_px)

    def _md_rewrite(m: re.Match) -> str:
        return f"{m.group(1)}{_process_src(m.group(2))}{m.group(3)}"

    def _html_rewrite(m: re.Match) -> str:
        new_src = _process_src(m.group(3))
        return f"{m.group(1)}{m.group(2)}{new_src}{m.group(4)}{m.group(5)}"

    out_lines: list[str] = []
    in_code = False
    for line in content.split("\n"):
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out_lines.append(line)
            continue
        if in_code:
            out_lines.append(line)
            continue
        line = _IMG_PATH_RE.sub(_md_rewrite, line)
        line = _HTML_IMG_RE.sub(_html_rewrite, line)
        out_lines.append(line)
    return "\n".join(out_lines)


def download_remote_images(content: str, out_dir: str) -> str:  # noqa: ARG001
    """Download ``http(s)://`` image references to the XDG cache directory.

    Pandoc does not reliably embed remote images in DOCX/PPTX output, so we
    fetch each URL once (keyed by MD5 of the URL) and rewrite the Markdown to
    point at the local copy. Failures leave the original URL in place.

    *out_dir* is retained for backwards compatibility but ignored — every
    download now lands in ``$XDG_CACHE_HOME/md2star/remote/`` so the user's
    source directory stays clean.
    """
    remote_cache = cache_dir("remote")

    def _download_and_replace(match: re.Match) -> str:
        prefix = match.group(1)        # ![alt]
        url = match.group(2)           # https://...
        attrs = match.group(3) or ""   # {width=85%} or empty

        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]

        ext = ".png"
        url_path = url.split("?")[0].split("#")[0]
        if "." in url_path.split("/")[-1]:
            ext = "." + url_path.split("/")[-1].rsplit(".", 1)[-1].lower()
            if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"):
                ext = ".png"

        local_path = str(remote_cache / f"{url_hash}{ext}")

        if not os.path.exists(local_path):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; md2star/1.0)"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    if "jpeg" in ct or "jpg" in ct:
                        ext = ".jpg"
                    elif "gif" in ct:
                        ext = ".gif"
                    elif "webp" in ct:
                        ext = ".webp"
                    elif "svg" in ct:
                        ext = ".svg"
                    local_path = str(remote_cache / f"{url_hash}{ext}")
                    with open(local_path, "wb") as f:
                        f.write(data)
            except Exception as e:
                # Download failed: leave the original remote reference in place
                # so pandoc can still try (or the user can fix the URL).
                logger.warning(
                    f"md2star warning: Failed to download image {url}: {e}"
                )
                return match.group(0)

        return f"{prefix}({local_path}){attrs}"

    return _REMOTE_IMG_RE.sub(_download_and_replace, content)
