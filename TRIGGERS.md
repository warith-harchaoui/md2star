# md2star — exhaustive trigger catalogue

The exhaustive catalogue of what `md2star` does and of the natural-language
phrasings, commands, functions and file situations that should invoke it, whether you
call it yourself or drive it as an agent skill.

It lives twice, byte-identical: `TRIGGERS.md` at the repo root for people, and
`skills/md2star/references/triggers.md` for the skill. `scripts/check_triggers.py`
fails when the two drift apart. The `description:` in `SKILL.md` is what a host
model actually sees and is capped at 1024 characters; this file is the
auditable superset behind it, so keep the two in sync.

`md2star` converts **Markdown → DOCX / PPTX / PDF** via Pandoc with a curated
styling layer (branded templates, BibTeX citations, footnotes, Mermaid
diagrams, LaTeX math, image embedding). It also runs the **reverse direction**:
read a finished PDF / DOCX / PPTX back into an editable Markdown *twin* (prose +
tables + scraped images, optionally re-authoring diagrams as Mermaid). And it
**audits** any PowerPoint deck for overlapping, off-slide or unreadable text.
It is local-first: the document content never leaves your machine. It does
**not** generate websites or run a LaTeX-native workflow.

## The operations → how to invoke

| Intent | Shorthand | Subcommand | API |
|--------|-----------|------------|-----|
| Markdown → Word (.docx) | `md2docx report.md` | `md2star docx report.md` | `POST /convert?fmt=docx` |
| Markdown → PowerPoint (.pptx) | `md2pptx slides.md` | `md2star pptx slides.md` | `POST /convert?fmt=pptx` |
| Markdown → PDF (needs LibreOffice) | `md2pdf paper.md` | `md2star pdf paper.md` | `POST /convert?fmt=pdf` |
| Full browser editor (live PDF preview) | n/a | `md2star gui` | n/a |
| Document → editable Markdown *twin* (reverse) | n/a | `md2star twin file.pdf [--diagrams]` | `POST /extract` |
| Check a deck for layout defects | n/a | `md2star audit deck.pptx [--json] [--strict]` | `POST /audit` |
| Environment diagnostic | n/a | `md2star doctor [--json]` | `GET /doctor` |
| Inspect bundled / cached / project templates | n/a | `md2star templates` | n/a |
| Where the cache lives, wipe it | n/a | `md2star cache-dir`, `md2star clear-cache` | n/a |

The shorthands are the same click commands as `md2star docx|pptx|pdf`, with the
same flags. Every conversion is also reachable through the FastAPI HTTP surface
(`md2star-api`, with a minimal browser bench at `GET /gui`) and the MCP server
(`md2star-mcp`, the `[api,mcp]` extras); both bind `0.0.0.0:8000` unless
`--host` / `--port` or `MD2STAR_HOST` / `MD2STAR_PORT` say otherwise. The
skill's `references/surfaces.md` has the details.

## Natural-language phrasings that should fire

**Format-named conversion of Markdown**
- "convert this markdown to Word / a Word document / .docx / docx"
- "make a PowerPoint / .pptx / pptx / slide deck / slides / presentation from
  this markdown"
- "markdown to PDF", "export as PDF", "turn my .md into a PDF"
- "export / convert my README / notes / report / paper as DOCX / PPTX / PDF"
- "I have a markdown file, I need a Word / PowerPoint / PDF version"

**Explicit tool / command mentions**
- `md2docx`, `md2pptx`, `md2pdf`
- `md2star docx|pptx|pdf|gui|twin|audit|doctor|templates|cache-dir|clear-cache`,
  `md2star-api`, `md2star-mcp`
- "the md2star tool", "md2star", "how do I install / run md2star"

**Branding / templates**
- "use our corporate .docx / .pptx template", "brand this with our template"
- "apply a reference-doc" (`--reference-doc template.docx`), "styled Word
  output", "our house-style deck"

**Scientific / structured content**
- "resolve `[@citation]` / `[@key]` against my .bib" (`--bib refs.bib`),
  "BibTeX to Word", "citeproc citations in a Word doc"
- "footnotes in the Word / PDF output"
- "render this Mermaid diagram into a PDF / DOCX", "mermaid to document"
- "LaTeX math / equations in DOCX / PPTX / PDF"

**Preview / editor**
- "local Overleaf-style markdown editor", "live PDF preview of my markdown"
- "a browser editor for markdown → PDF", "minimal preview server for markdown"

**Reverse / twin (document → editable Markdown)**
- "turn this PDF / Word back into Markdown", "recover the Markdown from this
  document"
- "make an editable Markdown twin of this file", "reverse-engineer this
  document"
- "extract the tables and images from this PDF into Markdown"
- `md2star twin file.pdf`, `--diagrams` (re-author node-and-edge figures as
  Mermaid, other vector figures as SVG)

**Deck audit (what is wrong with this .pptx?)**
- "check this PowerPoint for overlapping text", "is anything off the slide in
  this deck?"
- "why is the text so small on slide 7", "lint my .pptx", "audit this deck /
  presentation"
- "does this deck have empty placeholders", "will this text fit on the slide"
- `md2star audit deck.pptx`: any presentation, not only one md2star made;
  exits 1 on a defect so it drops into CI; `--json` for machines

**Surfaces**
- "run the md2star API / MCP server", "open the md2star GUI", "install md2star"

## File situations it accepts

- **Input**: a Markdown file (`.md`, `.markdown`), optionally with `[@key]`
  citations (pass `--bib refs.bib`), footnotes, Mermaid code fences, LaTeX math,
  and local or (opt-in, `--allow-remote-images`) remote images.
- **Output**: `.docx`, `.pptx`, `.pdf`.
- **Optional branding**: a `.docx` / `.pptx` reference document
  (`--reference-doc template.docx`).
- **Reverse input**: a finished `.pdf`, `.docx` or `.pptx` for `md2star twin`;
  any `.pptx` for `md2star audit`.

## When NOT to use md2star (SKIP)

- Wanting only raw text / parsing out of a document with no intent to get an
  editable Markdown source back: use a plain parser or OCR tool. The twin path
  is for round-trippable Markdown, not one-shot text extraction.
- "Just run pandoc with these flags": the user wants raw Pandoc control.
- "Build a website / static HTML site from these markdown files": use a site
  generator.
- "I write in LaTeX / need a LaTeX-native PDF": Overleaf / latexmk.
- Drafting alt text or captions as primary content: the sprezzature-accessibility
  (alt text) and sprezzature-audio (captions) skills. md2star only fills EMPTY
  alts as an opt-in `--lint` side effect.
- Wanting a deck *redesigned* or its content rewritten: the audit measures a
  file and reports; it never edits one.

## Enforcement checklist

A trigger is "enforced" when: (1) it appears in the `SKILL.md` `description` so
the host model sees it before load; (2) the SKIP clause is present so the skill
does not over-fire; (3) `scripts/check_triggers.py` confirms every positive /
negative bucket is represented in the description string, and that this
catalogue and its mirror are still identical.

## See also

- the repo's `README.md`: features, install, quick start (English).
- the repo's `LISEZMOI.md`: the same in French.
- the repo's `EXAMPLES.md`: runnable recipes.
- the repo's `skills/README.md`: installing this as an agent skill.
