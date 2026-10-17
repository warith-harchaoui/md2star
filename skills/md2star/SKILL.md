---
name: md2star
description: >-
  Convert Markdown into professional DOCX (Word), PPTX (PowerPoint) and PDF
  documents through a Pandoc wrapper with branded templates, BibTeX citations,
  footnotes, Mermaid diagrams, math and remote-image embedding — and read a
  finished PDF / DOCX / PPTX back into an editable Markdown twin. Use when the
  user says "convert this markdown to Word / .docx", "make a PowerPoint /
  deck / slides from this markdown", "markdown to PDF", "export my README as a
  PDF", "use our corporate template", "resolve [@key] against my .bib",
  "BibTeX to Word", "render this Mermaid diagram into a document", "turn this
  PDF back into Markdown", "make an editable twin of this doc", or types
  `md2docx`, `md2pptx`, `md2pdf`, `md2star docx|pptx|pdf|gui|doctor|twin`,
  `md2star-x`, `md2star-api`, `md2star-mcp`. Do NOT use to extract plain text
  from a document, to author the Markdown itself, or for HTML output. The
  exhaustive trigger catalogue is in `references/triggers.md`.
license: BSD-3-Clause
metadata:
  author: Warith Harchaoui
  package: md2star
  suite: ai-helpers
  homepage: https://deraison.ai/ai-helpers
---

# md2star — Markdown → DOCX / PPTX / PDF

`md2star` wraps Pandoc with a curated styling layer and practical automation.
You (the agent) drive it through its command-line surface; the user gets a
polished Office or PDF file back.

## Before anything: verify it is installed

```bash
md2star doctor      # reports Python, Pandoc, LibreOffice, Node, Ollama, templates
```

If the command is missing, install it (Pandoc is a hard system dependency;
LibreOffice is needed only for PDF):

```bash
pipx install md2star                 # cross-platform, isolated
# macOS one-shot: pandoc + pipx + md2star (add --with-pdf for LibreOffice)
bash scripts/brew.sh --with-pdf      # if working inside the md2star repo
```

`md2star doctor --json` gives a machine-readable status you can parse before
deciding whether a format is available (e.g. skip PDF if `soffice` is absent).

## The four conversions

Each format has a short alias and an equivalent `md2star <fmt>` subcommand:

```bash
md2docx report.md                    # → report.docx      (md2star docx report.md)
md2pptx slides.md                    # → slides.pptx      (md2star pptx slides.md)
md2pdf  paper.md                     # → paper.pdf        (needs LibreOffice)
md2star gui                          # local browser editor with live PDF preview
```

Common flags (all wrappers): `-o OUT` output path, `--author NAME`,
`--bib refs.bib` (BibTeX citations), `--reference-doc template.docx` (branding),
`--lang en`, `--lint` (opt-in local-LLM syntax fixer + empty-alt drafting),
`--offline`, `--allow-remote-images`. Run `md2docx --help` for the full surface
(it prints md2star flags then `pandoc --help`).

For the full flag matrix, template resolution rules, and the preprocessing
pipeline, read `references/cli-reference.md`. For the non-CLI surfaces (HTTP
API, MCP server, GUI), read `references/surfaces.md`.

## Rules of thumb

- **Pick the format from the deliverable**, not the source: "a Word doc" → docx,
  "slides/deck" → pptx, "a PDF to send" → pdf.
- **Default to deterministic.** `--lint` (the only AI pass) is OFF by default;
  only add it if the user asks for auto-fixing or empty-alt drafting.
- **Branding:** if the user has a `template.docx`/`template.pptx` or names a
  corporate template, pass `--reference-doc`; otherwise md2star uses its bundled
  (or the deraison.ai default) template.
- **Citations:** if the Markdown has `[@key]` references, look for a `.bib` and
  pass `--bib`, else the keys render literally.
- **After converting, confirm the output path** md2star printed (`Wrote: …`) and
  hand it back to the user; do not re-render unless something failed.
