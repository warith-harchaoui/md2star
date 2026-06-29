"""Orchestrator: runs the preprocessing phases in order.

The phase order matters and is not trivially permutable. From outermost to
innermost:

1. (opt-in) LLM lint — fix syntax-level errors before anything else parses.
2. Download remote images — replace ``http(s)://`` refs with local paths.
3. HTML table conversion — must run before line-splitting so multi-line
   ``<table>`` blocks are still in one piece.
4. Absolutize image paths — rewrite relative ``![](path)`` refs to absolute
   paths so the temp Markdown is portable across cwds (URLs and absolute
   paths pass through untouched).
5. Process image assets — render SVGs to PNG (via rsvg-convert or
   cairosvg) and downscale oversized rasters with Gaussian-prefiltered
   Lanczos resampling so Pandoc gets clean, reasonably-sized media.
6. Language detection — inject ``lang`` / ``date_format`` into YAML.
7. Line-by-line pass: math-in-code unwrap, Mermaid render, blank-line-
   before-list normalization. Fenced code blocks are skipped wholesale so
   their content stays verbatim.
8. Resize pipe-table cell images (physical resize).
9. Pipe-table separator normalization (proportional dashes + trailing blank
   line) so Pandoc honours per-column width hints in DOCX/PPTX.
10. ``{width=100%}`` injection on non-cell images.
11. PPTX slide isolation — split images off slides containing tables.

Each phase has a stable name (see :data:`PHASES`) so the CLI ``--skip-phase``
flag can address it directly. Names are deliberately snake_case and stable
across versions; treat them as part of the public API.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable

from .alt_text import fill_empty_alt_text
from .images import (
    absolutize_image_paths,
    download_remote_images,
    fix_image_widths,
    html_images_to_markdown,
    process_image_assets,
    resize_images_in_markdown_tables,
)
from .language import get_language_metadata
from .lint import lint_with_llm
from .math import unwrap_math_in_code_spans
from .mermaid import render_mermaid_local
from .regexes import PIPE_TABLE_ROW_RE
from .tables import convert_html_tables, normalize_pipe_tables

# Canonical, stable phase names. The CLI ``--skip-phase`` flag (and any
# ``md2star_skip:`` metadata key in a document's YAML front-matter) refers
# to phases by these names. Phases that have no obvious skip semantics
# (the line-by-line pass) are still listed for discoverability.
PHASES: frozenset[str] = frozenset({
    "lint",
    "remote_images",
    "html_tables",
    "html_images",
    "absolutize",
    "image_assets",
    "language",
    "line_pass",
    "table_resize",
    "table_normalize",
    "image_widths",
    "pptx_isolation",
})


# Standalone image line: ``![…](…)`` with optional ``{attrs}``.
_STANDALONE_IMG_RE = re.compile(r"^\s*!\[.*\]\(.*\)")

# Matches a list item: optional indent, marker (-, *, +, or N.), then a space.
_LIST_PATTERN = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+.*)")


def _warn_remote_images_blocked(content: str) -> None:
    """Emit a single stderr warning summarising blocked remote images.

    Triggered when the document references ``![](https://…)`` images
    but the caller did not pass ``allow_remote_images=True``. We do not
    raise: the rest of the pipeline still produces a sensible document
    (modulo the missing images), and the user gets one actionable
    breadcrumb pointing at the opt-in flag.
    """
    import re
    matches = re.findall(r"!\[[^\]]*\]\((https?://[^)]+)\)", content)
    if not matches:
        return
    sample = matches[0]
    extra = f" (and {len(matches) - 1} more)" if len(matches) > 1 else ""
    print(
        f"md2star: skipped remote image {sample!r}{extra} — pass "
        f"--allow-remote-images to download them, or --offline to "
        f"silence this warning explicitly.",
        file=sys.stderr,
    )


def _normalize_skip(skip_phases: Iterable[str] | None) -> frozenset[str]:
    """Validate ``skip_phases`` against :data:`PHASES`, warning on unknown names."""
    if not skip_phases:
        return frozenset()
    asked = {p.strip() for p in skip_phases if p and p.strip()}
    unknown = asked - PHASES
    if unknown:
        print(
            f"md2star warning: unknown --skip-phase name(s): "
            f"{', '.join(sorted(unknown))}. Known phases: "
            f"{', '.join(sorted(PHASES))}.",
            file=sys.stderr,
        )
    return frozenset(asked & PHASES)


def _extract_skip_from_metadata(content: str) -> set[str]:
    """Read ``md2star_skip:`` from the YAML front-matter, if any.

    Supports both list form (``md2star_skip: [language, image_widths]``) and
    one-per-line YAML list form. Unknown phase names are returned as-is and
    later filtered by :func:`_normalize_skip`.
    """
    m = re.match(
        r"^---[\r\n]+(.*?)[\r\n]+(?:---|\.\.\.)(?:[\r\n]+|$)",
        content,
        flags=re.DOTALL,
    )
    if not m:
        return set()
    block = m.group(1)
    inline = re.search(
        r"^md2star_skip\s*:\s*\[([^\]]*)\]", block, flags=re.MULTILINE
    )
    if inline:
        return {p.strip().strip("\"'") for p in inline.group(1).split(",") if p.strip()}
    multi = re.search(
        r"^md2star_skip\s*:[\r\n]+((?:\s*-\s*\S+[\r\n]+)+)",
        block,
        flags=re.MULTILINE,
    )
    if multi:
        return {
            re.sub(r"^\s*-\s*", "", line).strip().strip("\"'")
            for line in multi.group(1).splitlines()
            if line.strip()
        }
    return set()


def preprocess_markdown(
    content: str,
    base_dir: str = ".",
    inject_metadata: bool = True,
    lint_enabled: bool = False,
    skip_phases: Iterable[str] | None = None,
    *,
    allow_remote_images: bool = False,
    offline: bool = False,
) -> str:
    """Run the full preprocessing pipeline on a Markdown string.

    Parameters
    ----------
    content : str
        Raw Markdown source.
    base_dir : str
        Directory used to resolve relative image paths and to receive
        downloaded remote images / mermaid renders.
    inject_metadata : bool
        Whether to inject ``lang`` / ``date_format`` based on language
        detection (default: True). Equivalent to skipping ``language``.
    lint_enabled : bool
        Whether to run the optional Ollama LLM lint (default: False).
        Opt-in because it requires Ollama, adds latency, and can in rare
        cases rewrite content despite the safety guard.
    skip_phases : Iterable[str], optional
        Phase names to skip (see :data:`PHASES`). Merged with any
        ``md2star_skip:`` list found in the document's YAML front-matter.
    allow_remote_images : bool, keyword-only
        Whether to download ``![alt](https://...)`` references. Defaults
        to ``False`` (the safe-by-default policy introduced in v1.2.0):
        remote image markers are left in place, and the user sees a
        warning if any were skipped. Pass ``True`` to opt in.
    offline : bool, keyword-only
        Hard-disable every network-touching phase. Takes precedence
        over ``allow_remote_images`` and ``lint_enabled``.
    """
    skip = set(_normalize_skip(skip_phases))
    skip |= _normalize_skip(_extract_skip_from_metadata(content))

    # Offline mode hard-disables every phase that could reach the
    # network. The opt-in flags below become no-ops in this case.
    if offline:
        skip |= {"lint", "remote_images"}

    if lint_enabled and "lint" not in skip:
        content = lint_with_llm(content)

    if "remote_images" not in skip:
        if allow_remote_images:
            content = download_remote_images(content, base_dir)
        else:
            # Soft refusal: warn once and leave the http(s) refs in
            # place so pandoc embeds them as URLs (which it can in
            # HTML output; DOCX/PPTX will drop them, which is the
            # honest result of "no network was allowed").
            _warn_remote_images_blocked(content)
    if "html_tables" not in skip:
        content = convert_html_tables(content, base_dir)
    if "html_images" not in skip:
        content = html_images_to_markdown(content)
    if "absolutize" not in skip:
        content = absolutize_image_paths(content, base_dir)
    if "image_assets" not in skip:
        content = process_image_assets(content, base_dir)

    if inject_metadata and "language" not in skip:
        meta_injection = get_language_metadata(content)
        if meta_injection:
            injections = []
            if not re.search(r"^lang\s*:", content, flags=re.MULTILINE | re.IGNORECASE):
                injections.append(f"lang: {meta_injection['lang']}")
            if not re.search(r"^date_format\s*:", content, flags=re.MULTILINE | re.IGNORECASE):
                injections.append(f"date_format: \"{meta_injection['date_format']}\"")

            if injections:
                injection_str = "\n".join(injections) + "\n"
                yaml_match = re.match(
                    r"^(---[\r\n]+)(.*?)([\r\n]+(?:---|\.\.\.)(?:[\r\n]+|$))",
                    content, flags=re.DOTALL,
                )
                if yaml_match:
                    new_yaml = (
                        f"{yaml_match.group(1)}{injection_str}"
                        f"{yaml_match.group(2)}{yaml_match.group(3)}"
                    )
                    content = new_yaml + content[yaml_match.end():]
                else:
                    content = f"---\n{injection_str}---\n\n{content}"

    if "line_pass" not in skip:
        out_lines: list[str] = []
        in_code_block = False
        in_mermaid_block = False
        mermaid_lines: list[str] = []

        for line in content.split("\n"):
            stripped_line = line.strip()

            # Entering a fenced block
            if stripped_line.startswith("```") and not in_code_block:
                in_code_block = True
                if stripped_line.lower().startswith("```mermaid"):
                    in_mermaid_block = True
                else:
                    out_lines.append(line)
                continue

            # Exiting a fenced block
            if stripped_line.startswith("```") and in_code_block:
                in_code_block = False
                if in_mermaid_block:
                    in_mermaid_block = False
                    mermaid_content = "\n".join(mermaid_lines)
                    try:
                        img_name = render_mermaid_local(mermaid_content, base_dir)
                        if out_lines and out_lines[-1].strip() != "":
                            out_lines.append("")
                        out_lines.append(f"![]({img_name})\n")
                    except Exception as e:
                        print(
                            f"md2star warning: Mermaid rendering failed: {e}",
                            file=sys.stderr,
                        )
                        out_lines.append("```mermaid")
                        out_lines.extend(mermaid_lines)
                        out_lines.append("```")
                    mermaid_lines = []
                else:
                    out_lines.append(line)
                continue

            # Inside a fenced block
            if in_code_block:
                if in_mermaid_block:
                    mermaid_lines.append(line)
                else:
                    out_lines.append(line)
                continue

            # Rewrite ``\`$x^2$\``` / ``\`text $math$\``` into proper math so
            # Pandoc renders the formula instead of a verbatim code span.
            line = unwrap_math_in_code_spans(line)

            # Insert blank line before a list item if missing
            if _LIST_PATTERN.match(line):
                if out_lines and out_lines[-1].strip() != "":
                    out_lines.append("")

            out_lines.append(line)

        content = "\n".join(out_lines)

    if "table_resize" not in skip:
        content = resize_images_in_markdown_tables(content, base_dir)
    if "table_normalize" not in skip:
        content = normalize_pipe_tables(content)
    # Alt-text drafting piggy-backs on ``--lint`` — same opt-in, same
    # offline kill-switch. Runs *after* the mermaid line-pass (so freshly
    # rendered diagrams get described too) and *before*
    # :func:`fix_image_widths` (so the bare ``![](src)`` regex still
    # matches the empty alts).
    if lint_enabled and "lint" not in skip:
        content = fill_empty_alt_text(content, base_dir)
    if "image_widths" not in skip:
        content = fix_image_widths(content)
    if "pptx_isolation" not in skip:
        content = isolate_images_for_pptx(content)

    return content


def isolate_images_for_pptx(content: str) -> str:
    """Push standalone images and pipe-tables onto fresh PPTX slides.

    Pandoc's PPTX writer maps each ``## H2`` (or ``# H1``) heading to one
    slide. A slide that mixes prose with an image silently drops the image,
    and a slide that mixes prose with a table cramps everything together.
    Inserting a blank ``##`` before the offending block forces it onto its
    own slide. Empty headings render as nothing in DOCX, so the rewrite is
    harmless for that output.

    Both images *and* tables are isolated by the same pass — keeping them
    in one function avoids cascading ``##`` insertions from two independent
    walkers tripping over each other's output.
    """
    lines = content.split("\n")
    out: list[str] = []

    section_has_table = False
    section_has_content = False
    in_table = False
    in_code = False

    for line in lines:
        stripped = line.strip()

        # Fenced code blocks pass through verbatim — they may contain
        # pipe-table-shaped lines that are not actual tables.
        if stripped.startswith("```"):
            in_code = not in_code
            in_table = False
            out.append(line)
            continue
        if in_code:
            out.append(line)
            continue

        if stripped.startswith("## ") or stripped.startswith("# "):
            section_has_table = False
            section_has_content = False
            in_table = False
            out.append(line)
            continue

        is_table_row = bool(PIPE_TABLE_ROW_RE.match(stripped))

        if is_table_row:
            if not in_table and (section_has_table or section_has_content):
                # New table on a slide that already has stuff → isolate it.
                out.append("")
                out.append("##")
                out.append("")
                section_has_table = False
                section_has_content = False
            in_table = True
            section_has_table = True
            out.append(line)
            continue

        # Any non-table line ends an in-progress table block.
        in_table = False

        if _STANDALONE_IMG_RE.match(stripped):
            if section_has_table or section_has_content:
                out.append("")
                out.append("##")
                out.append("")
                section_has_table = False
                section_has_content = False
            out.append(line)
            # The image itself counts as content for any *subsequent* item.
            section_has_content = True
            continue

        if stripped:
            section_has_content = True

        out.append(line)

    return "\n".join(out)
