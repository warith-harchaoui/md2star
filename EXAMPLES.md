# md2star: Examples & Syntax Reference ⭐️

Welcome to the `md2star` syntax reference! Because `md2star` extends pure Pandoc by fixing annoying layout issues (especially surrounding bullet lists and `mermaid` blocks), you can format documents dynamically without breaking workflows.

Check out our pre-rendered examples inside the [`tests/examples/`](tests/examples) folder:
- 📄 **Word Document:** [`comprehensive_document.md`](tests/examples/comprehensive_document.md) ➡️ [`comprehensive_document.docx`](tests/examples/comprehensive_document.docx)
- 📊 **PowerPoint Deck:** [`comprehensive_presentation.md`](tests/examples/comprehensive_presentation.md) ➡️ [`comprehensive_presentation.pptx`](tests/examples/comprehensive_presentation.pptx)
- 🇫🇷 **French Document:** [`guide_complet_document_fr.md`](tests/examples/guide_complet_document_fr.md) ➡️ [`guide_complet_document_fr.docx`](tests/examples/guide_complet_document_fr.docx)
- 🎨 **Branded Slides:** [`branded_slides.md`](tests/examples/branded_slides.md) + [`Presentation1.pptx`](tests/examples/Presentation1.pptx) ➡️ [`branded_slides.pptx`](tests/examples/branded_slides.pptx)
- 🔖 **Footnotes:** [`footnotes_document.md`](tests/examples/footnotes_document.md) ➡️ [`footnotes_document.docx`](tests/examples/footnotes_document.docx)

To compile all examples at once:
```bash
cd tests/examples && ./run.sh
```

---

## 1. Title and Subtitles

`md2star` automatically extracts the first `# Heading` and uses it as the document **Title** metadata. If you use `--author`, the author string alongside the localized date constructs the **Subtitle**.

```bash
md2docx document.md --author "Someone Great"
```

The date is automatically localized based on the detected language:
- 🇫🇷 French → `dimanche 10 mai 2026`
- 🇪🇸 Spanish → `domingo, 10 de mayo de 2026`
- 🇩🇪 German → `Sonntag, 10. Mai 2026`

---

## 2. Mermaid Diagrams

Standard Pandoc breaks on ````mermaid` fenced code blocks. `md2star` automatically converts them to high-resolution PNGs using the Mermaid CLI locally; no data leaves your machine.

```markdown
Here is our pipeline architecture:

` ` `mermaid
graph LR;
    Raw[Markdown Source] --> Engine[md2star Preprocessor]
    Engine --> Office[DOCX/PPTX]
` ` `
```

> [!TIP]
> Mermaid rendering requires Node.js (≥16) on your PATH. The CLI is auto-installed via `npx` on first use.

---

## 3. Flawless List Formatting

Markdown writers often glue unordered lists directly to paragraphs, which breaks Pandoc output by forcing inline blocks. `md2star`'s Python AST engine automatically inserts the correct spacing so bullet lists always render cleanly.

```markdown
Our company provides:
- Seamless DOCX wrapping
- Deep PPTX grid-structuring
- Mathematics evaluations
```

*(This will always generate properly spaced Microsoft bullet items.)*

---

## 4. Multi-Column Slides (PPTX Only)

Divide your presentation slides into layout halves using `{.column}` spans:

```markdown
# Section Slide Architecture

This is my left paragraph.

{.column}

This is my right paragraph, structurally independent on the right side of the slide.
```

---

## 5. LaTeX Mathematics

Use native LaTeX expressions inside `$$` tags. Pandoc compiles them into Word / PowerPoint native Mathematical Equation objects.

```markdown
We evaluate the standard structural equation:

$$
e^{i \times \pi}+1 = 0
$$
```

---

## 6. Corporate Bibliographies

For large technical documents, `md2star` leverages native `.bib` libraries via `--bib`:

```markdown
Standard AI scaling laws have been deeply structured inside causality research metrics [@causality-pearl].
```

**Compilation:**
```bash
md2pptx presentation.md --bib references.bib --bibliography-name "References"
```

The `--bibliography-name` flag injects an automatic heading at the end of your document containing the compiled citation list.

---

## 7. Branded Templates (PPTX)

Use any custom `.pptx` as a reference template to brand your slides. If the template already has standard Pandoc layout names (`Title Slide`, `Title and Content`, etc.), use it directly:

```bash
md2pptx slides.md --reference-doc Presentation1.pptx
```

For corporate templates with non-standard layout names, use the
[md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt) sibling
tool to build a compatible reference doc, then point md2pptx at it via
`--reference-doc branded_ref.pptx`.

---

## 8. Language Detection & Date Localization

`md2star` automatically detects the language of your content and localizes dates accordingly, no configuration needed. Supported languages include French, Spanish, German, Italian, Portuguese, Dutch, Russian, Chinese, and Japanese.

```markdown
# Test du langage

J'ai un "je ne sais quoi" que je ne connais pas.
```

```bash
md2docx document.md --author "Utilisateur"
# → Subtitle: "Utilisateur, dimanche 10 mai 2026"
```

You can override with explicit metadata:
```yaml
---
lang: fr-FR
date_format: "%A %e %B %Y"
---
```

---

## 9. Page Breaks (DOCX only)

A horizontal rule (`---` on its own line) is rewritten into a hard
page break in the DOCX output. The Lua filter only fires this
mapping for the DOCX writer: PPTX keeps the default horizontal-rule
rendering, because slide structure in PPTX already comes from `## `
headings and overloading `---` there would conflict with intent.

```markdown
# Page 1

The opening paragraph stays on page 1.

---

# Page 2

After the `---`, Word starts a brand-new page automatically.

---

## Even a subsection works

The page break fires for any standalone `---`, not only between
`# Heading 1` blocks.
```

**Compilation:**
```bash
md2docx pagebreaks.md
```

> [!TIP]
> The `---` must be on its **own line**, with blank lines above
> and below; that's the standard Pandoc horizontal-rule syntax.
> A `---` inside a YAML metadata block (the document's front
> matter) is not affected: Pandoc consumes it as metadata
> delimiter before the Lua filter ever sees it.

> [!NOTE]
> No equivalent in PPTX. To force a slide break, start a new
> `## Heading`; that's how Pandoc maps Markdown to PowerPoint
> slides.

---

## 10. Footnotes

Markdown footnotes pass straight through to **native Word footnotes**:
they land in the DOCX's `word/footnotes.xml` part, so Word renders
them at the bottom of the page with clickable superscript markers and
automatic renumbering. `md2star` does no special pre-processing here;
Pandoc's default Markdown reader has the `footnotes` extension on, so
the standard `[^label]` syntax just works.

```markdown
Structured evaluation shows a 12% gain.[^bench] The gain holds even
under adversarial inputs.[^adv]

[^bench]: Measured on the internal benchmark suite, 2026-Q2 run.
[^adv]: See the red-team appendix for the full protocol.
```

Labels are arbitrary identifiers (`[^1]`, `[^bench]`, `[^note-a]`);
Word reorders and renumbers the visible markers automatically, so the
label you choose never leaks into the output. You can also inline the
note directly with the `^[...]` form:

```markdown
The result reproduces across seeds.^[Ten seeds, variance under 1%.]
```

**Compilation:**
```bash
md2docx report.md
```

> [!TIP]
> Footnotes work in DOCX and PPTX alike. DOCX gets true bottom-of-page
> footnotes; PPTX collects each slide's notes into a small **"Notes"**
> text block appended to that slide's body (endnote-style, on the
> slide itself, not the speaker-notes pane). The marker-and-text
> pairing is preserved either way.

## 11. Reverse direction: the Markdown twin

Go the *other* way: turn a finished document back into an editable
Markdown source. `md2star twin` recovers prose + GFM tables, scrapes
every embedded image out to an `assets/` folder, and re-links them,
so the result is a real source you can edit and re-render, not a flat
text dump. Works on **any PDF, or anything LibreOffice can convert to
one** (`.docx`, `.pptx`, `.odt`, `.rtf`, `.html`, …). Needs the `[ocr]`
extra: `pip install 'md2star[ocr]'`.

```bash
# report.pdf  →  report.md + assets/img-p1-0.png …
md2star twin report.pdf --out ./recovered/

# prose + tables only, no scraped rasters
md2star twin report.pdf --no-images
```

Add `--diagrams` (opt-in, needs `[ocr]` + a local Ollama) and md2star
classifies each scraped image with a local vision model into three
buckets: **photos stay as PNGs**, **node-and-edge diagrams are
re-authored as Mermaid**, and other **vector figures** (charts, plots,
logos, icons, line drawings) are re-authored as an editable **SVG**
written beside the raster. Every candidate, Mermaid or SVG, is
verified by the same *target-matching eyeball loop*: render it (the
same `mmdc` the forward path uses for Mermaid; a detected rasteriser,
`cairosvg` / `rsvg-convert` / `inkscape` / ImageMagick, for SVG),
compare it against the scraped original with the VLM, and iterate until
it matches. The original PNG is always kept as a commented fallback, so
a reconstruction is never a lossy dead end.

```bash
# diagrams become editable Mermaid; photos stay PNGs
md2star twin architecture.pdf --diagrams --out ./recovered/
```

A recovered diagram lands in the twin like this: editable code, with
the source raster preserved beneath it:

````markdown
```mermaid
flowchart LR
    A[Client] --> B[API]
    B --> C[(Database)]
```

<!-- source figure: ![](assets/img-p2-0.png) -->
````

> [!TIP]
> The twin is the reverse of md2star's own output: render Markdown →
> DOCX/PDF with the forward CLIs, then `md2star twin` reads it back.
> Because a reconstructed diagram is Mermaid (which the forward path
> renders natively), the round-trip `md → doc → twin → doc` keeps
> diagrams as code the whole way.

### The twin in the GUI and over HTTP

The twin is not CLI-only. In the full editor (`md2star gui`), the
**Import** control has two toggles:

- **Twin**: keep scraped images. The recovered `<stem>.md` **and** an
  `assets/` folder are written into the folder you have open (so the
  image links resolve when you re-render), and the sidebar refreshes.
  Requires an open folder; plain **Import** stays a text-only load.
- **Mermaid**: additionally re-author node-and-edge figures via the
  local VLM (needs the `[ocr]` stack + Ollama). Implies **Twin**.

Over the HTTP API (`md2star-api`), `POST /extract` takes the same
options as form fields: text-only returns JSON, twin returns a zip of
`<stem>.md` + `assets/`:

```bash
# Text-only (JSON: {"filename": "report.md", "markdown": "..."})
curl -sF file=@report.pdf http://localhost:8000/extract

# Full twin (a report.zip containing report.md + assets/)
curl -sF file=@report.pdf -F twin=true \
     -o report.zip http://localhost:8000/extract

# Twin + AI diagram reconstruction (implies twin; needs the [ocr] stack)
curl -sF file=@architecture.pdf -F diagrams=true \
     -o architecture.zip http://localhost:8000/extract
```

## 12. Template-Intelligent PPTX

Pandoc's PPTX writer only ever reaches its bundled template's ~7 generic
named layouts. `md2pptx --smart-layout --template <designer.pptx>` maps
each Markdown slide onto a **real designer template's own layout
vocabulary** instead: an LLM reads each slide's content against a catalog
of the template's named layouts and picks the best fit, a **VLM visually
confirms or overrides** that pick against the candidate layouts' actual
thumbnails (not just their captions), and a `python-pptx` assembler builds
the deck directly on the chosen layout per slide. Needs the `[pptx]`
extra (`pip install 'md2star[pptx]'`) and a resolved local LLM+VLM engine
(the same `best_engine_ai_helper` stack `--lint`/`twin --diagrams` use).

```bash
md2pptx talk.md --template ./brand/Company-Template.pptx --smart-layout
```

Add `--eyeball-iterations N` (default 0, off) to run a **target-matching
Ralph Eyeball Loop** after assembly: each pass renders the deck, shows the
vision model both a candidate slide and the chosen layout's own catalog
thumbnail, and applies bounded fixes (shrink an overflowing title, cap the
bullet count, grow an undersized image) — never touching the picture
itself, only the spec the assembler re-reads.

```bash
md2pptx talk.md --template ./brand/Company-Template.pptx \
    --smart-layout --eyeball-iterations 2
```

> [!TIP]
> `--no-visual-confirm` skips the VLM tie-break stage (cheaper, text-only
> layout selection) when you want the LLM's first pick taken as final.

### The designer's own slides, not just their layouts

A layout carries the background and the placeholder boxes. The accent bars,
the numbered step chevrons, the decorative rules — the bespoke shapes that
make a deck look like *itself* — live one level further in, on the
template's **example slides**. `--reference-slides` clones the example page
for the chosen layout and replaces its content with yours:

```bash
md2pptx talk.md --template ./brand/Company-Template.pptx \
    --smart-layout --reference-slides
```

```text
Wrote: talk.pptx (14/14 slides, 11 from the template's own pages)
```

Your title goes in their title, your bullets in their columns — keeping
their bullet glyph, face, size and colour — and your image in their photo
slot, contain-fitted so it is never stretched. Everything they drew around
that content stays exactly where they drew it.

Nothing they *wrote* comes with it. Every text frame on a cloned page is
either filled with your content or retired, and retiring knows the
difference between filler and design: ornament stays (the "01" of a
numbered step **is** the design), a bare text box goes, and an autoshape is
emptied but kept, because a chevron is a drawn object. Their stand-in photo
is dropped from the file itself, not merely from the slide, and their
hyperlinks do not outlive the words they were attached to.

A page that cannot honestly carry a slide is **declined, not half-filled**:
a three-column design needs at least three bullets; an image slide needs a
picture slot, and a page built around a photograph needs an image (their
stand-in has to go, and the rest of the page was composed around the shape
of it); and a page with a chart or a table on it is refused outright, since
no replacement can restate someone else's numbers. A page is also refused
when your text would have to **shrink past 12 pt** to fit the frames the
designer sized for their own line — the question asked is not "does it
overflow" but "how small would it have to get", because a renderer answers
overflow by quietly shrinking the type. Among the pages that do
qualify, a slide with an image takes the one whose slot is **biggest** —
contain-fitting means that slot is the size the reader actually sees.
Declined slides fall through to the normal assembler, so the flag only ever
adds — and a template distributed as layouts alone, with no example pages,
builds exactly as it would without it.

Add `--eyeball-iterations N` and the Ralph Eyeball Loop gets two things it
does not have on any other path. Its **target** becomes the designer page
each slide was cloned from — the candidate is literally that page with your
words in it, so anything the vision model sees as different is about *this*
slide, not about the layout family. And it gains a **fix it never had**:
when a slide is flagged with no bounded correction to apply (`too_empty`
and a misalignment never had one), it moves that slide onto **another of
the designer's demonstrations of the same layout** before considering a
layout swap.

```bash
md2pptx talk.md --template ./brand/Company-Template.pptx \
    --smart-layout --reference-slides --eyeball-iterations 2
```

```text
eyeball loop: slide 4 — example page 31 is not carrying it (a void on the
  right half); trying another page of Split1_lime
```

A designer who demonstrated one layout five ways has given you five
compositions; reaching for another of theirs is a smaller and truer
correction than abandoning the layout they chose. Only when every page has
been judged and refused does the slide fall through — first to a different
layout, then to the bare-layout assembler, which can always place it.

### Speaker notes

A Pandoc `::: notes` block is the presenter's script, and it goes to the
notes pane on both paths — the ordinary Pandoc one and `--smart-layout`:

```markdown
## Q3 revenue

- up 18% year on year

::: notes
The 18% is provisional until the audit closes. Do not take questions on
the European segment.
:::
```

### The layout audit

Every `--smart-layout` run ends with a deterministic audit of the deck it
just wrote — no model, no render, no network, so it reports the same thing
on a laptop with no LLM at all:

```text
Wrote: talk.pptx (14/14 slides)
layout audit: 2 findings on 2 slides (1 overlap, 1 overrun)
```

It is also a tool on its own, pointed at **any** presentation — one a
colleague sent you, one PowerPoint made, one you built years ago:

```bash
md2star audit theirs.pptx            # human-readable, one line per finding
md2star audit theirs.pptx --json     # same findings, machine-readable
md2star audit theirs.pptx --strict   # also fail on `overrun`
```

It exits `1` when it finds a **defect** (off-slide, overlap, ghost
placeholder, illegible type) and `0` when it finds only observations, so it
drops straight into a CI job or a pre-commit hook. The deck is read, never
written.

Run with `-v` to see each finding with its measurement:

```text
slide 7: overlap — 'Title 1' and 'TextBox 4' share 38% of the smaller box
slide 9: overrun [TextBox 3] — text needs 1.6x its box at 16pt (fits at ~13pt)
```

The five checks are `off-slide`, `overlap` (text over text — text over a
*picture* is a composition, not a bug), `ghost-placeholder`,
`illegible-type` (under 12 pt) and `overrun`. An `overrun` is an
observation rather than an error: PowerPoint auto-shrinks the text, so the
consequence is quiet, and the finding tells you what size the slide really
is. Available as a library call too:

```python
from pathlib import Path
from md2star.pptx_audit import audit, summarise

findings = audit(Path("talk.pptx"))
print(summarise(findings, slides=14))
```

`--smart-layout` bypasses Pandoc entirely for that run — `--template`
plays the role a Pandoc reference-doc normally plays. The ordinary
`md2pptx talk.md` (no `--smart-layout`) path is unaffected and stays the
default. See `docs/design/pptx-template-intelligence.md` for the full
design (catalog format, layout-selection prompts, the eyeball-loop shape).
