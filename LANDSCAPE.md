# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/md2star/blob/main/PAYSAGE.md) · 🇬🇧 English

Honest competitive comparison in the "Markdown → polished document"
space, benchmarked against `md2star`. Ratings are ⭐ (1) to
⭐⭐⭐⭐⭐ (5), scored on `md2star`'s intended job — take a Markdown
source of truth and produce a deliberate-looking DOCX / PPTX / PDF,
offline by default, with clean git-friendly diffs. A tool optimised
for a very different job (native Office co-editing, LaTeX-native
typesetting) is not penalised — the score just reflects fit to *this*
niche. Picking the right tool matters more than picking ours: if your
team lives in native Office documents, Word / Google Docs beats
md2star and we say so.

We grade ourselves honestly — `md2star` does not get 5 stars on every
row. This document is maintained by hand and reflects the state of
each project as of mid-2026; open an issue if something is out of
date.

## At a glance

<!-- TABLE:START -->
| Markdown Conversion | Office+PDF | Citations | Diagrams | Math | Branded | One-cmd CLI | Offline | Local-LLM | Reverse-MD |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **md2star** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Pandoc | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Pandoc + templates | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| Typst | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Marp | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Slidev | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| reveal.js | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| MkDocs | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ |
| Docusaurus | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ |
| LibreOffice | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ |
| Overleaf | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ |
| Obsidian export | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Word / Google Docs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/landscape.png)

The map is a 2-D summary of the nine criteria, so read it as a shape, not a scoreboard. `md2star` is at the top-right corner. The axes read **Horizontal — Educational ↔ Practical** and **Vertical — Visual ↔ Comprehensive**.
<!-- FIGURE:END -->

## Column legend

The nine criteria, in short:

- **Office+PDF** — quality and reliability of `.docx`, `.pptx` and PDF
  output (PDF without requiring a LaTeX toolchain).
- **Citations** — citations / bibliography (BibTeX, CSL, Zotero).
- **Diagrams** — Mermaid / Graphviz / PlantUML rendered into the
  document.
- **Math** — LaTeX `$…$` / `$$…$$` typesetting, inline and display,
  rendered correctly in the chosen output.
- **Branded** — house-style templates (fonts, colours, cover, headers/
  footers) so output looks deliberate, not a raw export.
- **One-cmd CLI** — a single command turns Markdown into the
  deliverable, with no multi-step toolchain to wire up by hand.
- **Offline** — works fully offline by default, no silent network
  calls.
- **Local-LLM** — optional local-LLM features (lint, summaries, merge
  proposals) via Ollama or similar.
- **Reverse-MD** — round-trips a finished DOCX / PPTX / PDF back into
  an editable Markdown twin.

Cells that would be "not applicable" in the hand-maintained rubric
(e.g. an Office+PDF rating for a slides-only or website-only tool)
score ⭐ here, so the machine-read table stays pure stars — read those
as "not a fit for this dimension".

## Positioning

`md2star` deliberately sits at the intersection of a **Markdown
source of truth** (plain-text diffs, greppable archive, zero
proprietary-format risk) and **polished, branded document output** (a
DOCX, PPTX or PDF that looks like a deliberate document, not a raw
export), driven by **one command**, **offline**, with optional
**local-LLM** assists and a **reverse path** back to Markdown. It
intentionally does **not** try to beat Typst or Overleaf on
LaTeX-native math, or Word / Google Docs on native Office editing.

You should pick `md2star` when **all** of these apply:

- Your source of truth is Markdown — you want plain-text diffs, a
  greppable archive, and no proprietary-format risk.
- You produce DOCX, PPTX or PDF as the polished deliverable (papers,
  internal reports, client slides, training material, a book draft
  headed to a copy editor).
- You want branding baked in and a single-command conversion, not a
  hand-wired template + PDF toolchain.
- You value offline-by-default, zero telemetry, and optional
  local-LLM assists.
- Your team is small (1–10) and async, or you work solo across
  several devices.

Where `md2star` deliberately doesn't top the table:

1. **Math** — 3 stars, its weakest row. Deep LaTeX math belongs to
   Typst, Overleaf or raw Pandoc; md2star renders everyday inline and
   display math well but is not a full LaTeX substitute.
2. **Office+PDF** — 4 stars. Output is deliberate and reliable, but
   native editors (Word / Google Docs, LibreOffice) and Overleaf beat
   it on raw rendering fidelity in their own format.
3. **Citations & Diagrams** — 4 stars each. Broad enough for reports
   and papers; Pandoc and Quarto go further on exotic CSL styles and
   the long tail of diagram engines.

## When to pick what

- **`md2star`** — Markdown-sourced documents that must ship as a
  polished, branded DOCX / PPTX / PDF, offline, one command, with
  clean git diffs and a reverse path back to Markdown.
- **Pandoc** — the raw universal converter when you're happy wiring
  templates and a PDF toolchain yourself (md2star sits on top of it).
- **Pandoc + templates** — same engine once you've built and
  maintain your own reference-doc / template set for branding.
- **Quarto** — R/Python notebook → publication pipelines with
  executable code and citations.
- **Typst** — a fast, modern LaTeX alternative for math-heavy,
  precisely typeset PDFs.
- **Marp / Slidev / reveal.js** — Markdown or HTML slide decks with
  hot reload (slides only, no Office / branded-PDF pipeline).
- **MkDocs / Docusaurus** — documentation websites from Markdown,
  not Office or PDF deliverables.
- **LibreOffice** — native Office editing and rock-solid DOCX / PPTX
  when Markdown isn't your source.
- **Overleaf** — collaborative LaTeX with LaTeX-native PDF and
  citations.
- **Obsidian export** — Markdown notes with plugin-driven export and
  some offline local-LLM tooling.
- **Word / Google Docs** — when native Office editing or real-time
  co-editing is the actual product.

## Methodology

- We score each tool's **shipped behavior**, not its roadmap, in its
  **default configuration**, for what **most users actually use it
  for**. (Pandoc technically drives HTML → headless Chrome → PDF, but
  in practice nobody does that without a wrapper, so its PDF rating
  reflects the LaTeX-dependent default.)
- Bias check: where `md2star` is borderline between two ratings, we
  pick the **lower** one; where competitors are borderline, we pick
  the rating their typical user would defend. We will not adjust
  md2star's self-rating upward without independent confirmation.
- If you think a rating is wrong, open an issue with the tool, the
  column, the current and proposed rating, and a concrete reason (a
  feature link, a benchmark, a representative document).
