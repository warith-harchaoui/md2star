# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/md2star/blob/main/PAYSAGE.md) · 🇬🇧 English

Honest competitive comparison in the "Markdown → polished document"
space, benchmarked against `md2star`. Ratings are ⭐ (1) to
⭐⭐⭐⭐⭐ (5), scored on `md2star`'s intended job: take a Markdown
source of truth and produce a deliberate-looking DOCX / PPTX / PDF,
offline by default, with clean git-friendly diffs. A tool optimised
for a very different job (native Office co-editing, LaTeX-native
typesetting) is not penalised; the score just reflects fit to *this*
niche. Picking the right tool matters more than picking ours: if your
team lives in native Office documents, Word / Google Docs beats
md2star and we say so.

We grade ourselves honestly: `md2star` does not get 5 stars on every
row. This document is maintained by hand and reflects the state of
each project as of mid-2026; open an issue if something is out of
date.

## At a glance

<!-- TABLE:START -->
| Markdown Conversion | Office+PDF | Citations | Diagrams | Math | Branded | One-cmd CLI | Offline | Local-LLM | Reverse-MD | Template-fit | Self-check | Editable |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **md2star** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Pandoc | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Pandoc + templates | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| Typst | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ |
| md2pptx | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Marp | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| Slidev | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐ |
| reveal.js | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| MkDocs | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| Docusaurus | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ |
| LibreOffice | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Overleaf | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐ |
| Obsidian export | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ |
| Gamma / Copilot | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Presenton | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
| PPTAgent | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Word / Google Docs | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/md2star/main/assets/landscape.png)

The map is a 2-D summary of the twelve criteria, so read it as a shape, not a scoreboard. `md2star` is at the top-right corner. The axes read **Horizontal — Scholarly ↔ Designed** and **Vertical — Visual ↔ Comprehensive**, and they are the poles the figure itself is drawn with: rebuild it from the table above with `scripts/positioning.py`.
<!-- FIGURE:END -->

## Column legend

The twelve criteria, in short:

- **Office+PDF**: quality and reliability of `.docx`, `.pptx` and PDF
  output (PDF without requiring a LaTeX toolchain).
- **Citations**: citations / bibliography (BibTeX, CSL, Zotero).
- **Diagrams**: Mermaid / Graphviz / PlantUML rendered into the
  document.
- **Math**: LaTeX `$…$` / `$$…$$` typesetting, inline and display,
  rendered correctly in the chosen output.
- **Branded**: house-style templates (fonts, colours, cover, headers/
  footers) so output looks deliberate, not a raw export.
- **One-cmd CLI**: a single command turns Markdown into the
  deliverable, with no multi-step toolchain to wire up by hand.
- **Offline**: works fully offline by default, no silent network
  calls.
- **Local-LLM**: optional local-LLM features (lint, summaries, merge
  proposals) via Ollama or similar.
- **Reverse-MD**: round-trips a finished DOCX / PPTX / PDF back into
  an editable Markdown twin.
- **Template-fit**: for PPTX, does the tool decide *which slide of a
  designer's own template* each piece of content belongs on, judged
  against how much content there actually is? Worth separating from
  **Branded**, because the two are different claims: Branded is "the
  output carries the right fonts and colours", Template-fit is "the
  content landed on the right slide". A tool can score well on the
  first and badly on the second — pandoc reaches about seven named
  layouts by a fixed content-shape heuristic, whatever the template
  holds.

  PowerPoint's Designer rates highly here and deserves to: it reads
  the text and images on a slide and proposes balanced arrangements.
  The difference is whose vocabulary it draws on — Designer composes
  from Microsoft's own catalogue, while the job md2star is doing is
  mapping onto *your* designer's layouts and leaving their design
  alone.

- **Self-check**: does the tool inspect **its own output** and tell you
  what is wrong with it — text off the canvas, two shapes on top of
  each other, type too small to read, more text than its box holds —
  or does it hand you a file and assume the render was fine? Most
  converters are in the second group, which is why a bad slide is
  normally found by a human opening the deck. LaTeX's "Overfull \hbox"
  warning is the oldest example of the first group; PowerPoint's
  Accessibility Checker is the most familiar one.

- **Editable**: what you can still *do* with the file afterwards. Real
  text in real placeholders, an outline PowerPoint can read, native
  shapes you can nudge — against a flat artefact that merely looks
  right, which is what an export of rendered HTML or a picture-perfect
  AI deck usually hands you. The dimension is borrowed from
  [SlidesGen-Bench](https://arxiv.org/html/2601.09487)'s *Presentation
  Editability Index* (L0–L5, parsed from the file's own structure),
  whose headline finding is worth repeating: across the systems it
  measured, aesthetic strength **inversely correlated** with editability
  depth, and nothing scored well on both. A "Structural Barrier", in its
  words. md2star's whole bet is that the barrier is an artefact of
  generating design instead of inheriting it: take the design from a
  human designer's own template and the output can be native OOXML all
  the way down, which is also how PPTAgent reaches the same top mark.

Cells that would be "not applicable" in the hand-maintained rubric
(e.g. an Office+PDF rating for a slides-only or website-only tool)
score ⭐ here, so the machine-read table stays pure stars; read those
as "not a fit for this dimension".

### Two rows the 2026 literature added

**Presenton** is the closest thing to an open-source Gamma: self-hosted,
bring-your-own-model, prompt-or-document in and PPTX/PDF out. It shares
md2star's offline-and-local-LLM ground and differs on the only question
that matters for this table — it *writes* the deck, while md2star maps a
Markdown source of truth onto a designer's template and leaves the design
alone.

**PPTAgent** ([EMNLP 2025](https://aclanthology.org/2025.emnlp-main.728/))
is the research system md2star's `--reference-slides` path owes its
central idea to: edit a *reference slide*, not a layout. It earns the
table's other five on Template-fit for exactly that reason, and the top
Editable mark because an edited reference slide is native by
construction. Where it differs: it drafts the content as well as the
deck, its PPTEval self-check is an evaluation harness for the paper
rather than a gate the tool runs on your file, and it needs a model for
every step. md2star keeps the author's words, runs its audit with no
model at all, and degrades to a plain Pandoc conversion when no engine
is available.

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

- Your source of truth is Markdown: you want plain-text diffs, a
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

1. **Math**: 3 stars, its weakest row. Deep LaTeX math belongs to
   Typst, Overleaf or raw Pandoc; md2star renders everyday inline and
   display math well but is not a full LaTeX substitute.
2. **Office+PDF**: 4 stars. Output is deliberate and reliable, but
   native editors (Word / Google Docs, LibreOffice) and Overleaf beat
   it on raw rendering fidelity in their own format.
3. **Citations & Diagrams**: 4 stars each. Broad enough for reports
   and papers; Pandoc and Quarto go further on exotic CSL styles and
   the long tail of diagram engines.

## When to pick what

- **`md2star`**: Markdown-sourced documents that must ship as a
  polished, branded DOCX / PPTX / PDF, offline, one command, with
  clean git diffs and a reverse path back to Markdown.
- **Pandoc**: the raw universal converter when you're happy wiring
  templates and a PDF toolchain yourself (md2star sits on top of it).
- **Pandoc + templates**: same engine once you've built and
  maintain your own reference-doc / template set for branding.
- **Quarto**: R/Python notebook → publication pipelines with
  executable code and citations.
- **Typst**: a fast, modern LaTeX alternative for math-heavy,
  precisely typeset PDFs.
- **md2pptx**: Markdown → PPTX with no Pandoc in the way, and by far
  the largest authoring vocabulary of anything here (cards, funnels,
  task slides, a generated table of contents, inline Python hooks).
  Pick it when you want that vocabulary and are happy learning it;
  md2star's bet is the opposite one, that the Markdown stays plain and
  the *template* carries the design.
- **Marp / Slidev / reveal.js**: Markdown or HTML slide decks with
  hot reload (slides only, no Office / branded-PDF pipeline).
- **Gamma / Copilot**: when you have no source document and want a
  deck generated from a prompt, in the cloud, and are happy for the
  tool's own catalogue to be the design.
- **MkDocs / Docusaurus**: documentation websites from Markdown,
  not Office or PDF deliverables.
- **LibreOffice**: native Office editing and rock-solid DOCX / PPTX
  when Markdown isn't your source.
- **Overleaf**: collaborative LaTeX with LaTeX-native PDF and
  citations.
- **Obsidian export**: Markdown notes with plugin-driven export and
  some offline local-LLM tooling.
- **Word / Google Docs**: when native Office editing or real-time
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

## Sources and as-of date

**Sources recorded 2026-10-27, against md2star v3.10.0.** The md2star column
was re-read off this repository at that version. The competitor columns come
from the mid-2026 reading noted at the top of this document, graded from each
project's own published documentation — so read them as "as of mid-2026", and
open an issue when a project has moved.

The two halves of the table are sourced differently, and the difference is
worth stating plainly:

- **md2star's own row** is read off the code, not off the README. Every claim
  in it has a command behind it: `md2star doctor` for what is actually
  installed, `md2docx --bib` for Citations, `md2docx` on a `mermaid` fence for
  Diagrams, `md2star twin` for Reverse-MD, `md2star audit` for Self-check, and
  `md2pptx --smart-layout --template` for Template-fit — the one row that needs
  a resolvable local LLM+VLM before it can be exercised at all. The Editable
  mark is the file itself: real text in real placeholders, which is what the
  audit walks.
- **Every other row** is graded from that project's own published
  documentation, read the way a prospective user reads it: default
  configuration, documented behaviour, no private builds. Where the
  documentation is silent, the cell scores ⭐ rather than a guess.

Primary sources, by row:

- **Pandoc**, **Pandoc + templates** — [the Pandoc manual](https://pandoc.org/MANUAL.html):
  `--reference-doc`, `--citeproc`, and the PPTX writer's named layouts.
- **Quarto** — [the Quarto guide](https://quarto.org/docs/guide/).
- **Typst** — [the Typst documentation](https://typst.app/docs/).
- **md2pptx** — [MartinPacker/md2pptx](https://github.com/MartinPacker/md2pptx)
  and its user guide, which is also where its authoring vocabulary is listed.
- **Marp** — [marp.app](https://marp.app/) · **Slidev** — [sli.dev](https://sli.dev/)
  · **reveal.js** — [revealjs.com](https://revealjs.com/).
- **MkDocs** — [mkdocs.org](https://www.mkdocs.org/) · **Docusaurus** —
  [docusaurus.io](https://docusaurus.io/).
- **LibreOffice** — [libreoffice.org](https://www.libreoffice.org/).
- **Overleaf** — [overleaf.com](https://www.overleaf.com/).
- **Obsidian export** — [obsidian.md](https://obsidian.md/) and its community
  plugin directory; the row grades the plugin ecosystem, not the core app.
- **Gamma / Copilot** — [gamma.app](https://gamma.app/) and
  [Copilot in PowerPoint](https://support.microsoft.com/en-us/powerpoint/welcome-to-copilot-in-powerpoint).
- **Presenton** — [presenton/presenton](https://github.com/presenton/presenton):
  Apache-2.0, self-hosted via Docker, with Ollama / LM Studio among its
  supported backends — which is what earns its Offline and Local-LLM stars.
- **PPTAgent** — [EMNLP 2025](https://aclanthology.org/2025.emnlp-main.728/)
  and [icip-cas/PPTAgent](https://github.com/icip-cas/PPTAgent).
- **Word / Google Docs** — [Microsoft Word](https://www.microsoft.com/microsoft-365/word)
  and [Google Docs](https://workspace.google.com/products/docs/).

The **Editable** column is not our own invention: its levels are the
Presentation Editability Index (L0–L5) of
[SlidesGen-Bench](https://arxiv.org/abs/2601.09487), cited in the column
legend above.

What is deliberately absent: no timing figures, no benchmark scores, no
version numbers pinned on other people's software. A star here is a dated
judgement about fit to one niche, which is honest in a way an undated
measurement would not be. When a rating has gone stale — and in this space
some will — the [Methodology](#methodology) section says what a useful
correction looks like.
