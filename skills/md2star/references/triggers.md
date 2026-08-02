# md2star skill — exhaustive trigger catalogue

Auditable list of the phrasings that should fire this skill. Keep it in sync
with the `description:` TRIGGER clause in `SKILL.md` — the description is what a
host model actually sees, this file is the human-reviewable superset.

## Fire (positive triggers)

**Format-named conversion of Markdown**
- "convert this markdown to Word / a Word document / .docx / docx"
- "make a PowerPoint / .pptx / pptx / slide deck / slides / presentation from this markdown"
- "markdown to PDF / export as PDF / turn my .md into a PDF"
- "export/convert my README / notes / report / paper as DOCX/PPTX/PDF"
- "I have a markdown file, I need a Word/PowerPoint/PDF version"

**Explicit tool/command mentions**
- `md2docx`, `md2pptx`, `md2pdf`
- `md2star docx|pptx|pdf|gui|doctor|templates`, `md2star-x`, `md2star-api`, `md2star-mcp`
- "the md2star tool", "md2star", "how do I install/run md2star"

**Branding / templates**
- "use our corporate .docx / .pptx template", "brand this with our template"
- "apply a reference-doc", "styled Word output", "our house style deck"

**Scientific / structured content**
- "resolve [@citation] / [@key] against my .bib", "BibTeX to Word", "citeproc citations in a Word doc"
- "footnotes in the Word/PDF output"
- "render this Mermaid diagram into a PDF/DOCX", "mermaid to document"
- "LaTeX math / equations in DOCX/PPTX/PDF"

**Preview / editor**
- "local Overleaf-style markdown editor", "live PDF preview of my markdown"
- "a browser editor for markdown → PDF", "minimal preview server for markdown"

**Reverse / twin (document → editable Markdown)**
- "turn this PDF / Word back into Markdown", "recover the Markdown from this doc"
- "make an editable Markdown twin of this file", "reverse-engineer this document"
- "extract the tables and images from this PDF into Markdown"
- `md2star twin file.pdf`, `--diagrams` (re-author node-and-edge figures as Mermaid)

## Do NOT fire (negative triggers / SKIP)

- Wanting only raw text/parsing out of a document with no intent to get an
  editable Markdown source back — use a plain parser / OCR tool. (The twin path
  is for round-trippable Markdown, not one-shot text extraction.)
- "just run pandoc with these flags" — the user wants raw Pandoc control.
- "build a website / static HTML site from these markdown files" → site generator.
- "I write in LaTeX / need a LaTeX-native PDF" → Overleaf/latexmk.
- Drafting alt-text or captions as primary content → front-vision / front-audio
  (md2star only fills EMPTY alts as an opt-in `--lint` side effect).

## Enforcement checklist

A trigger is "enforced" when: (1) it appears in the `SKILL.md` `description`
so the host model sees it before load; (2) the SKIP clause is present so the
skill does not over-fire; (3) `scripts/check_triggers.py` confirms every
positive/negative bucket above is represented in the description string.
