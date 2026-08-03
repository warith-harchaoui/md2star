# Template-intelligent PPTX — design note (branch `jsk`)

> **Thesis.** A great PowerPoint deck starts from a template a *human graphic
> designer* made. md2star's job is **not** to design slides — it is to **map
> authored Markdown content onto the right slide of the designer's template**,
> then **verify the result looks like the designer intended** with a
> Ralph Eyeball Loop. An LLM chooses the layout per slide; a VLM checks the
> render and drives revisions. The design itself always comes from the template.

Author: Warith Harchaoui — <warith.harchaoui@deraison.ai>
Status: investigation / design (not yet implemented). Reference template:
`assets/templates/pptx/Jellysmack-Presentation-Template.pptx` (git-ignored, see §8).

---

## 1. The problem, precisely

Pandoc's PPTX writer can only reach **~7 named layouts** (`Title Slide`,
`Section Header`, `Title and Content`, `Two Content`, `Comparison`,
`Content with Caption`, `Blank`) and it picks among them by a fixed
*content-shape heuristic* — md2star does nothing to steer it (confirmed: no
`--slide-level`, no Lua layout branch, no pptx post-processing; the bundled
`template.pptx` ships exactly those named layouts and pandoc matches on the
names). See `md2star/cli.py:_run_pandoc` and `md2star/data/filters/md2star.lua`.

A real designer template is **far** richer. The Jellysmack template
(`type="screen16x9"`, 9144000×5143500 EMU) contains:

| Artefact | Count |
|---|---|
| Example/showcase slides | **64** |
| Slide **layouts** | **115** (across 3 masters → ~38 unique) |
| Slide masters | 3 |
| Media assets | 224 |

The 64 example slides resolve to **22 distinct named layouts** — the designer's
actual vocabulary. Pandoc can address maybe 2–3 of them by accident; the other
~19 are unreachable today. That gap is the whole opportunity.

## 2. The designer's layout vocabulary (evidence)

Contact sheet of all 64 slides: `.private/jsk/jellysmack-contact-sheet.png`
(regenerate with the commands in §9). The named layouts the 64 examples use,
grouped into **content archetypes** an LLM can target:

| Archetype (semantic role) | Designer layout names (examples) | Markdown that should map here |
|---|---|---|
| Cover / title | `TITLE_AND_BODY`, `title1`–`title9` | first `#` H1 (deck title + subtitle) |
| Section divider | `INTRO_2`, `Segmentation 1A/1E/2A`, "MAIN THEME: …" | a lone `#`/`##` with no body |
| Big number / stat | (Numbers slides — `100`, `+123%`, `9.4Bn`) | a slide whose body is one big figure |
| Bold statement / big word | `big text`, `big text 1A` ("How high can you go?") | a short punchy line, no bullets |
| Split (image ∥ text) | `Split1_lime`, `Split1_gradient`, `Split2_lime` | `:::columns` with an image column |
| Bullets (1–4 col) + framed | `title2`…, "Bullet points", "Frame Bullet points" | a `##` + bullet list (n columns) |
| Photo hero (L/R/full) | `title5`, `title6`, `title8`, `title9` | a `##` + one dominant image |
| Numbered process / steps | (01/02/03/04, arrow-flow) | an ordered list of short steps |
| Brand accents | `title_lime`, `title_gradient` | emphasis / callout slides |
| Closing | `Thank you 2` | last slide "Thank you" |
| Reference (NOT content) | logos, colours, icon grids | never targeted — skip |

Slide→layout mapping for all 64 (proof each example *is* a named layout):
`.private/jsk/` regeneration script in §9. The point: **the layout name is a
strong, designer-authored semantic label** — an LLM can match a slide's role to
it from the name alone, and a VLM can confirm from the rendered picture.

## 3. The engines — `best-engine-ai-helper`

### 3.1 Calling the models

`best-engine-ai-helper` (v1.0.0) gives both *which model* and *the transport*:

```python
import best_engine_ai_helper as beh                 # tag resolvers (used today)
from best_engine_ai_helper.llm import chat          # transport (text + vision)

# text: layout decision as strict JSON (structured output)
decision = chat(prompt, json_schema=LAYOUT_SCHEMA)          # -> dict

# vision: compare a rendered slide against the target layout picture
verdict  = chat(compare_prompt, images=[cand_png, target_png],
                json_schema=VERDICT_SCHEMA)                 # -> dict
```

`chat(prompt, *, system=None, images: list[bytes]|None=None,
json_schema: dict|None=None, model: str|None=None, temperature=0.2) -> str|dict`.
Images are **raw bytes**; when `images` is non-empty it auto-selects
`vision_model()`, else `text_model()`. With a `json_schema` it returns a parsed
`dict` (falls back to `str` on invalid JSON — parse defensively). Local-first
(Ollama), fails with `RuntimeError` if the daemon/model is absent.

### 3.2 Making it pick **non-generic** engines — the goals description

`best-engine`'s `parse_task(text)` maps free text onto benchmark axes
(`ocr` / `code` / `math` / `vision`, else `generalist`) and adds a VLM on any
vision keyword; `recommend()` then picks the highest-scoring **structured-output-
capable** model that fits memory *and* clears the throughput floor. So the lever
for "good non-generic engines" is a task description whose keywords land the LLM
on **generalist reasoning + JSON** and the VLM on the **vision/aesthetic** axis
(never OCR, never code/math). This is the description we feed it:

> Two coupled jobs for a tool that maps authored Markdown slides onto a
> professional designer's PowerPoint template. **(1) A text reasoning engine:**
> read each slide's Markdown content plus a catalog of the template's named
> layouts and decide which layout best fits — a semantic classification and
> instruction-following task returning a strict JSON decision (structured
> output), reasoning about each slide's role such as cover, section divider,
> big-number statistic, bold statement, one-to-four-column bullets, two-column
> split, photo hero, numbered process steps, and closing thank-you.
> **(2) A vision engine** for a visual quality-assessment loop: given a
> screenshot of the rendered candidate slide and the target designer layout
> picture, judge how well the visual layout, composition, hierarchy, colour and
> aesthetic match, returning the visual discrepancies as JSON — image,
> screenshot, diagram and chart aesthetic quality assessment for design, not
> fine-print reading.

Run `best-engine-ai-helper report --task "<the text above>"`. Validated on an
Apple M2 Max / 96 GB (budget 61 GB, 400 GB/s):

- **Matched keywords:** aesthetic, chart, diagram, image, photo, picture,
  quality assessment, screenshot, vision, visual → **LLM + VLM**, clean vision
  axis, no OCR/code/math misfire.
- **LLM (generalist):** `qwen3:14b` (score 78, ~25 tok/s) — an upgrade over the
  generic default `qwen3:8b` (74). Lighter alt `gemma3:12b`.
- **VLM (vision):** `gemma3:12b` auto-picked **because it honours Ollama
  structured JSON**; `qwen3-vl:14b/32b` score higher (83/87) but are *not*
  auto-chosen — qwen3-vl can't do Ollama structured output reliably.

**Design consequence.** The VLM compare step can go two ways:
1. **Strict-JSON verdict** → use `gemma3:12b` (structured-capable, auto-picked).
2. **Lenient verdict** (freeform "discrepancies", parsed with the tolerant
   `_parse_verdict` md2star already has) → unlocks the stronger
   `qwen3-vl:14b/32b`. Given the eyeball loop only needs `{matches, discrepancies}`
   and md2star already parses that defensively, **option 2 is attractive** and
   should be a benchmarked toggle.

Everything stays overridable via `BEST_LLM_TEXT` / `BEST_LLM_VISION` env vars
and the picker's persisted config — nothing hard-coded, per suite policy.

## 4. Architecture

Four stages. The design vocabulary is extracted from the template **once**; the
per-deck path selects, assembles, and verifies.

```
                    ┌──────────────────────── one-time per template ──────────┐
template.pptx  ──►  │ LAYOUT CATALOG BUILDER                                   │
                    │  • enumerate layouts (name + placeholder geometry)       │
                    │  • render each layout / example slide → thumbnail PNG    │
                    │  • (optional) VLM captions each thumbnail                │
                    │  → layouts.json  +  thumbs/<layout>.png                  │
                    └─────────────────────────────────────────────────────────┘
                                        │  (catalog)
 authored.md ─► segment into slides ─►  ▼
                    ┌──────────────────────── per deck ───────────────────────┐
 per md slide ──►   │ 1. LLM LAYOUT SELECT  (text engine, JSON)                │
                    │      in:  slide markdown + catalog (names+captions)      │
                    │      out: {layout_id, placeholder_map, confidence}       │
                    │ 2. ASSEMBLE the slide onto that layout (Seam C or D)     │
                    │ 3. RENDER slide → PNG  (LibreOffice → PDF → pdftoppm)    │
                    │ 4. RALPH EYEBALL LOOP  (vision engine)                   │
                    │      compare(candidate_png, target_thumb) → verdict      │
                    │      if !match and budget: revise placement/layout, goto 2│
                    │      else keep best; fall back to a safe layout          │
                    └─────────────────────────────────────────────────────────┘
```

### 4.1 Layout Catalog (the missing primitive)

There is no LibreOffice/PPTX surface in the sprezzature render toolchain today —
this is the new piece. For a template, emit `layouts.json`:

```json
{ "template": "Jellysmack…pptx", "slide_size_emu": [9144000, 5143500],
  "layouts": [
    { "id": "slideLayout17", "name": "title9", "master": 1,
      "placeholders": [ {"idx":0,"type":"title","emu":[..]},
                        {"idx":1,"type":"pic","emu":[..]} ],
      "thumb": "thumbs/title9.png",
      "caption": "photo-hero, large image right, title top-left" } ] }
```

Thumbnails are produced exactly like the eyeball loop will render candidates:
`soffice --headless --convert-to pdf` then `pdftoppm -png` per page (poppler is
already a declared dep). Placeholder geometry comes from the layout XML
(`<p:sp>`/`<p:ph type=.. idx=..>` + `<a:off>/<a:ext>`), read with `zipfile` +
`ElementTree` — the same tooling `postprocess.py` uses for docx.

### 4.2 LLM layout selection (per slide)

Feed the model the slide's Markdown plus the catalog as `{id, name, caption,
placeholder-kinds}` rows; force a JSON decision:

```
LAYOUT_SCHEMA = { "type":"object", "required":["layout_id","placement"],
  "properties": {
    "layout_id":  {"type":"string"},                     // must be a catalog id
    "placement":  {"type":"object"},                     // md block -> placeholder idx
    "confidence": {"type":"number"},
    "why":        {"type":"string"} } }
```

Prompt shape (mirrors md2star's existing terse, machine-parseable prompts):
*"Here is one slide of Markdown and a catalog of the template's layouts (id,
name, what each looks like). Choose the single layout whose design best carries
this slide's role, and map each content block to a placeholder. Reply as JSON."*
Optionally escalate ambiguous slides to the **VLM** with the top-k layout
thumbnails ("which of these pictures best fits this content?").

### 4.3 Assembly seam — C vs D

From the pipeline study, four seams exist (A pre-pandoc md shaping, B Lua,
C post-pandoc XML rewrite, D full python-pptx assembler):

- **Seam A/B can't reach the rich layouts** — pandoc only instantiates its ~7,
  and layout choice isn't Lua-controllable. Good for *steering* pandoc, not for
  a 22-layout template.
- **Seam C — post-pandoc `slideN.xml.rels` rewrite.** Keep pandoc for content,
  then rewrite each slide's layout relationship to the chosen `slideLayoutM` and
  reconcile placeholders. Reuses `postprocess.py`'s zipfile+ElementTree pattern.
  Cheapest path to *all* layouts; the hard part is placeholder reconciliation
  between pandoc's emitted shapes and the target layout's placeholders.
- **Seam D — python-pptx assembler.** Parse md → slide models → build the deck
  directly on the template's layouts with `python-pptx`. Maximum control
  (VLM-inspectable, exact placeholder mapping); cost is reimplementing the
  pandoc-derived polish (tables, math→OMML, citeproc, fragments) and a new dep.

**Recommendation:** prototype on **Seam D for a curated slice** (cover, section,
big-number, bullets, split, photo-hero, thank-you) — it makes the
layout↔placeholder mapping explicit and is the natural fit for the eyeball loop
(we control exactly what lands where). Keep pandoc (Seam A steering + current
path) as the fallback/back-compat route. Revisit Seam C if we want to inherit
pandoc's content fidelity across *arbitrary* layouts later. Mermaid/SVG images
are already rendered pre-pandoc, so that work survives either way.

### 4.4 Ralph Eyeball Loop for slides

The **Ralph Eyeball Loop** (Warith Harchaoui's method — canonical definition:
[EN](https://harchaoui.org/warith/sprezzature/ralph-eyeball-loop.html) ·
[FR](https://harchaoui.org/warith/sprezzature/fr/ralph-eyeball-loop.html)) is
the capstone quality gate. Its four steps map directly onto slides —
**Render** (deterministically, LibreOffice → `pdftoppm` PNG) → **Look** (is the
point the first thing the eye finds? overflow / low-contrast / awkward void /
too-small figure?) → **Critique/Fix** → **Edit the *spec*, never the picture**
(the picture is only ever the evidence; here the spec is `mapping.json`'s
per-slide `overrides`). Loop *until there is nothing left to catch, then ship*.
Two modes as the method prescribes: **agent** (the agent that built the deck does
the looking) and **model-assisted** (a small local VLM does it); a
colour-vision / grayscale accessibility pass folds in before review.

Two shapes are useful here. A **target-matching** variant (like
`md2star/reverse_diagrams.py`) compares against the chosen layout's thumbnail;
a **self-critique** variant judges the rendered slide against design principles
(what the shipped `.private/jsk/eyeball.py` PoC does). Reuse the generic
`_reconstruct` shape (render → judge → revise → budget/fallback); only the render
and prompts change:

- **Render** (`RenderFn("slide", src) -> png`): assemble the one slide → tiny
  pptx → `soffice --headless --convert-to pdf` → `pdftoppm -png -r 150 -f N -l N`.
- **Target** = the chosen layout's thumbnail (or the designer's nearest example
  slide) from the catalog. **Candidate** = the rendered slide. Order: target
  first, candidate second (md2star convention).
- **Compare prompt** (slide-flavoured `_COMPARE_FIGURE_PROMPT`):
  *"The FIRST image is the target slide layout. The SECOND is a candidate render.
  Do they place the same title, body, bullets and images in the same regions with
  the same emphasis, and is nothing overflowing or clipped? Reply JSON:
  `{"matches": true|false, "discrepancies": "…"}`."* Add slide-specific
  dimensions: **overflow past bounds, empty/overfull placeholders,
  title-vs-body hierarchy, image aspect/crop, text legible at projection size.**
- **Revise**: feed `discrepancies` back to the **text** engine to fix the
  *source* — the layout choice, placeholder assignment, and content placement
  (shorten overflowing text, move a block, pick a roomier layout). Never edit the
  PNG. Budget `max_iterations=3`; on no-improvement or unrenderable, keep the
  best and fall back to a safe generic layout (never lose the slide).
- **Two modes** like the rest of the suite: *agent* (Claude reads both PNGs) and
  *local* (`gemma3:12b` for strict JSON, or `qwen3-vl:*` lenient) via the same
  Ollama transport md2star already has.

## 5. Where it lands in md2star

- New module `md2star/pptx_layout.py` — catalog builder + LLM selector (schemas,
  prompts). Model tags via `beh.text_model()/vision_model()`; transport via
  `best_engine_ai_helper.llm.chat` (first use of the transport in md2star).
- New module `md2star/pptx_assemble.py` — Seam-D python-pptx assembler for the
  curated archetype slice (behind a flag; pandoc path stays default).
- Reuse `md2star/reverse_diagrams.py`'s `_reconstruct` / `_parse_verdict` /
  injectable `VlmFn`/`RenderFn` seams for the slide eyeball loop (extract the
  generic loop into a shared helper so both diagram and slide loops share it).
- New `RenderFn("slide")` via LibreOffice+poppler (both already used for PDF).
- CLI: `md2star pptx --template <designer.pptx> --smart-layout [--diagrams-style
  eyeball]`; graceful degradation to today's pandoc path when `[ai]`/Ollama/
  LibreOffice absent (same contract as `twin --diagrams`).
- Deps: `python-pptx` (new, gui/ai-adjacent extra), LibreOffice (already needed
  for PDF), poppler (already a dep). No new *core* dep if gated behind an extra.

## 6. Risks & open questions

- **Placeholder reconciliation** (Seam C) or **faithful assembly** (Seam D) is
  the real engineering; layout *selection* is the easy, high-value half.
- **Layout count vs latency:** 22–38 layouts × per-slide LLM call is fine; VLM
  eyeball loops are the cost — cap iterations, cache renders (content-address
  like the mermaid/svg caches).
- **VLM structured output:** gemma3 (JSON) vs qwen3-vl (stronger, lenient) —
  benchmark both on real slide comparisons before committing (§3.2).
- **Template variability:** every designer template names layouts differently
  ("title9", "Split1_lime"). The catalog's VLM captions make selection robust to
  arbitrary names — don't hard-code any template's vocabulary.
- **Reference slides** (colours/logos/icon grids) must be excluded from the
  content-targetable set — detect via "no editable text placeholder" + a VLM
  "is this a content layout or a brand-reference page?" pass at catalog time.
- **best-engine dep pin bug:** md2star pins `best-engine-ai-helper>=0.3.0,<1`,
  which *excludes* the installed 1.0.0. Bump to `>=1.0.0,<2` before shipping any
  code that imports `best_engine_ai_helper.llm`.

## 7. Phased PoC plan

1. **Catalog builder** — `layouts.json` + thumbnails for the Jellysmack template
   (LibreOffice render + XML placeholder read). Deliverable: a browsable catalog.
2. **LLM selector** — given a hand-written 6-slide md and the catalog, print the
   chosen `layout_id` + placement per slide (JSON). Eyeball the choices vs the
   contact sheet. No assembly yet.
3. **Seam-D assembler** — build those 6 slides onto the chosen layouts with
   python-pptx; render to PDF; look. This is the "does it actually produce a
   Jellysmack-looking deck?" milestone.
4. **Eyeball loop** — wire the target-matching loop (reuse `_reconstruct`);
   measure how often it fixes overflow/misplacement within 3 iterations.
5. **Bench VLM** — gemma3-JSON vs qwen3-vl-lenient on step-4 verdict quality.
6. Fold into `md2star pptx --smart-layout` behind an extra, with graceful
   degradation to the pandoc path.

## 8. Assets & 9. Reproduce {#assets}

- Template: `assets/templates/pptx/Jellysmack-Presentation-Template.pptx`
  (**git-ignored** by `*.pptx`; only `assets/template.pptx` is whitelisted — add
  a `!assets/templates/pptx/*.pptx` exception if we want it tracked, but a 63 MB
  branded binary probably shouldn't live in git).
- Contact sheet: `.private/jsk/jellysmack-contact-sheet.png` (git-ignored scratch).

Reproduce the investigation:

```bash
# anatomy
unzip -l assets/templates/pptx/Jellysmack-Presentation-Template.pptx | grep -c slides/slide
# render + contact sheet
soffice --headless --convert-to pdf --outdir /tmp/j assets/templates/pptx/Jellysmack-Presentation-Template.pptx
pdftoppm -png -r 46 /tmp/j/Jellysmack-Presentation-Template.pdf /tmp/j/s
magick montage /tmp/j/s-*.png -tile 8x8 -geometry 320x180+3+3 .private/jsk/jellysmack-contact-sheet.png
# non-generic engine recommendation (paste the §3.2 task text)
best-engine-ai-helper report --task "<goals description from §3.2>"
```
