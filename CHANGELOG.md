# Changelog

All notable changes to **md2star** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
