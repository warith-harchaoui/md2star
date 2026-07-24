# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/md2star/blob/main/PAYSAGE.md) · 🇬🇧 English

Honest competitive comparison in the "Markdown → polished document"
space, benchmarked against `md2star`. Ratings are ⭐ (1) to
⭐⭐⭐⭐⭐ (5), scored on `md2star`'s intended job — take a Markdown
source of truth and produce a deliberate-looking DOCX / PPTX / PDF,
offline by default, with clean git-friendly diffs. A tool optimised
for a very different job (real-time co-editing, LaTeX-native
authoring) is not penalised — the score just reflects fit to *this*
niche. Picking the right tool matters more than picking ours: if your
team is co-editing in real time, Google Docs beats md2star and we say
so.

We grade ourselves honestly — `md2star` does not get 5 stars on every
row. This document is maintained by hand and reflects the state of
each project as of mid-2026; open an issue if something is out of
date.

## At a glance

<!-- TABLE:START -->
| Markdown Conversion | MD-src | WYSIWYG | DOCX | PPTX | PDF | Cite | Diagrams | Math | Local-LLM | Offline | OSS | RT-collab | Git-async | Mobile |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **md2star** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Pandoc | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| Quarto | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Curvenote | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Stencila | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Marp / Slidev | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Typora | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Zettlr | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ |
| Obsidian + plugins | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| StackEdit | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| HedgeDoc / HackMD | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| CryptPad | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| Notion | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| GitBook | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Google Docs | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| Overleaf | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| MS Word / Office | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/landscape.png)

The map is a 2-D summary of the fourteen criteria, so read it as a shape, not a scoreboard. `md2star` is at the top-right corner. The axes read **Horizontal — Collaborative ↔ Open** and **Vertical — Mobile ↔ Documented**.
<!-- FIGURE:END -->

## Column legend

The criteria, in short:

- **MD-src** — Markdown is the native source format, not just an
  import/export path.
- **WYSIWYG** — true inline what-you-see-is-what-you-get editing, not
  split-pane preview.
- **DOCX / PPTX / PDF** — quality and reliability of `.docx`, `.pptx`
  and PDF output (PDF without requiring a LaTeX toolchain).
- **Cite** — citations / bibliography (BibTeX, CSL, Zotero).
- **Diagrams** — Mermaid / Graphviz / PlantUML built in.
- **Math** — LaTeX `$…$` / `$$…$$` typesetting, inline and display,
  rendered correctly in the chosen output.
- **Local-LLM** — optional local-LLM features (lint, summaries, merge
  proposals) via Ollama or similar.
- **Offline** — works fully offline by default, no silent network
  calls.
- **OSS** — free and open-source under a permissive or copyleft
  license.
- **RT-collab** — real-time co-editing with presence (cursors,
  selections, who's typing).
- **Git-async** — git-friendly async collaboration on the source
  files (clean diffs, sane merges).
- **Mobile** — first-class mobile editing, not just "works in a
  browser".

Cells that would be "not applicable" in the hand-maintained rubric
(e.g. a PPTX rating for a slides-only tool) score ⭐ here, so the
machine-read table stays pure stars — read those as "not a fit for
this dimension".

## Positioning

`md2star` deliberately sits at the intersection of a **Markdown
source of truth** (plain-text diffs, greppable archive, zero
proprietary-format risk) and **polished document output** (a DOCX,
PPTX or PDF that looks like a deliberate document, not a raw export).
It intentionally does **not** try to compete with Google Docs on
real-time co-editing, Overleaf on LaTeX-native authoring, or MS Word
on native rendering fidelity.

You should pick `md2star` when **all** of these apply:

- Your source of truth is Markdown — you want plain-text diffs, a
  greppable archive, and no proprietary-format risk.
- You produce DOCX, PPTX or PDF as the polished deliverable (papers,
  internal reports, client slides, training material, a book draft
  headed to a copy editor).
- You value offline-by-default and zero telemetry.
- Your team is small (1–10) and async, or you work solo across
  several devices.
- You're fine with a split-pane editor (Markdown source + live
  preview) rather than true inline WYSIWYG.

Where `md2star` deliberately doesn't compete:

1. **Real-time collab** — 1 star, on purpose. Adding presence + CRDT
   would make it a different product. If real-time ever ships, it is
   a hosted Premium product, not a Community-Edition feature.
2. **WYSIWYG** — 3 stars. The split-pane preview keeps the Markdown
   source clean and reviewable; the local editor ships bundled in
   the core package (`md2star gui`), while a single-pane WYSIWYG mode
   remains an investigation, not a commitment.
3. **Mobile** — 2 stars. The local web GUI binds to `127.0.0.1` and
   assumes a desktop; a mobile shell is on the long-term backlog, not
   promised.

## When to pick what

- **`md2star`** — Markdown-sourced documents that must ship as a
  polished DOCX / PPTX / PDF, offline, with clean git diffs.
- **Pandoc** — when you want the raw universal converter and are
  happy wiring templates and a PDF toolchain yourself (md2star sits
  on top of it).
- **Quarto** — R/Python notebook → publication pipelines with
  executable code and citations.
- **Curvenote / Stencila** — real-time or executable scientific
  publishing on MyST Markdown with citations, math and collab.
- **Typora / iA Writer** — true single-pane WYSIWYG Markdown editing.
- **Obsidian** — mobile-first Markdown with a large plugin ecosystem.
- **Zettlr** — Zotero-integrated academic writing in Markdown.
- **Marp / Slidev** — slides-only Markdown with hot reload.
- **StackEdit** — browser-only Markdown from any device with direct
  GitHub/GitLab read/write (no DOCX/PPTX export).
- **HedgeDoc / CryptPad** — real-time (and end-to-end-encrypted)
  co-editing you can self-host.
- **Overleaf** — collaborative LaTeX with LaTeX-native PDF.
- **Google Docs / Notion / MS Word** — when real-time collab, a team
  wiki, or native Office editing is the actual product.

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
