# md2star Developer Guide 🛠️⭐️

Welcome to the **md2star** engineering documentation! This guide covers the pipeline architecture, each processing layer, and the testing framework.

---

## 🏗️ Conversion Architecture

Your Markdown goes through three layers before becoming a `.docx` or `.pptx`:

```mermaid
graph TD;
    A[Raw Markdown File] -->|CLI Invocation| B(Python Preprocessor)
    B -->|Normalizes AST & Fixes Spacing| C{Mermaid Check?}
    C -- Yes --> D[Mermaid CLI (mmdc)]
    D -->|BASE64 -> PNG Cache| E[Inject Image Links]
    C -- No --> E
    E -->|Clean Markdown| F(Pandoc Engine)
    F -->|Lua Filter: AST Analysis| G[Extract Metadata]
    G -->|Custom Attributes| H[Inject Localization]
    H -->|Reference Template| I[Output: .docx / .pptx]

    classDef python fill:#3776ab,stroke:#fff,stroke-width:2px,color:#fff;
    classDef lua fill:#2c2d72,stroke:#fff,stroke-width:2px,color:#fff;
    
    class B,C,D,E python;
    class F,G,H lua;
```

---

## 🐍 1. Python Preprocessing Engine

**Entry point:** [`md2star/cli.py`](../md2star/cli.py) — the single Python module that registers the `md2docx`, `md2pptx`, and `md2star` console scripts.

**Implementation:** [`md2star/preprocessing/`](../md2star/preprocessing/) (9 modules; run `wc -l md2star/preprocessing/*.py` for an up-to-date total)

Runs **before** Pandoc touches the file. The CLI reads the input, hands off to `md2star.preprocessing.preprocess_markdown`, and writes the result to a temp file alongside the input so relative image/link paths keep resolving.

### Package layout

| Module | Responsibility |
|--------|----------------|
| `pipeline.py` | Orchestrator: runs phases in order, handles list-spacing, fenced-block tracking, Mermaid extraction, and PPTX slide isolation (images **and** tables) |
| `tables.py` | `<table>` HTML → Pandoc pipe-table; **pipe-table separator normalization** (proportional dashes, soft-break injection, long-cell `<br/>` wrap) |
| `images.py` | `{width=100%}` injection, in-cell physical resize (Pillow), `http(s)://` image download, **relative-path absolutization** so `md2docx subdir/file.md` resolves images regardless of cwd |
| `mermaid.py` | Local diagram rendering via `npx @mermaid-js/mermaid-cli` (cached under `$XDG_CACHE_HOME/md2star/mermaid/` by MD5; cache key includes the active template body font — see "Mermaid font cache invariant" below) |
| `language.py` | `langdetect` → `lang` + `date_format` YAML injection |
| `lint.py` | Auto-enabled Ollama-based syntax fixer (text-only `gemma4:e2b-mlx` on macOS / `gemma4:e2b` elsewhere); pulls the model on first use if missing |
| `math.py` | Unwraps backtick-wrapped LaTeX math (``` `$x^2$` ``` → `$x^2$`); merges mixed prose+math spans into a unified `$..$` expression; exposes `MATH_FORMULA_RE` for other passes to protect math chunks |
| `regexes.py` | Shared compiled regexes used across the package (currently `PIPE_TABLE_ROW_RE`) so sibling modules do not reach into each other's private symbols |

### Phase order (executed by `pipeline.preprocess_markdown`)

| # | Phase | What it solves |
|---|-------|---------------|
| 1 | **LLM lint** (opt-in, `--lint`) | Fix syntax-level errors (broken links, unclosed fences, malformed pipes) via Ollama. Off by default. |
| 2 | **Remote image download** | Pandoc cannot reliably embed `http(s)://` images in DOCX/PPTX; we fetch them to local temp files first. |
| 3 | **HTML table conversion** | Pandoc DOCX silently drops raw HTML; `<table>` blocks are converted to pipe-tables. |
| 4 | **Language detection** | `langdetect` → `lang` (BCP 47) and `date_format` (strftime) inserted into the YAML front-matter. |
| 5 | **Line pass** (math-in-code unwrap, Mermaid render, list-spacing) | Per-line transforms over the body, with fenced code blocks skipped wholesale so their content stays verbatim. |
| 6 | **In-cell image resize** | Images embedded in pipe-table cells are physically downscaled with Pillow (Pandoc's `{width=100%}` refers to the page, not the cell). |
| 7 | **Pipe-table separator normalization** | Proportional dashes scaled past Pandoc's 72-char column threshold so DOCX/PPTX honour per-column widths; ZWSPs after `/` and `_` in long unbreakable runs; `<br/>` wraps for >120-char cells; trailing blank line. |
| 8 | **Standalone image width injection** | `{width=100%}` for non-cell images. |
| 9 | **PPTX slide isolation** | Inserts a blank `##` heading before standalone images **and** before tables that follow other content in the same `## H2` section (Pandoc otherwise drops images or cramps tables). |

### Key design decisions

- **Temporary file output**: The preprocessor writes to a temp file in the same directory (not `/tmp`) so relative paths in image links keep working.
- **Code block preservation**: Lines inside fenced code blocks are never modified, even if they contain list-like syntax.
- **Idempotency**: Running the preprocessor twice on the same input produces the same output.
- **LLM lint is opt-in**: it requires Ollama, adds latency, and can in rare cases rewrite content despite the 0.5×–2× length safety guard. Off by default; pass `--lint` to enable.
- **Skippable phases**: pass `--skip-phase <name>` to disable a specific phase (or list `md2star_skip: [name, ...]` in the document's YAML front-matter). See `md2star.preprocessing.PHASES` for the canonical name set.

### Mermaid font cache invariant

The mermaid cache key is **`md5(source_text || body_font)`**, not just
`md5(source_text)`. The body font is read from the active reference
template's `word/styles.xml` (`md2star.preprocessing.mermaid._template_body_font`)
and spliced into the mermaid theme so rendered diagrams visually match
the surrounding prose. Practical consequence: **changing the reference
template's body font invalidates every previously cached mermaid PNG.**
This is intentional — without the font in the key, you would see stale
diagrams in the wrong typeface after a template swap. If you ever need to
force a re-render, `md2star clear-cache` is the escape hatch.

> [!NOTE]
> Mermaid diagrams are otherwise cached forever; they are only re-rendered when their source content or the template body font changes.

---

## 🌙 2. Lua Filter (Pandoc AST Hook)

**Path:** [`pandoc/filters/md2star.lua`](../pandoc/filters/md2star.lua) (~177 lines)

Intercepts the Pandoc AST during conversion and performs five operations:

| # | Operation | Description |
|---|-----------|-------------|
| 1 | **Title extraction** | Captures the first `# H1 Heading` and promotes it to document `title` metadata. Removes the heading from the body to avoid duplication. |
| 2 | **Author handling** | Reads `author` metadata when present and folds it into the subtitle. No placeholder is shipped by default — pass `--author "Name"` per-document. |
| 3 | **Date localization** | Maps `lang` to built-in translation dictionaries (7 languages: fr, es, de, it, pt, nl, ru). Replaces `%A` and `%B` in `date_format` with localized day/month names. Does **not** rely on `os.setlocale()`. |
| 4 | **Subtitle injection** | Builds an "Author, Date" string, wraps it in `custom-style="Subtitle"`, and inserts it after the title. |
| 5 | **Heading ID cleanup** | Strips automatic heading identifiers (`{#my-heading}`) which are meaningless in Office exports. |

### Why not rely on OS locale?

`os.setlocale()` is notoriously unreliable:
- macOS ships with few locales installed
- Docker containers often lack locale data
- Windows uses a different locale system

Instead, the filter carries its own day/month name dictionaries and performs string replacement before calling `os.date()`. This guarantees `dimanche 10 mai 2026` works everywhere.

> [!WARNING]
> The Lua filter modifies the document AST. If you change the title extraction logic, test with `make test` to ensure subtitle injection still works correctly.

---

## 🎨 3. Template Adapter (separate repo)

The AI-powered PPTX template adapter lives in its own repository:
[**md2star-adapt**](https://github.com/warith-harchaoui/md2star-adapt). It
classifies corporate template layouts with a local VLM and assembles a
Pandoc-compatible reference doc. Carved out of md2star because its
dependency footprint (PyMuPDF, lxml, python-pptx, requests + Ollama) is
much heavier than the core conversion pipeline needs.

---

## 🧪 4. Testing Framework

### Unit tests (pytest)

**Paths:**
- [`tests/test_preprocessing.py`](../tests/test_preprocessing.py) — the preprocessor pipeline (~80 tests)
- [`tests/test_lua_filter.py`](../tests/test_lua_filter.py) — drives `pandoc --lua-filter` against fixture Markdown (skipped if pandoc is not on PATH)
- [`tests/test_postprocess.py`](../tests/test_postprocess.py) — `inject_table_styles` round-trip on a synthesised DOCX zip

| Test class | Coverage |
|------------|----------|
| `TestPreprocessMarkdownBasic` | Empty input, no lists, whitespace-only |
| `TestUnorderedLists` | Dash, star, plus markers, no-double-blank, consecutive items |
| `TestOrderedLists` | Numbered items, multi-digit numbers |
| `TestNestedLists` | Indented sub-items |
| `TestCodeBlocks` | Code block preservation, surrounding text |
| `TestMixedContent` | Headings + lists + paragraphs |
| `TestMermaidBlocks` | Mocked Mermaid CLI success/failure |
| `TestBibliographyCitations` | Citations in lists, inline citations |
| `TestHtmlTables` | Simple tables, inline HTML, multirow, separator rows |
| `TestPipeTableNormalization` | Proportional dashes, alignment markers, idempotency, code-block escape, soft-breaks, `<br/>` wrapping, math protection |
| `TestImageWidths` | Bare images, existing widths, empty alt text |
| `TestPptxSlideIsolation` | Tables/images after prose split onto fresh slides; first-in-section table left alone; code-fenced pipe-tables ignored |
| `TestMathInCodeSpans` | Pure math unwrap, mixed prose+math merge, snake_case rewriting, fenced-block protection, math inside table cells |
| `TestLanguageDetection` | English/French detection, existing lang preserved (skipped if `langdetect` not installed) |

```bash
make dev                                # creates .venv/ + pip install -e .[dev]
./.venv/bin/python -m pytest tests/ -v
```

### Integration tests (shell)

**Path:** [`scripts/test.sh`](../scripts/test.sh)

Exercises the full `md2docx` / `md2pptx` pipeline against sample Markdown files and verifies output by inspecting the generated OOXML.

```bash
make test
```

---

## 📁 Repository Structure

```
md2star/
├── md2star/                          # Importable Python package
│   ├── __init__.py                   # Re-exports preprocess_markdown, __version__
│   ├── cli.py                        # md2docx / md2pptx / md2pdf / md2star console scripts
│   ├── cache.py                      # $XDG_CACHE_HOME/md2star/ resolver
│   ├── doctor.py                     # `md2star doctor` environment diagnostic
│   ├── gui_server.py                 # `md2star gui` local web editor (stdlib http.server, 127.0.0.1)
│   ├── errors.py                     # Typed exception classes
│   ├── postprocess.py                # DOCX table-style re-injection
│   ├── preprocessing/                # Preprocessor package (one module per phase)
│   │   ├── __init__.py
│   │   ├── pipeline.py               # Orchestrator + PPTX slide isolation + PHASES
│   │   ├── tables.py                 # HTML <table> → pipe-table + width normalization
│   │   ├── images.py                 # Width injection, cell resize, remote download
│   │   ├── mermaid.py                # mmdc-based diagram rendering
│   │   ├── language.py               # langdetect → lang / date_format metadata
│   │   ├── lint.py                   # Opt-in Ollama syntax fixer
│   │   ├── alt_text.py               # Opt-in Ollama vision-model alt-text drafter
│   │   ├── math.py                   # Math-in-code unwrapping
│   │   └── regexes.py                # Shared compiled regexes
│   └── data/                         # Bundled package data
│       ├── filters/md2star.lua       # Pandoc Lua filter (title, subtitle, date_override, …)
│       ├── gui/                       # Vendored GUI frontend (PDF.js, CodeMirror, Tailwind, fonts)
│       ├── defaults/                 # Pandoc --defaults YAMLs (vestigial; CLI uses explicit flags)
│       ├── metadata.yaml             # Global metadata defaults
│       ├── mermaid-config.json       # mmdc theme defaults
│       ├── puppeteer-config.json     # mmdc / Puppeteer sandbox tweaks (Ubuntu 24.04 AppArmor)
│       ├── template.docx             # Bundled default reference template
│       └── template.pptx             # ditto
├── assets/                            # Sample inputs + bibliography
│   ├── docx/                         # basic.md, with_author.md, with_bib.md, with_lang.md, math.md
│   ├── pptx/                         # example.md
│   └── references.bib                # BibTeX for citation tests
├── docs/developer_guide.md           # This file
├── tests/
│   ├── conftest.py                   # Autouse fixture: cache → tmp_path per test
│   ├── test_preprocessing.py         # ~80 unit tests for the preprocessor
│   ├── test_lua_filter.py            # End-to-end Lua filter tests via pandoc
│   ├── test_postprocess.py           # inject_table_styles round-trips
│   ├── test_gui_security.py         # `/fs/*` path-confinement tests for the GUI server
│   └── examples/                     # Multi-page demo .md inputs (outputs regenerable via run.sh)
├── scripts/
│   ├── install.sh / install.ps1      # pipx installer + LibreOffice auto-install (--no-libreoffice opt-out)
│   ├── uninstall.sh / uninstall.ps1  # Confirm + pipx uninstall + legacy cleanup
│   └── test.sh                       # Integration suite
├── .github/workflows/ci.yml          # pytest matrix + integration + shellcheck
├── Makefile                          # `make install / dev / test / build / publish`
├── pyproject.toml                    # Package definition (replaces requirements.txt)
├── CHANGELOG.md
├── CONTRIBUTING.md
├── README.md / LISEZMOI.md           # User docs (EN / FR)
└── EXAMPLES.md                       # Syntax reference
```

## 🌐 5. GUI status

The Overleaf-style local web editor was **restored in v2.6.0**,
**bundled in the core wheel** (no `md2star[gui]` extra needed).
Invoke it with `md2star gui`. The server module is
`md2star/gui_server.py` — pure Python stdlib `http.server` bound to
`127.0.0.1`, adding **zero** extra Python dependencies. The entire
frontend (PDF.js, CodeMirror, Tailwind, Montserrat + Roboto Serif) is
vendored under `md2star/data/gui/`, which is why the wheel grew from
~200 KB back to ~2.3 MB. Path confinement of the `/fs/*` endpoints
(root-confined folder browser, in-session reference-template upload,
server-side draft auto-save) is covered by
`tests/test_gui_security.py`. It is a fully offline, localhost-only
Markdown→PDF editor with live PDF preview (PDF.js).
