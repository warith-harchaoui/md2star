# Contributing to md2star

Thanks for considering a contribution. md2star is a small project with one
maintainer — small, well-scoped PRs are very welcome.

## Quickstart

```bash
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star

# Create a dev venv at .venv/ and install the package editable + dev extras.
make dev

# Activate it (or use ./.venv/bin/<tool> directly).
source .venv/bin/activate

# Run the test suite.
python -m pytest tests/ -v

# Or just the fast subset (skips the LibreOffice/kreuzberg OCR round-trip).
python -m pytest -m "not slow" -q

# Run the integration suite (needs pandoc + the package installed).
make test
```

`make dev` is the only setup step. `pyproject.toml` declares everything
else (runtime deps, dev deps, console scripts, package data).

If you prefer not to use `make`, the equivalent one-liner into an
already-activated venv is `pip install -r requirements-dev.txt` (installs
`-e .[dev]`: pytest, pytest-cov, ruff, pypdf, the api/mcp deps, and
kreuzberg for the OCR round-trip test). `pip install -r requirements.txt`
gives you the runtime set only (`-e .`).

## Project layout

- `md2star/` — the importable Python package.
  - `cli.py` — the single source of truth for `md2docx` / `md2pptx` /
    `md2pdf` / `md2star`. There used to be a bash wrapper, a PowerShell
    wrapper, and a `.cmd` wrapper. Don't bring them back.
  - `click_cli.py` — the `md2star-x docx|pptx|pdf|gui|doctor` click
    front-end. It is a *thin adapter*: it delegates to
    `cli._convert`, so behaviour is defined once. Add a flag in
    `cli.py` first, then wire it through here — never fork the logic.
  - `api.py` / `mcp.py` — the FastAPI HTTP surface (`md2star-api`,
    `[api]` extra) and the FastAPI-MCP server (`md2star-mcp`, `[mcp]`
    extra). Both wrap the same conversion pipeline.
  - `doctor.py` — `md2star doctor` environment diagnostic.
  - `preprocessing/` — the 12-phase Markdown preprocessor. The order
    is in `pipeline.py` and is *load-bearing*; reordering needs a
    correctness argument.
  - `postprocess.py` — DOCX-only zip rewrite that re-injects the
    `MyTable` / `MyTableSmall` styles Pandoc strips. Idempotent.
  - `cache.py` — XDG cache dir resolver. Override with
    `MD2STAR_CACHE_DIR` (tests do this via the autouse fixture).
  - `data/` — bundled package data (Lua filter, defaults YAMLs,
    templates, Mermaid config).
- `tests/` — pytest suite. `conftest.py` redirects the cache to `tmp_path`
  for every test. The load-bearing files:
  - `test_preprocessing.py` (~85 tests) — the line-level pipeline.
  - `test_postprocess.py` — DOCX style re-injection.
  - `test_lua_filter.py` — the Pandoc Lua filter (drives pandoc as a
    subprocess; skipped when pandoc is not on PATH).
  - `test_offline_security.py` — the `--offline` / `--allow-remote-*`
    network gates (the contract documented in `SECURITY.md`).
  - `test_roundtrip_ocr.py` — the `md → docx → pdf → text` OCR round-trip
    *identity* `g(f(x)) = x`: exact whole-document equality under an explicit
    normal form, for prose (any length), bullet lists, multi-page docs, and
    footnotes (numeric `[^1]` and named `[^aa]`). Marked `slow` (needs
    LibreOffice + kreuzberg); the CI `ocr-roundtrip` job installs the toolchain
    and runs it for real (and fails if it skips).

  Other files cover the CLI surfaces (`test_click_cli.py`,
  `test_api.py`, `test_mcp.py`), the agent skill (`test_skill.py`),
  idempotence (`test_idempotence.py`), doctor, templates, and
  bibliography localization. `test_ai_eval.py` (marker `ai_eval`) is a
  quality eval of the opt-in `--lint` / alt-text passes against a real
  local Ollama daemon and skips cleanly when none is running.
- `minimal-gui/` — the standalone stdlib `md → PDF` preview server
  (`python3 minimal-gui/server.py`). Renamed from the old `overleaf/`;
  don't reintroduce that path.
- `skills/` — the Claude Skill / OpenCode skill packaging
  (`skills/md2star/SKILL.md` + `references/`). The host model only reads
  the `description`, so `scripts/check_triggers.py` enforces trigger
  coverage — edit the description and `references/triggers.md` together
  and re-run it.
- `scripts/` — `install.sh` / `uninstall.sh` / `test.sh` plus the
  PowerShell siblings (`install.ps1` / `uninstall.ps1` / `update.ps1`),
  `brew.sh` (idempotent macOS Homebrew bootstrap), `check_triggers.py`
  (skill trigger coverage), and `audit_comments.py`. Thin wrappers; the
  real install path is `pipx`.
- `docs/developer_guide.md` — architectural notes (the why, not the what).

## PR checklist

Before opening a PR:

- [ ] `python -m pytest tests/ -v` is green (`pytest -m "not slow"` for a
      faster local loop that skips the LibreOffice/kreuzberg round-trip).
- [ ] `ruff check md2star tests` is clean (no new warnings).
- [ ] If you touched the Lua filter, the integration suite still passes
      (`make test`) — pytest alone does not cover end-to-end DOCX output.
- [ ] If you added a new preprocessing phase, register its name in
      `md2star.preprocessing.pipeline.PHASES` so `--skip-phase` knows
      about it, and add at least one test in `tests/test_preprocessing.py`
      covering the skip behavior.
- [ ] No new files in `tests/examples/` larger than ~50 kB unless you've
      checked it in via Git LFS. The regenerable demos live there as
      Markdown only; their `.docx` / `.pptx` outputs are produced by
      `tests/examples/run.sh` and intentionally not committed.
- [ ] If you added user-facing flags, wire them through both the
      argparse `cli.py` and the click `click_cli.py` front-ends, and
      update both `README.md` and `LISEZMOI.md` (and `CHANGELOG.md`'s
      `## [Unreleased]` section).
- [ ] If you changed a capability the agent skill advertises, update
      `skills/md2star/SKILL.md`'s `description` (and
      `references/triggers.md`) and re-run `python scripts/check_triggers.py`
      until it exits 0.
- [ ] If you added a network-touching code path, route it through the
      `--offline` / `--allow-remote-*` gates (see `md2star/cli.py`
      and the contract in `SECURITY.md`).
- [ ] All `.py` files you add or modify keep a module header docstring
      with an Author block linking to
      [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/),
      NumPy-style docstrings on **every** function and class — public
      *and* private (`_helper`, `__dunder__`, nested closures included;
      no exemption for visibility) — and full type annotations.

## Conventions

- **One short docstring per module / function** — public and private
  alike. The codebase already documents *why*, not *what* — keep that
  bias.
- **No backward-compat shims** unless you can name a real outside caller
  that relies on the old API. This is a small, single-author project; do
  the rename and update the imports.
- **Don't add features beyond the PR's stated scope.** A bug fix doesn't
  need surrounding cleanup; a refactor doesn't need to also touch the
  CHANGELOG format. Smaller diffs review faster.

## Rebuilding the bundled templates

`md2star/data/template.docx` and `md2star/data/template.pptx` ship the
branded reference docs that every conversion picks up by default. They
were rebuilt in v2.0.0 from a Pandoc-clean baseline so soffice renders
tables as proper grids (vs the v1.x vertical-dump bug).

To regenerate either from scratch:

1. Dump Pandoc's built-in reference (has every named style /
   layout):

       pandoc --print-default-data-file reference.docx > /tmp/ref.docx
       pandoc --print-default-data-file reference.pptx > /tmp/ref.pptx

2. Write a comprehensive markdown source that exercises every
   element you want to style. The two we used for v2.0 live in
   `.private/template-source.md` (DOCX) and
   `.private/template-pptx-source.md` (PPTX) — copy them as a
   starting point.

3. Render with the default ref:

       pandoc src.md -o branded.docx --reference-doc=/tmp/ref.docx
       pandoc src.md -o branded.pptx --reference-doc=/tmp/ref.pptx

4. Open in Word / PowerPoint / Keynote / LibreOffice and brand:
   fonts, colours, margins, logo in headers / slide masters,
   etc. Don't rename existing styles — pandoc looks them up by
   name (`Heading1`, `Title`, `Hyperlink`, ...). For PPTX, the
   layout names must match the pandoc set: `Title Slide`,
   `Section Header`, `Title and Content`, `Two Content`,
   `Comparison`, `Content with Caption`, `Blank`, `Title Only`,
   `Picture with Caption`.

5. Save back to `md2star/data/template.docx` /
   `md2star/data/template.pptx` and verify:

       md2docx assets/docx/basic.md && md2pdf assets/docx/basic.md
       md2pptx assets/pptx/example.md

   The tables in the PDF should render as a proper grid (not a
   column-major vertical dump); pandoc should not warn about
   missing layout names on the PPTX.

## Reporting bugs

Open an issue with: the input Markdown that triggers the bug, the exact
command you ran, the full stderr output, and your `md2star --version` /
`pandoc --version`. If the bug is in DOCX/PPTX output, attaching the
produced file is much faster than a long description.

## Licence

By contributing you agree your contributions are released under the
**BSD 3-Clause License**, the same licence as the rest of the project.
See [LICENSE](LICENSE) for the full text.
