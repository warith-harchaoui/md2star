# TRIGGERS — md2star

This is the user-facing, exhaustive catalogue of what `md2star` does and the
natural-language phrasings, commands, and file situations that should invoke it
— whether you call it yourself or drive it as a Claude / OpenCode **skill** (see
[`skills/md2star/SKILL.md`](skills/md2star/SKILL.md) and its
[`references/triggers.md`](skills/md2star/references/triggers.md), the
machine-checked superset that `scripts/check_triggers.py` enforces).

`md2star` converts **Markdown → DOCX / PPTX / PDF** via Pandoc with a curated
styling layer (branded templates, BibTeX citations, footnotes, Mermaid
diagrams, LaTeX math, image embedding). It is local-first: the document content
never leaves your machine. It does **not** read/extract existing DOCX/PDF files,
generate websites, or run a LaTeX-native workflow.

## The conversions → how to invoke

| Intent | Wrapper | Subcommand | Library / API |
|--------|---------|------------|---------------|
| Markdown → Word (.docx) | `md2docx report.md` | `md2star docx report.md` | `POST /convert?fmt=docx` |
| Markdown → PowerPoint (.pptx) | `md2pptx slides.md` | `md2star pptx slides.md` | `POST /convert?fmt=pptx` |
| Markdown → PDF (needs LibreOffice) | `md2pdf paper.md` | `md2star pdf paper.md` | `POST /convert?fmt=pdf` |
| Full browser editor (live PDF preview) | — | `md2star gui` | — |
| Environment diagnostic | — | `md2star doctor [--json]` | `GET /doctor` |

Every conversion is also reachable through the click CLI (`md2star-x
docx|pptx|pdf|gui|doctor`, same delegation), the FastAPI HTTP surface
(`md2star-api`, with a minimal browser bench at `GET /gui`), and the MCP server
(`md2star-mcp`). See [`skills/md2star/references/surfaces.md`](skills/md2star/references/surfaces.md).

## Natural-language phrasings that should fire

- **Format-named conversion**: "convert this markdown to Word / .docx", "make a
  PowerPoint / deck / slides from this markdown", "markdown to PDF", "export my
  README / notes / paper as DOCX/PPTX/PDF".
- **Command mentions**: `md2docx`, `md2pptx`, `md2pdf`, `md2star
  docx|pptx|pdf|gui|doctor`, `md2star-x`, `md2star-api`, `md2star-mcp`, or "the
  md2star tool" / "how do I install/run md2star".
- **Branding / templates**: "use our corporate .docx/.pptx template", "brand
  this with our template", "apply a reference-doc", "our house-style deck".
- **Scientific / structured content**: "resolve `[@key]` against my .bib",
  "BibTeX to Word", "citeproc citations", "footnotes in the Word/PDF",
  "render this Mermaid diagram into a PDF/DOCX", "LaTeX math in DOCX/PPTX/PDF".
- **Preview / editor**: "local Overleaf-style markdown editor", "live PDF
  preview of my markdown", "a browser editor for markdown → PDF".
- **Surfaces**: "run the md2star API / MCP server", "open the md2star GUI",
  "install md2star".

## File situations it accepts

- **Input**: a Markdown file (`.md`, `.markdown`) — optionally with `[@key]`
  citations (pass `--bib refs.bib`), footnotes, Mermaid code fences, LaTeX math,
  and local or (opt-in) remote images.
- **Output**: `.docx`, `.pptx`, `.pdf`.
- **Optional branding**: a `.docx` / `.pptx` reference document
  (`--reference-doc template.docx`).

## When NOT to use md2star (SKIP)

- Reading / extracting text from an existing `.docx` / `.pdf` — that is
  extraction, not conversion (use a document parser / OCR tool).
- "Just run pandoc with these flags" — the user wants raw Pandoc control.
- Building a website / static HTML from Markdown → use a site generator.
- LaTeX-native PDF authoring → Overleaf / latexmk.
- Drafting alt-text or captions as primary content → the dedicated
  front-vision / front-audio skills. md2star only fills EMPTY alts as an opt-in
  `--lint` side effect.

## See also

- [`README.md`](README.md) — features, install, quick start (English).
- [`LISEZMOI.md`](LISEZMOI.md) — the same in French.
- [`EXAMPLES.md`](EXAMPLES.md) — runnable recipes.
- [`skills/README.md`](skills/README.md) — installing this as an agent skill.
