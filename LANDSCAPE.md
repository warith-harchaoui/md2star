# Landscape — md2star vs the competition

Honest competitive comparison. Picking the right tool matters more
than picking ours: if your team is co-editing in real time, Google
Docs beats md2star and we'll say so.

This document is **maintained by hand** and reflects the state of
each project as of mid-2026. If you spot something out of date,
open an issue.

## Scoring rubric

Each cell is rated 1–5 stars (or `—` for "not applicable").

| Stars | Meaning |
|---|---|
| ⭐️⭐️⭐️⭐️⭐️ | Best-in-class for this dimension. Hard to beat. |
| ⭐️⭐️⭐️⭐️ | Great. Production-grade, minor caveats. |
| ⭐️⭐️⭐️ | Adequate. Works, but with rough edges or limitations. |
| ⭐️⭐️ | Weak. Possible but painful, or low quality output. |
| ⭐️ | Absent / poor. Practically unusable for this dimension. |
| — | Not applicable (e.g. PPTX rating for a slides-only tool's "DOCX" column). |

We grade ourselves honestly. md2star does not get 5 stars on every
row.

## Column legend

| Column | Means |
|---|---|
| **MD-src** | Markdown is the native source format (not just import/export). |
| **WYSIWYG** | True what-you-see-is-what-you-get inline editing (not split-pane preview). |
| **DOCX** | Quality and reliability of `.docx` output. |
| **PPTX** | Quality and reliability of `.pptx` output. |
| **PDF** | PDF output without requiring a LaTeX toolchain. |
| **Cite** | Citations / bibliography (BibTeX, CSL, Zotero, etc.). |
| **Diag** | Diagrams (Mermaid, Graphviz, PlantUML) built-in. |
| **Math** | Mathematical typesetting (LaTeX `$…$` / `$$…$$` syntax) — inline and display, rendered correctly in the chosen output format. |
| **Local-LLM** | Optional local-LLM features (lint, summaries, merge proposals) via Ollama or similar. |
| **Offline** | Works fully offline by default; no silent network calls. |
| **OSS** | Free and open-source under a permissive or copyleft license. |
| **RT-collab** | Real-time co-editing with presence (cursors, selections, who's typing). |
| **Git-async** | Git-friendly async collab on the source files (clean diffs, sane merges). |
| **Mobile** | First-class mobile editing experience (iOS / Android, not just "works in a browser"). |

## The comparison table

| Tool | MD-src | WYSIWYG | DOCX | PPTX | PDF | Cite | Diag | Math | Local-LLM | Offline | OSS | RT-collab | Git-async | Mobile |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **md2star** (us) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ |
| Pandoc (CLI alone) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | — | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | — | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️ |
| Quarto | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ |
| Curvenote | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ |
| Stencila | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ |
| Marp / Slidev | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | — | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | — | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | — | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ |
| Typora | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ |
| Zettlr | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ |
| Obsidian + plugins | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| StackEdit | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ |
| HedgeDoc / HackMD | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️ |
| CryptPad | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ |
| Notion | ⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| GitBook | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ |
| Google Docs | ⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| Overleaf | ⭐️ | ⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ |
| MS Word / Office | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ |

## How to read this

### When md2star is the right choice

You should pick md2star when **all** of these apply:

- Your source-of-truth is Markdown (you want plain-text diffs, you
  want to grep your archive, you want zero proprietary format risk).
- You produce DOCX, PPTX, or PDF as the polished deliverable
  (research papers, internal reports, client slides, training
  material, a book draft going to a copy editor).
- You value offline-by-default and zero telemetry.
- Your team is small (1-10) and async, OR you work solo across
  multiple devices.
- You're OK with a split-pane editor (markdown source + live preview)
  rather than true inline WYSIWYG.

### When something else is the right choice

| If you need... | Use |
|---|---|
| Real-time co-editing with cursors | **HedgeDoc** (OSS, self-host) or **Google Docs** (hosted) |
| Browser-only editing from any device (incl. phone) without installing anything | **StackEdit** for Markdown (PWA; direct GitHub/GitLab repo read/write; no DOCX/PPTX export) or **Overleaf** for LaTeX (real-time collab + LaTeX-native PDF) |
| Best-in-class DOCX/PPTX editing (not generation) | **MS Word / PowerPoint** |
| Academic LaTeX with collab | **Overleaf** |
| Mobile-first markdown editing | **Obsidian** (iOS + Android apps) |
| True WYSIWYG single-pane markdown | **Typora** or **iA Writer** |
| Zotero-integrated academic writing | **Zettlr** |
| R/Python notebook → publication pipeline | **Quarto** |
| Real-time collab on a scientific paper with citations + math + LaTeX-grade PDF (closest thing to "Overleaf for Markdown") | **Curvenote** (built on MyST Markdown) |
| Open-source scientific publishing platform with executable code cells and collab | **Stencila** |
| Git-backed docs site with browser WYSIWYG editor + two-way GitHub sync | **GitBook** (closed-source editor) or **MkDocs / Docusaurus** (OSS, no in-browser editor) |
| Slides-only Markdown with hot-reload | **Marp** or **Slidev** |
| End-to-end-encrypted collab | **CryptPad** |
| Team wiki with WYSIWYG | **Notion** (proprietary) or **Outline** (OSS) |

> **A note on the GUI ratings.** Several rows below (WYSIWYG,
> Mobile, Git-async) describe the local web editor. That GUI was
> removed from the core CLI wheel in v2.0 to keep the PyPI package
> lean, and was **restored in v2.6.0 bundled in the core package**
> (invoked via `md2star gui`; no extra to install). The star
> ratings here reflect the author's editorial judgment of the
> product *vision* — the GUI-dependent capabilities now ship in
> the default install, not as an opt-in extra.

### Where md2star deliberately doesn't compete

- **Real-time collab**: 1 star, on purpose. Adding presence + CRDT
  would change the product into a different one. See
  `.private/GIT.md` for the analysis.
- **WYSIWYG**: 3 stars. The split-pane preview is a deliberate
  choice — it keeps the Markdown source clean and reviewable. The
  editor itself is back in v2.6.0, bundled in the core package; a
  single-pane WYSIWYG mode remains an investigation only and is
  not committed.
- **Mobile**: 2 stars. The local web GUI (restored in v2.6.0,
  bundled in the core package) binds to `127.0.0.1` and assumes
  desktop. A Tauri-based mobile shell is on the long-term backlog
  but not promised.
- **Local-LLM**: 3 stars today (Ollama-based lint, optional). The
  planned git awareness inside the (now core) GUI (ROADMAP P2,
  v2.2+) would add commit-message generation and LLM-assisted
  merge, which moves this toward 4 stars; the Community Edition
  will support both local and BYO OpenAI-compatible endpoints,
  with Premium hosting our own model for users who don't want to
  run inference themselves.

### Where md2star wants to improve

| Dimension | Current | Target | How |
|---|---|---|---|
| Git-async | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | Git awareness inside the (now core) GUI (ROADMAP P2, v2.2+): read-only status → opt-in commit-on-save → opt-in push-on-save, rolled out in three phases. |
| Local-LLM | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | The `md2star[ai]` extra (ROADMAP P1, v2.1) plus the git-awareness LLM features (commit messages, merge proposals). |
| Mobile | ⭐️⭐️ | ⭐️⭐️⭐️ | Document the "use Working Copy + a hosted render endpoint" workflow as an explicit supported path. |
| WYSIWYG | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ | The split-pane editor is back in v2.6.0, bundled in the core package. A Lexical / TipTap single-pane mode is an investigation only; not committed. |
| Cite | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | Add Zotero Better-BibTeX integration (ROADMAP P2). |

### Where md2star will probably stay where it is

- **RT-collab** stays at ⭐️ — out of scope for the open-source
  Community Edition. If we ever ship real-time, it's a Premium
  product that runs on our servers (HedgeDoc-style), not a CE
  feature.
- **DOCX / PPTX / PDF** are already ⭐️⭐️⭐️⭐️. Reaching ⭐️⭐️⭐️⭐️⭐️ requires
  matching MS Office's native rendering quality, which means
  building an Office-compatible layout engine. Not realistic, not
  worth it.

## Methodology

- We score the tool's **shipped behavior**, not its roadmap.
- We score the **default configuration** unless we note otherwise.
  ("Typora + a hand-tuned Pandoc template" is not the default Typora
  experience.)
- We score what **most users actually use the tool for**. Pandoc
  technically supports HTML output → headless Chrome → PDF; in
  practice nobody does this without a wrapper, so Pandoc's PDF
  rating reflects the LaTeX-dependent default.
- Bias check: where md2star is borderline between two ratings, we
  pick the **lower** one. Where competitors are borderline, we pick
  the rating their typical user would defend.

## Disagreements

If you think a rating is wrong, open an issue with:

1. The tool and the column.
2. The current rating and your proposed rating.
3. A concrete reason (a feature link, a benchmark, a representative
   document).

We will not adjust md2star's self-rating upward without independent
confirmation; we will adjust competitors' ratings in either
direction based on evidence.
