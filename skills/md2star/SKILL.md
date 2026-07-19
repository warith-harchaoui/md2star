---
name: md2star
description: >-
  Convert Markdown into professional DOCX (Word), PPTX (PowerPoint) and PDF
  documents via the `md2star` CLI — a Pandoc wrapper with branded templates,
  BibTeX citations, footnotes, Mermaid diagrams, math, and remote-image
  embedding. Use it whenever a user wants a Markdown file turned into an Office
  or PDF deliverable rather than raw HTML/LaTeX.

  TRIGGER — any of: the user names a target format for a `.md` file ("convert
  this markdown to Word / .docx / a Word document", "make a PowerPoint / .pptx /
  slides / a deck from this markdown", "markdown to PDF", "export my README as a
  PDF/DOCX"); the user types or references a wrapper command (`md2docx`,
  `md2pptx`, `md2pdf`, `md2star docx|pptx|pdf|gui|doctor`); the user wants a
  branded/templated Office document ("use our .docx/.pptx template", "corporate
  template", "reference-doc styling"); the user wants citations/bibliography in
  Word ("resolve [@key] against my .bib", "BibTeX to Word", "citeproc"),
  footnotes, a Mermaid diagram rendered into a document, or LaTeX-style math in
  DOCX/PPTX/PDF; the user asks for a local "Overleaf-style" Markdown→PDF preview
  editor; the user asks how to install/run any of the above or says "md2star".

  SKIP when: the source is not Markdown (e.g. a raw .docx/.pdf to be read or
  edited — that is extraction, not conversion); the user explicitly wants to run
  Pandoc directly with their own flags; the target is a static website/HTML
  (use a site generator) or a LaTeX-native workflow (use Overleaf/latexmk). For
  drafting alt-text or captions as content, prefer the dedicated front-vision /
  front-audio skills; md2star only fills EMPTY alts as an opt-in `--lint` side
  effect.
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
