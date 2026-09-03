# Changelog

All notable changes to **md2star** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.0] — 2026-09-03

### Added
- **Template-intelligent PPTX (`md2pptx --smart-layout --template <designer.pptx>`)**:
  maps each Markdown slide onto a real designer PowerPoint template's own
  named layouts instead of Pandoc's ~7 generic ones. Two new modules —
  `md2star/pptx_layout.py` (deterministic layout/placeholder catalog via
  `zipfile`+`ElementTree`, an LLM text pass that picks the best-fitting
  layout per slide, and a **VLM visual tie-break** that shows the vision
  model actual candidate-layout thumbnails alongside the slide's content and
  overrides the text pick on disagreement) and `md2star/pptx_assemble.py`
  (a Seam-D `python-pptx` assembler that instantiates the *chosen* layout per
  slide — not a fixed round-robin subset — sized from that layout's own
  placeholder geometry, plus a **target-matching Ralph Eyeball Loop**
  (`--eyeball-iterations N`) that compares a rendered candidate against the
  chosen layout's own catalog thumbnail and applies bounded fixes). Both
  stages route through `best_engine_ai_helper.llm.chat` via md2star's
  resolved brief → engine contract, exactly like the existing alt-text/
  diagram-reconstruction AI passes; `md2star/llm.brief.yaml` gained a fourth
  job description and `structured_output: true` so the resolved engine
  supports the strict-JSON layout decisions this pass needs. Opt-in
  (`pip install 'md2star[pptx]'` for `python-pptx`) and best-effort: without
  a resolvable LLM+VLM engine or `python-pptx`, `--smart-layout` raises a
  clear, actionable error rather than silently falling back — the ordinary
  Pandoc `md2pptx` path is unaffected either way.

## [3.1.3] — 2026-08-21

### Fixed
- **Lua filter**: the auto-dated subtitle's day/month name was never
  capitalized for Russian (or any other script whose day name starts with a
  multi-byte UTF-8 character). `string.sub`/`string.upper` from Lua's plain
  `string` library operate on raw bytes, so slicing "the first character"
  only ever grabbed the first byte of a 2-byte Cyrillic codepoint; upper-
  casing that lone byte is a silent no-op in the standard C locale, leaving
  the day name lowercase ("пятница" instead of "Пятница") while every Latin-
  script language ("Vendredi", "Freitag", …) capitalized correctly. Switched
  to `pandoc.text.sub`/`pandoc.text.upper` (Pandoc's UTF-8-codepoint-aware
  text module) so the capitalization step works for every supported
  language, not just ASCII ones. Covered by a new regression test in
  `tests/test_lua_filter.py`.

## [3.1.2] — 2026-08-17

### Fixed
- **API**: `/convert` and `/extract` leaked their per-request temp directory
  on every failure. Cleanup was registered via `background.add_task(...)`
  before the risky work, which looks right, but FastAPI silently drops
  tasks already added to the injected `BackgroundTasks` object when the
  endpoint raises rather than returns a `Response` (verified empirically).
  Both endpoints now clean up explicitly in their `except` blocks; the
  background task is only registered right before a successful return.

### Changed
- Removed punctuation-dash asides (em/en dashes used mid-sentence) from
  every module docstring and the handful of documentation files that had
  them, per the project's writing charter. One unglossed acronym (VLM) in
  `WHY_MD2STAR_OVER_PANDOC.md` spelled out on first use. Prose only, no
  behavior change.

## [3.1.1] — 2026-08-15

### Fixed
- **`md2star-x`'s console-script entry point** pointed at the bare
  `click_cli.cli` group instead of `click_cli.main()` — the latter exists
  specifically to be the console entry point (its own docstring says so,
  and tests exercise it), but the installed script never actually ran
  through it. Fixed the `pyproject.toml` wiring.

## [3.1.0] — 2026-08-07

### Changed
- **Standalone images are now centred on the page.** md2star already sizes each
  bare `![](…)` image to a contain-fit that never exceeds the page (aspect-ratio
  preserved: `{width=15cm}` for wide images, `{height=17cm}` for tall ones — see
  `preprocessing/images.image_size_attr`), but Pandoc left them left-aligned. A
  new `postprocess.center_standalone_images` pass adds `<w:jc w:val="center"/>`
  to every image-only paragraph that is **outside a table** (`hors tableau`), so
  an image sits centred at the largest size that still fits — in the DOCX and,
  via LibreOffice, in the PDF. Table-cell images are untouched. Covered by
  `tests/test_postprocess.py`.
- **AI passes migrated to the suite's brief → engine LLM contract.** The three
  opt-in AI features — the `--lint` Markdown syntax fixer, empty-alt-text
  drafting, and `--diagrams` diagram/figure reconstruction — no longer pick a
  model tag themselves. md2star now commits a `md2star/llm.brief.yaml`
  (hardware-independent description of what the passes need: local, text +
  vision, low latency, multilingual); on first use `best_engine_ai_helper.ensure`
  resolves it against the machine and writes a **gitignored**
  `md2star/llm.engine.yaml`, and every call goes through
  `best_engine_ai_helper.llm.chat(engine=…, kind="llm"|"vlm")`. There is no
  hard-coded model tag and no `MD2STAR_LINT_MODEL` / `MD2STAR_ALT_TEXT_MODEL`
  env override anymore — the model comes only from the resolved engine.
- **`best-engine-ai-helper` is now the LLM transport, not just a tag picker.**
  The transport owns the daemon/serving lifecycle, so md2star no longer runs
  `ollama serve` / `ollama pull` or probes `localhost:11434` itself. The
  best-effort "never load-bearing" guarantee is unchanged: any resolution or
  transport failure degrades to the untouched document / scraped PNG.

### Removed
- **The `md2star[ai]` extra and the direct `ollama` dependency.** They existed
  only for the optional typed Ollama client behind an in-tree urllib fallback;
  both the extra and the fallback are gone now that all LLM traffic routes
  through `best_engine_ai_helper.llm.chat`. Deleted
  `md2star/preprocessing/_ollama_client.py`, the Ollama lifecycle helpers in
  `lint.py` (`is_ollama_installed`, `_ping_ollama`, `_ensure_model_pulled`, …),
  the `DEFAULT_LINT_MODEL` / `DEFAULT_ALT_TEXT_MODEL` constants, and
  `requirements-ai.txt`.

## [3.0.0] — 2026-08-02

Major release: md2star moves onto the stable 2.x / 1.x AI Helpers foundation.
The conversion behaviour and public API are unchanged — the bump is major
because two core suite dependencies each crossed a major boundary at once.

### Changed
- **Adopts `os-helper>=2.0.0,<3`** (was `>=1.7.2,<2`) — the hardened suite
  foundation for logging, file management and smart (resumable / verified)
  downloads.
- **Adopts `best-engine-ai-helper>=1.0.0,<2`** (was `>=0.3.0,<1`). The old `<1`
  cap silently locked md2star out of best-engine's first stable release, pinning
  it to the 0.x model-picker; the alt-text (`vision_model()`) and lint
  (`text_model()`) resolvers md2star relies on are unchanged in 1.x.
- **CI lint no longer floats its ruff version.** The `ruff` job installed
  `--upgrade ruff` (unpinned), which let a new ruff change gate behaviour by
  surprise; it now pins `ruff==0.15.21` like the rest of the suite. The unit
  `pytest` matrix drops to a single Python (the 3-OS integration, coverage and
  OCR round-trip jobs still cover breadth; the full local sweep runs before
  push).

### Added
- `tests/test_readme_install_pin.py` guards against a stale `git+…@vX` self-pin
  ever appearing in any Markdown file (the install docs stay `pip install
  md2star`).

## [2.14.0] — 2026-08-02

### Changed
- **GUI typography aligned to the house "three-Roboto" rule.** The full editor
  (`md2star gui`) now ships exactly three self-hosted variable web fonts, all
  from the Roboto super-family, so the whole surface reads as one typographic
  system:
  - **Roboto** (sans) replaces Montserrat for UI chrome and body text.
  - **Roboto Serif** (serif) stays for long-form prose / the rendered preview.
  - **Roboto Mono** (mono) replaces the OS system-mono stack in the CodeMirror
    editor pane, `<kbd>` and `<code>` (with the OS stack kept only as a
    first-paint fallback).
  All three are vendored under `md2star/data/gui/vendor/fonts/` straight from the
  `sprezzature-ui` skill (single variable woff2 each, SIL OFL 1.1, no CDN);
  `scripts/vendor_gui.sh` now refreshes them from that one source instead of
  copying Montserrat + fetching Roboto Serif from Google Fonts. The
  sprezzature-colors palette and the class-based dark mode were already in place
  and are unchanged; verified in a headless-Chrome render (light mode coherent,
  all three faces loading). No behavioural change and no new dependency — a
  vendor-tree swap only.

### Added
- **Twin diagram reconstruction now covers *free figures*, not just node-and-edge
  diagrams — via an editable SVG that joins the same Ralph Eyeball Loop.** The
  `--diagrams` pass (`md2star twin --diagrams`, GUI **Mermaid** toggle, API
  `diagrams=true`) gains a second reconstructable kind:
  - The classifier is now three-way — **DIAGRAM** (→ Mermaid, unchanged),
    **FIGURE** (a chart / plot / logo / icon / line drawing → **SVG**), and
    **PHOTO** (kept as a scraped PNG). A figure is re-authored as a
    self-contained `<svg>` written **alongside** the scraped raster
    (`assets/<name>.svg`) and linked as the primary asset, with the PNG kept as a
    commented fallback — the same "verified, not trusted, never lose the ground
    truth" contract the Mermaid path uses.
  - **Same target-matching eyeball loop, generalised**: `reconstruct_mermaid` and
    the new `reconstruct_svg` are thin wrappers over one shared render → compare →
    revise loop. SVG candidates are rasterised for comparison by a detected
    rasteriser — `cairosvg` if importable, else `rsvg-convert` / `inkscape` /
    ImageMagick (`magick` / `convert`) — and the render is content-addressed and
    cached like the Mermaid render. No rasteriser present → the figure degrades to
    the scraped PNG, exactly like a missing `mmdc`.
  - `RECONSTRUCTABLE_KINDS` is now `{"mermaid", "svg"}`. No new **required**
    runtime dependency: the SVG rasteriser is any tool already on the host, and
    `cairosvg` is used only if present. New offline tests in
    `tests/test_reverse_twin.py` (injected fakes — no rasteriser needed) cover the
    SVG parse, the SVG eyeball loop, and the FIGURE → SVG / fallback handler
    routing.

## [2.12.0] — 2026-08-02

### Added
- **The Markdown *twin* reaches the GUI and the API — feature parity with the
  CLI `md2star twin`.** The reverse path that recovers an *editable* document
  (prose + GFM tables + scraped images, optionally re-authored Mermaid diagrams)
  is no longer CLI-only:
  - **Full GUI (`md2star gui`).** The editor's **Import** control gains two
    toggles — **Twin** (keep scraped images) and **Mermaid** (re-author
    node-and-edge figures via the local VLM; implies Twin). Twin mode writes
    `<stem>.md` **plus an `assets/` folder into the open folder root** (so the
    recovered image links resolve on re-render) and refreshes the sidebar; the
    `.md` name is sanitised and de-duplicated so an import never clobbers an
    existing file. Twin mode requires an open folder (assets need a home) and
    returns a clear 409 otherwise; plain **Import** stays a zero-side-effect
    text load that needs no folder. `POST /extract` now reads `X-Md2star-Twin` /
    `X-Md2star-Diagrams` / `X-Md2star-Name` headers.
  - **API (`md2star-api`).** `POST /extract` gains `twin` / `diagrams` form
    fields (`diagrams` implies `twin`). Text-only mode still returns
    `{filename, markdown}` JSON; twin mode returns a **zip of `<stem>.md` +
    `assets/`** (`application/zip`) so the recovered twin travels as one
    self-contained, re-renderable unit.
  - **Graceful degradation preserved**: no `[ai]` stack / Ollama / `mmdc` → the
    Mermaid pass degrades to plain scraped PNGs; no `[ocr]` engine → the same
    501/503 install hint as before. No new runtime dependencies (the zip uses
    stdlib `zipfile`).
  - Docs: `TRIGGERS.md`, the agent skill (`skills/md2star/SKILL.md` +
    `references/triggers.md`) now advertise the reverse/twin direction and drop
    the stale "md2star does not extract documents" SKIP. Covered offline by new
    cases in `tests/test_api.py` and `tests/test_gui_reverse_lint.py` (injected
    fakes — no Kreuzberg needed).

## [2.11.0] — 2026-08-01

### Added
- **Markdown *twin* — the reverse path, upgraded from "recover the text" to
  "recover an editable document".** A new `md2star twin <file>` command (also
  `md2star-x twin`) reads **any PDF, or anything LibreOffice can convert to
  one**, back into a `<stem>.md` **plus an `assets/` folder**:
  - **Tables** come back as GFM pipe tables and **every embedded raster is
    scraped** out to `assets/` and re-linked, so the Markdown is a first-class
    source you can edit and re-render through the forward path.
  - **`--diagrams`** (opt-in, `[ai]`) classifies each scraped raster with the
    local vision model and **re-authors node-and-edge figures as Mermaid** via a
    **target-matching Ralph Eyeball Loop**: render the candidate with the same
    vendored `mmdc` the forward path uses, compare it against the scraped
    original with the VLM, feed the discrepancies back to the text model, and
    iterate until it matches (budget-capped). Photos and figures that aren't
    graph-expressible keep their scraped PNG; a reconstructed diagram keeps the
    PNG as a commented fallback, so the ground truth is never lost.
  - **Input normalization**: non-native formats (`.odt`, `.rtf`, `.doc`,
    `.xlsx`, `.html`, `.epub`, …) are routed through headless LibreOffice to PDF
    first, so everything funnels into the same Kreuzberg + OCR pipeline.
  - **Graceful degradation** throughout: no `[ocr]` engine → clear install hint;
    no AI stack / Ollama / `mmdc` → every image degrades to the plain scraped
    PNG (exactly the deterministic result). Model choice is delegated to
    `best-engine-ai-helper`; nothing is hard-coded.
  - New modules `md2star/reverse.py` (`to_markdown_twin`, `extract_twin`),
    `md2star/reverse_diagrams.py` (classifier + eyeball loop, injectable seams),
    and `md2star/twin_cli.py`. Covered by `tests/test_reverse_twin.py` (offline:
    the eyeball loop and handlers run against injected fakes; a live extraction
    test skips cleanly without the `[ocr]` engine).

## [2.10.0] — 2026-07-31

### Added
- **Reverse conversion — DOCX / PPTX / PDF → Markdown.** A new
  `md2star.reverse` module reads a finished document back into an editable
  Markdown source, powered by [Kreuzberg](https://github.com/Goldziher/kreuzberg)
  (OCR included, so scanned PDFs work). It is an opt-in extra —
  `pip install 'md2star[ocr]'` — and every surface degrades gracefully with a
  clear install hint when it is absent.
  - **Full GUI (`md2star gui`)** gains an **Import** button: pick a
    `.docx` / `.pptx` / `.pdf` and its Markdown loads straight into the editor
    (`POST /extract`).
  - **API (`md2star-api`)** gains **`POST /extract`** (upload a document → JSON
    `{filename, markdown}`); `GET /doctor` now reports `reverse_available`.
- **Full GUI: AI Lint button.** Runs the same syntax-only LLM repair pass as the
  CLI `--lint` (`POST /lint`, backed by `lint_with_llm`) over the editor buffer
  and applies the fix in place. Repairs only — never rewrites prose — and is a
  safe no-op when Ollama or the model is unavailable.

## [2.9.0] — 2026-07-31

### Changed
- **Model choice is delegated to the suite's model picker,
  `best-engine-ai-helper`.** The lint (text) pass now reads
  `best_engine_ai_helper.text_model()` and the alt-text (vision) pass reads
  `best_engine_ai_helper.vision_model()`, instead of hard-coding a tag or
  routing through `os_helper.llm_model()`. Those resolvers return the model
  selected for the current machine by `best-engine-ai-helper pull`, or a safe
  multimodal default (`qwen3-vl:8b`) when detection has never run — cheaply and
  deterministically, without probing hardware at conversion time. Explicit
  `MD2STAR_LINT_MODEL` / `MD2STAR_ALT_TEXT_MODEL` overrides still win.
- **Dependencies.** Added `best-engine-ai-helper>=0.3.0` (light: click / psutil
  / pyyaml / requests). Relaxed the `os-helper` floor back to `>=1.7.2` — its
  `llm_model()` is no longer used now that model choice lives in
  `best-engine-ai-helper`.
- **Landscape docs regenerated** from the CSV source of truth (star table,
  positioning map, commentary) and the French `LISEZMOI.md` / `PAYSAGE.md`
  reworded for a more idiomatic, natural tone.

### Fixed
- **MCP surface pinned below the breaking `mcp` 2.0.0.** `fastapi-mcp` 0.4.0
  declares only `mcp>=1.12` with no upper bound, so a fresh install pulled the
  new `mcp` 2.0.0 whose low-level `Server.__init__` signature change broke
  `fastapi-mcp` at import (`Server.__init__() takes 2 positional arguments but
  3 were given`). The `mcp` and `dev` extras now cap `mcp<2`.

## [2.8.0] — 2026-07-20

### Added
- **Minimal browser bench on the FastAPI surface (`GET /gui`).** `md2star-api`
  now serves a self-contained, build-step-free HTML page (`md2star/gui.py`):
  drop a `.md`, pick a target format, download the rendered document. It adds
  zero server logic — it POSTs to the same `/convert` endpoint the CLI and MCP
  surfaces use — and aligns md2star with the AI Helpers house standard where
  every package's API serves a minimal `/gui` (mirrors `audio_helper.gui`).
  `GET /` now redirects to `/gui`. This is the lightweight sibling of the full
  `md2star gui` Overleaf-style editor (`md2star/gui_server.py`), which is
  unchanged and remains the primary human surface. Covered by
  `tests/test_api.py` (`/gui` serves HTML, `/` redirects).
- **Repo-root `TRIGGERS.md`.** A user-facing, exhaustive catalogue of the
  phrasings, commands, and file situations that should invoke md2star — the
  house-standard companion to the skill's machine-checked
  `skills/md2star/references/triggers.md`. Referenced from README + LISEZMOI.
- **Local-first badge + "The Promise" / "La promesse" section** in README and
  LISEZMOI, standardised across the suite. Phrased truthfully: the document
  *content* stays local; the two optional network conveniences (the one-time
  default-template fetch, opt-in `--allow-remote-images`) are called out with
  their opt-outs.

### Changed
- **Alt-text drafting is now language-aware and context-aware** (aligned with the
  suite's `front-vision` skill). The `--lint` empty-alt pass writes the alt text
  in the **document's own language** — auto-detected from the surrounding prose,
  any language, not a hardcoded EN/FR toggle (French doc → French alt text) — and
  feeds each image's **surrounding text** (nearest heading + nearby prose) to the
  model so it describes what the image *means* in place. The default vision model
  changed from the shared text-lint tag to **`gemma3:4b`** (the suite's
  authorized multimodal model): the previous macOS default `gemma4:e2b-mlx` is a
  text-only MLX build that could not see images, so it produced empty/garbage
  captions. The per-image cache key now folds language + context so a re-run in a
  different language re-drafts. `MD2STAR_ALT_TEXT_MODEL` still overrides. The pass
  stays seamless (drafts embed directly, nothing to approve) but is no longer
  silent: a neutral one-glance summary of every image → its drafted alt text is
  logged at INFO (`--quiet` hides it).
- **Adopted `os_helper` (md2star's sibling in the same suite) across the package.**
  Added `os-helper>=1.6,<2` as a core dependency and routed the hand-rolled
  primitives through it: cache-key hashing (`osh.hash_string` in `images.py` /
  `mermaid.py`), OS detection (`osh.macos()/linux()/windows()` in `cache.py`,
  `lint.py`, `gui_server.py`), directory creation (`osh.make_directory`), temp
  folders (`osh.temporary_folder`), and the default-template download
  (`osh.download_file`). The standalone `minimal-gui` server logs through
  `osh.init_logging` / `osh.info` / `osh.warning` (incl. its LAN-bind banner).
- **The CLI's logging surface is now backed by `os_helper` too.** Rather than
  keep a bespoke live-stderr handler in md2star, the capability was contributed
  upstream: `os_helper` 1.6.0 gained named-logger + `live_stream` support (a
  handler that re-resolves `sys.stderr` on each emit, idempotent, `propagate=True`).
  `md2star.logging.configure()` now delegates to `osh.init_logging(name="md2star",
  live_stream=True, …)`, so `--verbose`/`--quiet`, the bare-message format, and
  pytest's `capsys`/`caplog` capture all work as before — with one less
  hand-rolled handler to maintain.
- **Completed the `os_helper` adoption by upstreaming the missing primitives**
  (os-helper 1.7.0) rather than leaving md2star exceptions: `download_file` now
  returns `{path, content_type, bytes}` and takes `check_url=False` (so the remote
  **image** path picks its extension from the MIME type without a HEAD precheck
  some CDNs reject); new `make_temporary_directory` (mkdtemp with caller-owned
  cleanup) backs the **API** request tempdir and the **GUI** session dir;
  `temporary_filename` gained a `directory=` arg, backing the CLI's
  preprocessed-Markdown temp file (kept beside the input so relative images
  resolve); and `alt_text`'s content hash now uses `osh.file_exists` +
  `osh.hashfile`. Dep floor bumped to `os-helper>=1.7`.

### Fixed
- **`minimal-gui/server.py` invoked a non-existent `md2star convert` CLI.** It now
  calls the real `md2star <fmt> <input> -o <output>` interface (the old call
  always failed and silently fell back to the PATH binary). Added the loud
  LAN-bind warning banner it was missing, mirroring `md2star gui`.
- **Comment density on `gui_server.py` (18.6% → 25.2%) and `click_cli.py`
  (24.5% → 28.6%)** raised to the 25% target with substantive handler/option
  documentation (both were already above the 15% CI floor).

### Added
- **click CLI front-end (`md2star-x`).** A modern click-based command surface
  (`md2star-x docx|pptx|pdf|gui|doctor`) over the exact same conversion pipeline
  as the argparse wrappers — a thin adapter delegating to `md2star.cli._convert`,
  so the two front-ends can never drift. `click>=8,<9` joins the core deps.
- **Agent skill packaging (`skills/md2star/`).** md2star now ships as a Claude
  Skill *and* OpenCode skill: `SKILL.md` with a trigger-rich description + SKIP
  clause, and `references/{cli-reference,surfaces,triggers}.md`.
  `scripts/check_triggers.py` enforces exhaustive trigger coverage (run in CI via
  `tests/test_skill.py`).
- **`scripts/brew.sh`** — idempotent macOS Homebrew bootstrap (pandoc + pipx +
  md2star, with `--with-pdf/--with-mermaid/--with-ai/--all`); added to CI
  shellcheck.
- **AI-eval layer (`tests/test_ai_eval.py`, marker `ai_eval`).** Quality eval of
  the opt-in `--lint`/alt-text passes against a real local Ollama daemon; skips
  cleanly in CI where no daemon is present.

### Changed
- **Renamed the standalone preview server `overleaf/` → `minimal-gui/`** (the old
  name borrowed a trademark and duplicated the `md2star gui` concept). No code
  referenced the path, so nothing breaks; it is now the documented "minimal GUI"
  surface. Added `md2star/gui_server.py`'s missing author header.

## [2.7.0] — 2026-07-19

### Added
- **`md2star[ai]` extra — the official `ollama` Python client for the AI passes.**
  The opt-in `--lint` syntax fixer and empty-alt-text drafter can now talk to the
  local Ollama daemon through the ergonomic, typed `ollama` client instead of a
  hand-rolled `urllib.request` POST. Install with `pip install 'md2star[ai]'`
  (or `pipx inject md2star ollama`). The extra is purely a transport upgrade:
  behaviour is identical to v2.0, and **without** it the passes keep working via
  the zero-dependency urllib fallback. System Ollama (the daemon + `ollama pull`)
  is still required at runtime either way. New
  `md2star/preprocessing/_ollama_client.py` wrapper + `tests/test_ollama_client.py`
  (both transports and both response shapes covered against an injected fake, so
  the suite stays offline).
- **`md2star[gui]` install command.** `pip install 'md2star[gui]'` is now a
  valid, self-documenting way to install for the local GUI. The GUI remains
  bundled in the single core wheel (its frontend is fully vendored, zero extra
  Python deps), so this extra resolves to the identical wheel as plain
  `md2star` — a UX/marker alias, not a separate download. (A separate
  `md2star-gui` distribution was considered and deliberately not pursued, to
  avoid maintaining two coupled PyPI packages.)

## [2.6.0] — 2026-07-18

### Added
- **The local GUI is back — `md2star gui`.** The Overleaf-style Markdown → PDF
  editor returns, this time bundled in the core package (no separate extra to
  install). Launch it with `md2star gui`; it serves a localhost-only editor with
  live PDF preview (PDF.js), a folder browser confined to one chosen root, an
  in-session reference-template upload, and server-side draft auto-save. The
  whole frontend (PDF.js, CodeMirror, Tailwind, Montserrat + Roboto Serif) is
  vendored under `md2star/data/gui/`, so the GUI runs fully offline and adds
  **zero** extra Python dependencies — it is pure stdlib `http.server` fronting
  the same `_convert` code path as the CLI. Path-confinement of the `/fs/*`
  endpoints is covered by `tests/test_gui_security.py`.
- **`requirements.txt` (CLI) and `requirements-gui.txt` (GUI)** for users who
  prefer `pip install -r …` over the packaging extras. The GUI file inherits the
  CLI one (the GUI adds no pip deps).

### Changed
- **Version is now single-sourced** from `md2star/__init__.py` via hatchling's
  version hook (`[tool.hatch.version]`). Previously the version lived in both
  `pyproject.toml` and `__init__.py`; they drifted at v2.5.1/v2.5.2 (the package
  reported `2.5.0` while the wheel was `2.5.2`). One edit point now, no drift.

### Fixed
- **Clean Ctrl-C.** Interrupting a conversion (Pandoc / Mermaid / LibreOffice)
  now prints `md2star: interrupted.` and exits `130` (shell 128 + SIGINT) instead
  of dumping a `KeyboardInterrupt` traceback.

## [2.5.2] — 2026-07-18

### Tests
- **OCR round-trip identity now covers footnotes.** Extended the normal form `N`
  in `tests/test_roundtrip_ocr.py` to fold Markdown footnotes — both numeric
  (`[^1]`) and named (`[^aa]`) labels — so `g(f(x)) = x` holds for documents with
  footnotes: the definition texts are recovered (appended in reference order), and
  the rendered superscript markers / running numbers (which a PDF assigns and a
  label never survives) are normalized out on both sides. Added
  `test_identity_with_numeric_footnotes` and `test_identity_with_named_footnotes`.

### CI
- The `ocr-roundtrip` job's guard is now count-agnostic (`set -o pipefail` +
  skip-detection) instead of hard-coding the passing-test count, so adding round-trip
  cases no longer requires editing the workflow.

## [2.5.1] — 2026-07-18

### Tests
- **OCR round-trip identity `g(f(x)) = x`.** Rewrote `tests/test_roundtrip_ocr.py`
  to prove, by exact whole-document string equality under an explicit normal form
  `N`, that the `md → docx → pdf` render (`f`) followed by kreuzberg PDF text
  extraction (`g`) is the identity on Markdown — for paragraphs of any length
  (wrapping is reflowed) and bullet lists, across multiple pages (page-number
  footers and the injected date subtitle are normalized out). The provable limits
  (inline emphasis, heading *levels*, tables — a PDF has no such markup layer) are
  stated precisely in the module docstring. Replaces the earlier, weaker
  "content-survival" framing; `f`, `g`, and `N` are now defined explicitly.

### CI
- New **`ocr-roundtrip`** job installs pandoc + LibreOffice + kreuzberg and
  *actually runs* the identity test (and fails if it silently skips), so the
  round-trip is verified on every push rather than only locally. Wired into the
  release gate.

### Documentation
- `requirements-dev.txt` now lists the OCR test dependencies (`kreuzberg`, `pypdf`)
  explicitly, with per-OS LibreOffice install hints. Corrected a stale note in
  `tests/test_roundtrip.py` that claimed the OCR direction was validated
  out-of-tree — it is now validated in-tree.

## [2.5.0] — 2026-07-16

### Changed
- **Remote reference template is now the default.** When no local
  `template.{docx,pptx}` (nor the legacy `.pandoc-reference.{docx,pptx}`,
  nor an XDG-cached copy) is found, md2star now fetches
  `https://deraison.ai/template.{docx,pptx}` **by default** and caches it
  under XDG — previously this required the opt-in `--allow-remote-templates`
  flag. This applies everywhere the converter runs: the `md2docx` / `md2pptx`
  / `md2pdf` CLIs, the HTTP API, and the MCP server (all route through
  `_convert`). A failed download (no network, 404, timeout) falls back to the
  bundled template, so a conversion never breaks because deraison.ai is
  unreachable.

### Added
- **`--no-remote-templates`** — opt OUT of the default deraison.ai fetch and
  use the bundled template instead. The hard `--offline` switch also skips it
  (and forbids every other network touch).

### Deprecated
- **`--allow-remote-templates`** is now a silent no-op (accepted so existing
  scripts/CI don't error). Remote templates being the default, it has nothing
  left to enable.

## [2.4.2] — 2026-07-15

### Added
- **Footnotes cookbook entry.** Markdown footnotes (`[^label]` and inline
  `^[…]`) already pass straight through to native Word footnotes via Pandoc's
  `footnotes` extension — no special preprocessing. Documented it end to end:
  `EXAMPLES.md` §10 plus a rendered example source
  `tests/examples/footnotes_document.md` (compiled by `tests/examples/run.sh`).
- **OCR round-trip test** (`tests/test_roundtrip_ocr.py`). Proves the long arm
  of idempotence — `md → docx → pdf → text` — by rendering through the real
  `md2pdf` path (headless LibreOffice) and reading the PDF back with
  `kreuzberg`. Asserts content survival (headings, list items, paragraph
  nouns), not byte-level equality. Marked `slow`; skips cleanly when
  LibreOffice/kreuzberg are absent. `kreuzberg` added to the `[dev]` extra —
  **test-only, never imported by the runtime.**
- **`requirements.txt` / `requirements-dev.txt`.** Thin, comment-rich pip entry
  points that install `-e .` and `-e .[dev]` respectively; `pyproject.toml`
  stays the single source of truth (no duplicated dep lists to drift).
- **Registered `slow` pytest marker** in `pyproject.toml` — run the fast subset
  with `pytest -m "not slow"`.

### Maintenance
- **Docstring pass (coding-standard rules 0/1).** Added NumPy-style docstrings
  to the 32 remaining undocumented functions — all private/nested/dunder
  (`doctor`, `tables`, `images`, `alt_text`, `math`, `cli`, `errors`,
  `logging`). Source docstring coverage is now 100%, public *and* private.
- **Comment-density pass (rule 4).** Raised the two below-target files —
  `doctor.py` (16.3 % → 29.3 %) and `preprocessing/pipeline.py`
  (18.8 % → 31.4 %) — with load-bearing *why* comments. Package-wide 29.2 %.
- **Test-suite rationalization (rule 13).** Folded `test_preprocessing.py`'s
  value-varying micro-tests into `@pytest.mark.parametrize` functions
  (86 → 60 functions) with **zero** cases dropped and coverage unchanged
  (79 %). Fewer, stronger tests; same protection.
- **Documentation refresh.** Synced README + LISEZMOI (footnotes, requirements,
  competitive-comparison link), de-staled ROADMAP (three shipped P1 items moved
  to a "P1 — shipped" section) and LANDSCAPE (GUI reframed as the `[gui]` extra;
  version references realigned), linked the previously-orphaned `LANDSCAPE.md`
  from README/LISEZMOI, and clarified CONTRIBUTING (rule-0 wording, `make dev`
  / `requirements-dev.txt`, fast-subset command). No behaviour change.

## [2.4.1] — 2026-07-13

### Maintenance
- **Comment-density pass (coding-standard rule 4).** Added *why* comments
  across the previously under-documented modules (`doctor`, `images`,
  `lint`, `alt_text`, `mermaid`, `api`, `errors`, `language`, `cache`);
  every non-glue source file is now above the 15 % floor (package-wide
  13.5 % → 23.4 %). No behaviour change.
- **New `scripts/audit_comments.py`** — a stdlib comment-density auditor
  (docstring-aware, unlike `cloc`) with a CI gate job that fails when any
  non-glue file drops below the floor. Covered by `tests/test_audit_comments.py`.

## [2.4.0] — 2026-07-13

### Added
- **Central logging surface** (`md2star/logging.py`) with `configure()` +
  `get_logger()`. All 31 stderr *diagnostics* (deprecation notices, download
  / render / lint fallbacks, LibreOffice failures) now go through a single
  `"md2star"` logger instead of scattered `print(..., file=sys.stderr)`
  calls. Program *output* (`Wrote: …`, `doctor --json`, `templates list`)
  stays on stdout, so piping is unaffected.
- **`--verbose` / `--quiet`** flags on `md2docx` / `md2pptx` / `md2pdf`
  (and the `md2star` subcommands). `--verbose` shows debug-level detail,
  `--quiet` limits stderr to errors. The default is unchanged: every
  message that used to print still prints.

## [2.3.0] — 2026-07-12

### Added
- **FastAPI HTTP surface** (`md2star.api`, `[api]` extra) — the converter as
  HTTP endpoints: `GET /health`, `GET /doctor` (the same environment diagnostic
  as `md2star doctor --json` — which tools are present, per-format feature
  status), and `POST /convert` (upload a `.md`, pick `docx`/`pptx`/`pdf`, stream
  back the compiled document; optional `author`/`lang`/`date` metadata). Missing
  system tools surface as `503`, invalid input as `400`. Run it with `md2star-api`
  or `uvicorn md2star.api:app`.
- **MCP surface** (`md2star.mcp`, `[mcp]` extra) — exposes the FastAPI app as MCP
  tools via `fastapi-mcp`, so an MCP client (Claude Desktop, agents, IDEs) can
  call `doctor` / `convert` as first-class tools. Run it with `md2star-mcp` or
  `python -m md2star.mcp`.
- Smoke + round-trip tests for both surfaces (`tests/test_api.py`,
  `tests/test_mcp.py`); the `/convert` round-trip renders a real DOCX when Pandoc
  is present. CI installs the `api`/`mcp` deps via `[dev]` so they run on every
  push. The `api.py`/`mcp.py` modules are excluded from the coverage gate (their
  happy path needs a running server + Pandoc), mirroring `__main__.py`.

## [2.2.0] — 2026-07-05

### Added
- **Round-trip fidelity guarantee, enforced in CI.** md2star's DOCX
  output is a faithful, reversible rendering of the source Markdown:
  headings, `**bold**` / `*italic*` / `` `code` `` emphasis, pipe
  tables, and lists all survive `md → docx → md`, and the pipeline is
  a fixed point (`g(g(x)) == g(x)`) so repeated conversions converge
  instead of drifting. New `tests/test_roundtrip.py` proves it by
  converting a fixture to DOCX, reading it back with Pandoc's native
  DOCX reader (no new dependency), and asserting both content survival
  and idempotence. The same property was validated out-of-tree against
  the [kreuzberg](https://github.com/Goldziher/kreuzberg) extractor,
  which also covers the `pdf → md` OCR direction (100 % word recall
  from DOCX, 94–99 % from the LibreOffice-rendered PDF). Documented in
  README / LISEZMOI under "Round-trip fidelity".

### Fixed
- **PPTX slide isolation is now idempotent.** The isolation pass
  inserts a blank `##` slide separator before a table/image that
  follows other content, but it recognized a heading only via
  `startswith("## ")` — with a trailing space the *empty* separator it
  emits does not have. Re-converting an already-isolated document
  therefore stacked a fresh `##` in front of every table on each run,
  breaking the round-trip fixed point. The walker now also matches the
  bare `#` / `##` forms, so `preprocess_markdown` is stable under
  repetition. Regression guard in
  `tests/test_preprocessing.py::TestPptxSlideIsolation::test_isolation_is_idempotent`.

## [2.1.0] — 2026-06-29

This release ships the quick-win + medium-lift batch from
`.private/ASSESSMENT.md`. No breaking changes; everything additive
or internal.

### Added
- **`md2star templates {list,path}` subcommand.** Reports the
  resolution order md2star would use for `template.docx` /
  `template.pptx` and prints the absolute path of the winner. Short-
  circuits the "why isn't my branding applied?" debug loop. Mirrors
  the priority documented in
  `cli._resolve_reference_doc` (per-project → legacy → cached →
  bundled). Test coverage in `tests/test_templates.py` (9 cases).
- **Typed exceptions wired into the CLI top level.** `md2docx` /
  `md2pptx` / `md2pdf` now catch `md2star.errors.Md2starError`
  subclasses and render a friendly two-block message
  (`md2star: <headline>` + indented `<hint>`) instead of a Python
  traceback. Three failure modes converted so far:
  `pandoc not found` → `MissingDependencyError` (exit 127);
  `LibreOffice not found` → `MissingDependencyError` (exit 127);
  `input file not found` → `InvalidInputError` (exit 2).
  Test coverage in `tests/test_cli_errors.py` (7 cases).
- **`python -m md2star`** as an alternative to the `md2star`
  console script via a new `md2star/__main__.py` shim. Standard
  Python convention.
- **CI: wheel-install smoke job.** After the existing `build` job,
  CI downloads the artifact, installs it into a fresh venv, and
  exercises every console-script entry point + `python -m md2star`
  + `doctor --json` shape. Catches `[project.scripts]` typos and
  missing package-data regressions before they ship to PyPI.
- **CI: `pip-audit` job.** Runs `pip-audit --strict` against the
  installed runtime + dev deps. Surfaces CVEs in `langdetect` /
  `Pillow` automatically; fails the gate so we notice promptly.
- **CI: coverage gate.** `pytest --cov` with a 70 % threshold
  configured in `pyproject.toml`. Current coverage: 78 %.

### Changed
- **CONTRIBUTING.md** gains a "Rebuilding the bundled templates"
  section documenting the
  `pandoc --print-default-data-file reference.{docx,pptx}` →
  brand → commit workflow so future maintainers don't have to
  reverse-engineer it.
- **`Makefile`** `publish` / `publish-testpypi` targets now prefer
  `.secrets/.pypirc` (the canonical twine config) when present and
  fall back to `.secrets/pypi.env`. Either path bootstrapped from
  the committed `.example` templates.
- **`README.md` + `LISEZMOI.md`** carry the live PyPI version badge
  alongside the existing CI / Python / license / status badges.
- **`docs/audit.md` + `ROADMAP.md`** drop residual references to
  private files so every pointer in the public docs resolves on a
  fresh clone.

### Fixed
- Stale "complex tables in PDF" caveat in the README's "Beta"
  paragraph — the v2.0.0 template rebuild resolved that bug at the
  source; the paragraph now points at the v2.0.0 fix.

## [2.0.1] — 2026-06-29

### Fixed
- **Logo broken on the PyPI project page.** The 2.0.0 README
  referenced the project logo with a relative path
  (`![logo](assets/logo.png)`) — fine on GitHub, but PyPI does not
  resolve relative URLs against the repo, so the image rendered as
  a broken icon. Switched to the absolute
  `raw.githubusercontent.com` URL so the same Markdown renders
  correctly on both PyPI and GitHub. Pure docs / metadata fix; no
  code change.

## [2.0.0] — 2026-06-29

This is the PyPI debut. Two breaking changes drive the major bump.

### Breaking
- **Licence is now BSD 3-Clause** (was The Unlicense / public domain).
  Aligned with scikit-learn and the broader scientific-Python
  conventions. Downstream redistributors must now ship the copyright
  notice + disclaimer alongside the binary. The change is permissive
  → permissive, so existing usage is unaffected; only redistribution
  obligations change.
- **GUI removed.** The Overleaf-style local web editor (`md2star gui`),
  the `md2star html` subcommand, and the ~3 MB vendored frontend tree
  (Tailwind, CodeMirror, PDF.js, Roboto Serif) have been removed for
  the PyPI debut so the wheel stays under 250 KB. The GUI lives in
  git history and is slated to return as an opt-in extra:
  `pipx install 'md2star[gui]'` in v2.1.

### Added
- **PyPI distribution.** Install with `pipx install md2star` — no
  clone required for end users. `make install` from a clone still
  works for the development path.
- **Style guide formalised in CONTRIBUTING.md.** NumPy docstrings,
  module headers with an Author link, and full type annotations
  are now enforced for new and modified code.

### Changed
- **Package description** mentions PDF alongside DOCX/PPTX.
- **README + LISEZMOI installation sections** restructured around the
  three-OS pattern with the `brew.sh` hint for macOS and `pipx
  install md2star` as the recommended path.
- **`md2star doctor`** no longer reports a "GUI" feature target.

### Fixed
- **PDF tables render correctly via headless LibreOffice.** The
  bundled template's `TableNormal0` custom-style caused soffice to
  spill table cell content out of the table as a vertical paragraph
  dump (Word rendered the same DOCX fine — the bug was the style +
  soffice's interpretation). The PDF pipeline now strips
  `TableNormal0` from the intermediate DOCX before invoking
  soffice (`md2star/postprocess.py:strip_table_normal_for_pdf`).
  DOCX output (`md2docx`) is untouched, so Word users keep the
  styled tables. Test coverage in
  `tests/test_postprocess.py`. Resolves the `[1.1.1] — Known
  issues` entry below.

### Removed
- `md2star/gui_server.py` (the GUI HTTP server).
- `md2star/data/gui/` (vendored Tailwind / CodeMirror / PDF.js / fonts).
- `tests/test_gui_security.py` (`/fs/*` path-confinement tests).
- `scripts/vendor_gui.sh` and the `make vendor` target.
- `md2star html` standalone-HTML subcommand (it existed solely for
  the GUI preview pane).
- The `[Public Domain]` classifier in `pyproject.toml`, replaced by
  `[OSI Approved :: BSD License]`.

## [1.3.0] — 2026-06-23

### Added
- **AI-drafted alt-text for empty image alts** — when `--lint` is on
  and Ollama is reachable, every `![](src)` whose alt is empty is
  described by a local vision model and the rewritten `![<alt>](src)`
  is what Pandoc sees. URLs, missing files, and non-empty alts pass
  through untouched. Same opt-in surface as the LLM Markdown lint —
  alt-text drafting *is* a form of lint, so it sits behind the same
  `--lint` flag (and `--offline` blocks it just like the text lint).
  Default vision model is whatever the text lint already uses
  (`gemma4:e2b-mlx` on macOS, `gemma4:e2b` elsewhere) — the gemma4
  family is multimodal, so a single `ollama pull` powers both passes.
  Override with `MD2STAR_ALT_TEXT_MODEL` to point alt-text at a
  different vision model. Per-image results are cached at
  `$XDG_CACHE_HOME/md2star/alt-text/<image-md5>_<model>.txt` so reruns
  over the same source tree do not re-query Ollama.

## [1.2.0] — 2026-06-23

### Added
- **Branded Mermaid palette** — every rendered diagram now uses the
  Warith colour system from
  [harchaoui.org/warith/colors](https://harchaoui.org/warith/colors):
  light-blue node fills (`#CCE4FF`) with blue borders (`#007AFF`),
  grey edges (`#808080`), light-yellow notes (`#FFF5CC`), and matching
  actor / activation / cluster colours for sequence and gantt
  diagrams. The bundled `mermaid-config.json` switched from `neutral`
  to `base` plus a full `themeVariables` block. Re-rendering is
  automatic — the render-cache key now folds in the resolved config
  hash, so palette edits invalidate stale PNGs on the next run.
- **Aspect-ratio-aware image cap (A4)** — bare `![](…)` images get a
  `{width=15cm}` *or* `{height=17cm}` block based on the image's
  pixel aspect ratio, so the rendered diagram or photo fits an A4
  page in *both* dimensions. Applies uniformly to mermaid renders,
  embedded photos, downloaded remote images, and SVG-to-PNG
  conversions. URLs and unreadable files keep the previous
  `{width=100%}` fallback.

### Fixed
- **Pandoc 3.6 Lua filter crash on tables** — `pandoc.utils.stringify`
  no longer accepts a `Cell` userdata directly; the filter now passes
  `cell.contents` so DOCX / PPTX builds work on Pandoc 3.6+ across
  the whole table-styling path.
- **Python 3.10 / 3.11 `_data_path` crash** —
  `MultiplexedPath.joinpath` only accepted one argument per call on
  3.10–3.11; walking the components one at a time restores the
  multi-segment `_data_path("filters", "md2star.lua")` form.
- **Windows date-format crash** — Windows' MSVCRT `strftime` rejects
  `%e` (a GNU extension). The Lua filter now expands `%e` to the
  literal day-of-month before handing the format string to
  `os.date`.
- **Mermaid rendering on Ubuntu 24.04+ CI runners** — Puppeteer's
  default sandbox is blocked by AppArmor user-namespace restrictions
  on recent Linux distros. A bundled `puppeteer-config.json` passes
  `--no-sandbox --disable-setuid-sandbox` to mmdc so headless Chrome
  starts cleanly.
- **Bundled templates ship in the wheel** — `template.docx` and
  `template.pptx` were silently excluded by the blanket `*.docx` /
  `*.pptx` gitignore rules. Allow-listed under `md2star/data/` so
  the built sdist / wheel always carry them.

## [1.1.1] — 2026-06-21

### Added
- **`assets/example.md`** — the canonical default demo content. The
  GUI's `/example` endpoint serves it; the editor loads it as the
  initial document when no localStorage / server draft is present.
  Also used as the default in screenshots and any future demo runs.
- **`md2star html`** (and `md2html` if you alias it) — pandoc-only
  HTML5 output path. Standalone document with MathML, inline CSS via
  the bundled `preview.css`. Useful as a fast preview or for
  publishing markdown to a website without the full Office pipeline.
- **GUI Save button** (replaces the old Clear button) — forces the
  4 s auto-save to run RIGHT NOW. Writes to `/fs/save` when a real
  file is loaded; falls back to the XDG draft cache otherwise. Status
  bar confirms the destination.

### Fixed
- **`md2pdf` first-invocation crash** — the collision check used
  `Path.samefile(out_path)` which raises `FileNotFoundError` when the
  output PDF doesn't exist yet (i.e. every first run). Replaced with
  an unconditional `.md2star.tmp.docx` sidecar so md2pdf can never
  stomp a user's real `.docx` even on a repeat run.
- **GUI pane-header heights are now uniform** (`min-h-9` on every
  sidebar / editor / preview header bar) so the three columns'
  filename rows line up regardless of which buttons live in each.

### Known issues
- **Tables in the live PDF preview render with empty cells** in some
  environments — the cell contents leak below the table border as a
  vertical paragraph dump. Root cause is an interaction between the
  bundled `template.docx` styles (specifically the `TableNormal0`
  custom-style on top of pandoc's "Compact" cell paragraph) and
  LibreOffice's headless renderer. Workarounds while a deeper fix
  lands: (a) export to DOCX and open in Word, which renders the
  table correctly; (b) write tables as raw `<table>` HTML inside the
  markdown — those are passed through and styled by your reference
  template; (c) avoid the preview rendering of tables and trust the
  DOCX export. The DOCX itself is well-formed; only the soffice →
  PDF intermediate stumbles.

## [1.1.0] — 2026-06-21

### Added
- **`md2pdf` / `md2star pdf`** — first-class PDF output. Internally runs
  the DOCX pipeline (so mermaid, table styles, slide-aware tweaks all
  apply) then renders to PDF via headless LibreOffice
  (`soffice --headless --convert-to pdf`). Honors every flag `md2docx`
  accepts (`--author`, `--bib`, `--lang`, `--date`, `--skip-phase`,
  `--lint`, `--reference-doc`).
- **`--date "string"` CLI flag** (and matching GUI field) overrides
  the auto-localized date in the subtitle. Lets authors backdate,
  post-date, or stamp a non-date label ("Draft 2", "Q2 2026",
  "submitted 14 March") without fighting the auto-locale path. The
  Lua filter gains a `date_override` metadata branch that takes
  priority over `date_format`.
- **`md2star gui`** — Overleaf-style local web editor. Highlights:
  - CodeMirror 6 Markdown editor (left) + PDF.js preview (right).
  - Debounced auto-render ~2.5 s after typing pause; **⌘↵** / **Ctrl ↵**
    forces a preview-only render (never downloads).
  - Format pill (PDF / DOCX / PPTX) with uniform **"Export X"** buttons.
    Clicking exports + downloads in the chosen format and refreshes the
    PDF preview.
  - **Folder browser sidebar**: Open a folder (native macOS picker via
    `osascript`, `zenity`/`kdialog` on Linux, `FolderBrowserDialog` on
    Windows, or paste a path). Sidebar shows the tree with expandable
    subdirectories. Click an `.md` to load (and any edits auto-save
    back to that file). Non-`.md` files are visible but click-disabled.
    `+` creates a new `.md`, `🗑` deletes selected files (multi-select
    via checkboxes; only `.md` is ever deleted as a safety guard).
  - **Server-side auto-save**: every edit persists 4 s after the last
    keystroke. Routes to `/fs/save` when a real file is open;
    otherwise to `$XDG_CACHE_HOME/md2star/drafts/last.md` as a
    safety net. `navigator.sendBeacon` fires on tab close so the
    very last edit can't get lost in the debounce window.
  - **Theme toggle** (🌗 Auto / 🌞 Light / 🌚 Dark). Auto follows the
    system `prefers-color-scheme`; choice persists in localStorage.
  - **Custom reference templates**: two upload buttons in the options
    drawer ("Load DOCX template" / "Load PPTX template") let the user
    swap the bundled defaults for the active session. The uploaded
    file lives in a per-process tempdir and is removed on
    `/template/clear`.
  - Backend is stdlib `http.server` on 127.0.0.1 only; no
    authentication (single-user laptop tool, same model as Jupyter).
- **WCAG-AA-compliant color tokens** lifted from
  `https://harchaoui.org/warith/colors/` (full base palette + light
  variants, semantic aliases for surface / label / brand). Uniform
  **10 px corner radius** across every container, button, input,
  drawer, chip, and PDF-page card.
- **Install-time LibreOffice check**: `scripts/install.sh` /
  `scripts/install.ps1` auto-install LibreOffice via Homebrew /
  apt / dnf / pacman / winget when `soffice` is missing, so
  `md2pdf` and the GUI preview pane work out of the box. Pass
  `--no-libreoffice` (or `-NoLibreOffice` on Windows) to opt out.
- **Two-line subtitle** (authors on line 1, date on line 2) — the
  Lua filter emits two `<w:p>` paragraphs inside the `Subtitle`
  custom-style Div, both styled identically. Long author lists no
  longer collide with the date on a single line.
- **Natural-language author list**: a comma-separated `--author`
  string is rewritten as "X" / "X and Y" / "X, Y and Z". The
  conjunction follows the document language: English "and",
  French "et", Spanish "y", German "und", Italian/Portuguese "e",
  Dutch "en", Russian "и"; falls back to "and" for any other.

### Changed
- **GUI is now fully offline.** Tailwind, CodeMirror, PDF.js (worker
  included), Montserrat, and Roboto Serif are vendored under
  `md2star/data/gui/vendor/` (~3.1 MB) and served from the local
  `/vendor/*` paths. `md2star gui` makes zero CDN calls at runtime.
  Refresh script: `make vendor` (requires `curl` + `node`).
- **CodeMirror is bundled as one esbuild artifact** (not 5 separate
  esm.sh URLs) — separate bundles would each carry their own
  `EditorState` constructor and `instanceof` checks would silently
  break the editor.
- **Dropped JetBrains Mono** as the editor font; the OS's own system
  monospace stack (`ui-monospace`, `SFMono-Regular`, `Menlo`,
  `Monaco`, `Consolas`) is enough and saves ~100 kB of vendored
  fonts. Added **Roboto Serif** as the serif token
  (`class="font-serif"`) alongside Montserrat for sans.
- **deraison.ai template fetch** now caches the downloaded template
  in `$XDG_CACHE_HOME/md2star/templates/` instead of dropping a
  ~2 MB / 16 MB file next to every source `.md`. First download
  prints one breadcrumb; subsequent runs are silent. Users still
  get per-project branding by placing their own `template.{docx,pptx}`
  next to the source.

### Fixed
- **`pyproject.toml` wheel-build failure**: removed the
  `[tool.hatch.build.targets.wheel.force-include]` block that was
  duplicating `md2star/data/` (already covered by `packages =
  ["md2star"]`) and breaking `pipx install`.
- **GUI preview-empty placeholder stayed visible** after the first
  successful render. Tailwind's `display: grid` on the placeholder
  beat the browser's `[hidden] { display: none }` UA rule. Switched
  to `.classList.add("hidden")` (Tailwind's `display: none
  !important`).
- **Cache-busting**: GUI server splices a per-process random tag
  into every static-asset URL so stale browsers can't keep serving
  pre-restart `app.js` / `codemirror.js` / `pdf.min.mjs`.

### Notes
- The folder-browser endpoints (`/fs/*`) confine every operation to
  the user-chosen root via `_safe_within_root` (rejects `..`,
  absolute paths, symlink escapes). Delete refuses anything that
  isn't `.md`/`.markdown`. Localhost-only, no auth — same trust
  model as Jupyter or Vite dev. Don't expose to the LAN.

## [1.0.0] — 2026-06-20

The first proper release. The legacy "git clone + `make install`" workflow
is replaced by a real Python package; the bash / PowerShell / cmd CLI
wrappers are replaced by a single Python entry-point module.

### Added
- **`pyproject.toml`** — md2star is now a real installable Python package
  (`pip install -e .` for dev, `pipx install .` for end users).
- **Console scripts** `md2docx`, `md2pptx`, and `md2star` are registered
  via `[project.scripts]` and implemented once in `md2star/cli.py`.
- **`md2star/cache.py`** — every on-disk artifact (downloaded remote
  images, downscaled rasters, cell-fitted images, SVG→PNG renders, mermaid
  PNGs) now lives under `$XDG_CACHE_HOME/md2star/` (or the platform
  equivalent on macOS / Windows). The user's source directories stay clean.
- **`md2star clear-cache`** and **`md2star cache-dir`** subcommands.
- **`--skip-phase NAME`** CLI flag (repeatable) and matching
  `md2star_skip:` YAML front-matter key. Twelve named phases are
  addressable: `lint`, `remote_images`, `html_tables`, `html_images`,
  `absolutize`, `image_assets`, `language`, `line_pass`, `table_resize`,
  `table_normalize`, `image_widths`, `pptx_isolation`.
- **`MD2STAR_LINT_MODEL`** environment variable to override the default
  Ollama lint model without editing code.
- **GitHub Actions CI** (`.github/workflows/ci.yml`) — pytest matrix on
  Python 3.10–3.13, integration suite on Ubuntu + macOS + Windows,
  `shellcheck` on the install scripts.
- **Lua filter unit tests** (`tests/test_lua_filter.py`) — title
  extraction, subtitle injection, French date rendering, heading-ID
  strip, DOCX horizontal-rule → page break.
- **Postprocess unit tests** (`tests/test_postprocess.py`) —
  `inject_table_styles` idempotency, partial-pre-existence, byte-identical
  preservation of unrelated zip entries.
- **`CONTRIBUTING.md`** with quickstart (`make dev` + pytest) and PR
  checklist.

### Changed
- **Install path** is now `pipx install .` (or `make install`). The old
  `bash scripts/install.sh` writes a thin wrapper that just shells to
  pipx; the 150+ lines of heredoc'd shell CLI are gone.
- **`scripts/test.sh`** no longer mutates `pandoc/metadata.yaml` mid-run
  (which left the repo dirty on Ctrl-C). French date / language is now
  passed via `--lang fr-FR --metadata date_format=...` per call.
- **Repo size shrunk by ~40 MB** — the regenerable `.docx` / `.pptx`
  fixtures under `tests/examples/` are no longer committed (sources are
  kept; outputs are produced by `tests/examples/run.sh`).
- **Default reference templates** are now bundled inside the wheel
  (`md2star/data/template.{docx,pptx}`) so a fresh install works fully
  offline. The `https://deraison.ai/template.{docx,pptx}` fallback is
  still consulted when no `template.{docx,pptx}` sits next to the input
  Markdown (preserved per project owner's request).
- **`make uninstall`** now prints what it will remove and prompts `[y/N]`.
  Pass `--yes` to skip the prompt in CI.

### Fixed
- The committed `tests/examples/.preprocessed_63am_59p.md` artifact (a
  stale temp file) is removed from the repo. The `.gitignore` rule that
  excludes it was already in place.
- Image cache filenames now use a hash of the source path, eliminating
  the rare collision when two source files with the same basename lived
  in different directories.

### Notes
- The `gemma4:e2b` (Linux/Windows) and `gemma4:e2b-mlx` (macOS) default
  lint models are confirmed published Ollama tags and remain the default.
- A WYSIWYG markdown editor / local GUI is planned for v1.1.0, building
  on the `front-ui` + `front-cli-gui` Claude Skills.
