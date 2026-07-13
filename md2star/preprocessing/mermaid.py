"""Local Mermaid diagram rendering via the official Mermaid CLI (``mmdc``).

Uses ``npx -y @mermaid-js/mermaid-cli`` so no global install is required. The
rendered PNG is cached in the XDG cache directory keyed by MD5 of the source
**plus** the resolved body font (so re-skinning the template invalidates the
cache).

Requires Node.js ≥16 on ``PATH``. Raises :class:`RuntimeError` on failure so
the caller can decide whether to fall back to the original code block.

Box-overflow fix
----------------
Headless mmdc cannot measure HTML <foreignObject> text reliably, which is the
usual cause of "the words don't fit inside the box". The shipped
``mermaid-config.json`` disables ``htmlLabels`` (forcing native SVG text that
auto-sizes) and bumps node padding. On top of that, this module reads the
active DOCX template's body font (``Normal`` style) and substitutes it into
the mermaid theme so diagrams visually match the surrounding prose.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import zipfile
from importlib import resources

from ..cache import cache_dir


def _template_body_font(template_docx: str) -> str | None:
    """Return the ``Normal`` paragraph style's ASCII font from a DOCX template.

    Falls back to ``docDefaults`` ``rPrDefault`` if ``Normal`` does not declare
    its own ``<w:rFonts/>``. Returns ``None`` if the template cannot be read.
    """
    # A .docx is a zip; the paragraph styles live in word/styles.xml. Any read
    # failure (missing file, not a zip) just means "no font info" → None.
    try:
        with zipfile.ZipFile(template_docx) as z:
            styles = z.read("word/styles.xml").decode("utf-8")
    except (FileNotFoundError, KeyError, zipfile.BadZipFile):
        return None

    # Prefer the ``Normal`` paragraph style's own font: that's the body text
    # font diagrams should visually match. We isolate the whole <w:style> block
    # first, then pull the ascii font out of its <w:rFonts>.
    normal = re.search(
        r'<w:style[^>]*w:styleId="Normal"[^>]*>.*?</w:style>',
        styles,
        re.DOTALL,
    )
    if normal:
        m = re.search(r'<w:rFonts[^/]*w:ascii="([^"]+)"', normal.group(0))
        if m:
            return m.group(1)

    # Normal didn't declare its own font → inherit the document-wide default.
    m = re.search(
        r"<w:docDefaults>.*?<w:rFonts[^/]*w:ascii=\"([^\"]+)\"",
        styles,
        re.DOTALL,
    )
    return m.group(1) if m else None


def _load_base_mermaid_config() -> dict | None:
    """Return the bundled ``mermaid-config.json`` as a dict, or ``None``."""
    try:
        with resources.files("md2star.data").joinpath("mermaid-config.json").open(
            "r", encoding="utf-8"
        ) as f:
            return json.load(f)
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError, OSError):
        return None


def _build_mermaid_config(font_family: str | None) -> tuple[str, str] | None:
    """Return ``(config_path, hash_key)`` for the mermaid config to pass to ``mmdc``.

    The bundled ``mermaid-config.json`` is loaded, the body font is spliced
    into ``themeVariables.fontFamily``, and the merged config is written to a
    hash-keyed file in the XDG cache. The hash also feeds the render cache
    key (see :func:`render_mermaid_local`) so edits to the bundled palette —
    not just the font — invalidate previously cached PNGs.

    Returns ``None`` if no config could be assembled.
    """
    cfg = _load_base_mermaid_config()
    if cfg is None:
        return None

    # Splice the template's body font into the theme, with a web-safe fallback
    # chain so mmdc still renders if that exact font isn't on the box.
    if font_family:
        theme_vars = cfg.setdefault("themeVariables", {})
        theme_vars["fontFamily"] = f"{font_family}, Arial, Helvetica, sans-serif"

    # Key the config file (and, upstream, the render cache) on the MD5 of the
    # *merged* config with sorted keys — so any palette edit, not just the
    # font, deterministically produces a new key and invalidates stale PNGs.
    key = hashlib.md5(json.dumps(cfg, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    resolved_path = str(cache_dir("mermaid") / f"config_{key}.json")
    # Write once per unique config; identical configs reuse the same file.
    if not os.path.exists(resolved_path):
        with open(resolved_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    return resolved_path, key


def _resolve_template_docx() -> str | None:
    """Locate the active DOCX template so we can read its body font.

    The historical path was ``~/.pandoc/template.docx`` (placed there by the
    legacy ``make install``). After the pyproject restructure the template is
    shipped inside the wheel, so we fall back to the package data copy.
    """
    legacy = os.path.join(os.path.expanduser("~"), ".pandoc", "template.docx")
    if os.path.exists(legacy):
        return legacy
    try:
        return str(resources.files("md2star.data").joinpath("template.docx"))
    except (FileNotFoundError, ModuleNotFoundError):
        return None


def render_mermaid_local(content: str, out_dir: str) -> str:  # noqa: ARG001
    """Render *content* (Mermaid markup) to a PNG and return its absolute path.

    *out_dir* is accepted for backwards compatibility but the cache lives in
    ``$XDG_CACHE_HOME/md2star/mermaid/`` so renders are shared across runs.
    """
    template_docx = _resolve_template_docx()
    body_font = _template_body_font(template_docx) if template_docx else None
    built = _build_mermaid_config(body_font)
    config_path, config_key = built if built else (None, "")

    # Cache key folds in the body font *and* the resolved config hash, so
    # both template-font changes and palette edits invalidate stale renders.
    cache_key = hashlib.md5(
        (content + "|" + (body_font or "") + "|" + config_key).encode("utf-8")
    ).hexdigest()
    mermaid_dir = cache_dir("mermaid")
    filepath = str(mermaid_dir / f"{cache_key}.png")

    # Cache hit: an identical diagram (same source + font + config) was already
    # rendered, so skip the expensive npx/Chromium spin-up entirely.
    if os.path.exists(filepath):
        return filepath

    # mmdc reads from a file, not stdin — stage the markup next to the output.
    tmp_input = str(mermaid_dir / f"{cache_key}.mmd")
    with open(tmp_input, "w", encoding="utf-8") as f:
        f.write(content)

    # ``npx -y`` fetches the pinned mermaid-cli on demand, so users don't need a
    # global install. transparent background blends into any page; --scale 2
    # renders at 2× for crisp diagrams in print/PDF.
    cmd = [
        "npx", "-y", "@mermaid-js/mermaid-cli",
        "-i", tmp_input, "-o", filepath,
        "-b", "transparent", "--scale", "2",
    ]
    if config_path:
        cmd.extend(["-c", config_path])
    # Pass --no-sandbox to the bundled Chromium. Ubuntu 24.04 and other
    # recent distros restrict unprivileged user namespaces via AppArmor,
    # which breaks Puppeteer's default sandbox. Our input is a static
    # ``.mmd`` file we just wrote ourselves, so disabling the sandbox is
    # the standard CI workaround (see https://pptr.dev/troubleshooting).
    try:
        puppeteer_cfg = str(
            resources.files("md2star.data").joinpath("puppeteer-config.json")
        )
        if os.path.exists(puppeteer_cfg):
            cmd.extend(["-p", puppeteer_cfg])
    except (FileNotFoundError, ModuleNotFoundError):
        pass

    # 60s cap: a hung headless browser shouldn't stall the whole conversion.
    result = subprocess.run(cmd, capture_output=True, timeout=60)

    # The .mmd was only scratch input — best-effort cleanup, ignore if gone.
    try:
        os.remove(tmp_input)
    except OSError:
        pass

    # Treat "non-zero exit" OR "no PNG produced" as failure; raising lets the
    # caller keep the original code fence instead of losing the diagram.
    if result.returncode != 0 or not os.path.exists(filepath):
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(
            f"mmdc failed (exit {result.returncode}): {stderr}\n"
            f"Ensure Node.js ≥16 is installed: https://nodejs.org/"
        )

    return filepath
