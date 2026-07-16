# md2star — engineering audit

_Snapshot: 2026-06-29, against `main @ v2.0.0` (CLI-only release;
~3,800 LOC of Python after the GUI removal)._

This audit is the working document for the PyPI debut and the
v2.x trajectory. Every recommendation pins to a file or a specific
behavior — vagueness is the enemy of action.

---

## Executive summary

md2star has solid engineering bones (well-decomposed preprocessor,
substantive test suite, working CI matrix, two prior released
versions) and v2.0.0 lands on PyPI with the smallest credible
surface area. The four things that took it from *personal tool* to
*credible open-source dependency*:

1. **`md2star doctor`** — diagnostic command. Users no longer hit
   "soffice not found" / "pandoc broken" / "mermaid silently
   failed" runtime errors with no path forward.
2. **Offline-by-default.** `_resolve_reference_doc`
   (`md2star/cli.py`) and `download_remote_images`
   (`md2star/preprocessing/images.py`) are gated behind explicit
   `--allow-remote-templates` / `--allow-remote-images` flags;
   `--offline` makes the refusal explicit. *(Update, v2.5.0: the
   reference-template fetch is now on by default — see SECURITY.md —
   with `--no-remote-templates` / `--offline` as the opt-outs. Remote
   images stay opt-in.)*
3. **Conservative installer.** `scripts/install.sh` no longer
   auto-installs LibreOffice without consent — `--install-system-deps`
   is the opt-in.
4. **License is BSD 3-Clause** (was Unlicense / public domain),
   aligning md2star with the scientific-Python conventions.

The GUI shipped in v1.x as a localhost-only Overleaf-style editor.
It was removed for the PyPI debut to keep the wheel under 250 KB
(the vendored Tailwind / CodeMirror / PDF.js / Roboto Serif tree
was ~3 MB). It's slated to come back as the `md2star[gui]` extra
in v2.1; see [ROADMAP.md](../ROADMAP.md).

---

## Forces (keep doing)

- **Phase-bounded preprocessor.** `md2star/preprocessing/pipeline.py`
  documents the 12-phase order with rationale per phase. The
  `--skip-phase` plumbing (and the matching `md2star_skip:` YAML key)
  is the right escape hatch for unusual inputs.
- **Pandoc Lua filter is narrowly scoped.** Five concerns
  (`md2star/data/filters/md2star.lua`) — title extraction, subtitle
  injection, date localisation, heading-ID strip, DOCX page-break
  from `---`. Easy to reason about; ~250 lines.
- **DOCX post-processor.** `md2star/postprocess.py` re-injects
  table styles Pandoc strips. This is *production-grade* work — the
  kind of thing most projects abandon to "use a docx template macro"
  or "preprocess styles.xml upfront".
- **Test coverage on the preprocessor.** 80+ tests, ~1,000 lines, hit
  the genuinely tricky paths (proportional dashes, math protection in
  cells, PPTX slide isolation, fenced-block escape).
- **Single Python entry point.** `md2star/cli.py` is the single
  source of truth for `md2docx` / `md2pptx` / `md2pdf` / `md2star`.
  No bash heredocs, no PowerShell heredocs, no drift across three
  shells.
- **XDG cache discipline.** `md2star/cache.py` keeps every disposable
  artifact (resized images, mermaid PNGs, downloaded remote images,
  rendered SVGs, downloaded templates) out of the user's source dirs.
- **CI exists and is non-trivial.** `.github/workflows/ci.yml` runs
  pytest matrix on Python 3.10–3.13 (ubuntu), integration on
  ubuntu/macos/windows, plus shellcheck.

---

## Technical risks (ranked)

### TR-1 — Soffice + bundled template tables render empty cells

**File**: `md2star/data/template.docx`, observed via
`md2star/cli.py:_convert_docx_to_pdf`.

The `TableNormal0` custom-style in the bundled template interacts
badly with LibreOffice's headless `--convert-to pdf`: cell content
leaks out of the table as a vertical paragraph dump. Word renders the
same DOCX correctly. Bare pandoc (no `--reference-doc`) also
produces a correctly-rendered PDF via soffice — the bug is the
template + the renderer.

**Documented as a known issue** in `CHANGELOG.md` under v1.1.1. The
real fix is a template rebuild from a known-good base (a manually
authored Word doc, not the deraison.ai one), removing
`TableNormal0` plus auditing for similar custom-styled artifacts.

### TR-2 — `md2pdf` has no pytest coverage

The DOCX → soffice → PDF path is exercised by the integration shell
script (`scripts/test.sh`) but not by pytest. Failures in soffice's
output handling (the TR-1 family) only surface manually. Adding a
pytest test that skips when soffice is missing closes this gap.

### TR-3 — No structured logging

The codebase still uses bare `print(..., file=sys.stderr)` for every
warning / informational message (template fallback notices, lint
hints, postprocess warnings). A stdlib `logging`-based migration
(one `logger = logging.getLogger("md2star")` + a single
`StreamHandler` in `cli.main` + `--verbose` / `--quiet` flags) is
queued as a v2.1 P1 item. Stdlib-only so no new runtime dep.

---

## Security risks (ranked)

### SR-1 — Implicit network access in default paths (FIXED in v1.2)

Resolved in v1.2.0 — `--offline`, `--allow-remote-templates`,
`--allow-remote-images` flags + typed `RemoteResourceDisabledError`.
md2star is now offline-by-default; the only network paths are
opt-in. Test coverage in `tests/test_offline_security.py`.

### SR-2 — `MD2STAR_LINT_MODEL` env override is unbounded

**File**: `md2star/preprocessing/lint.py:_default_lint_model`.

The user can set any string here, and `ollama pull <string>` runs as
a subprocess. Not exploitable per se (Ollama validates its own model
names), but worth noting in the security model doc.

---

## Packaging / install risks

### PI-1 — `scripts/install.sh` auto-runs `brew install --cask libreoffice` (FIXED in v1.2)

Resolved — installer is now conservative by default; LibreOffice
auto-install requires `--install-system-deps`.

### PI-2 — Two README copies (EN + FR) drift

`README.md` and `LISEZMOI.md` are maintained in parallel. Reasonable
for v2.x (the author's audience is bilingual), but the consistency
burden grows linearly. Long-term: a `docs/i18n/` dir with one source
per language is cleaner; the per-language README stays minimal and
links into the docs tree.

### PI-3 — Wheel size

v2.0.0 wheel is ~200 KB after GUI removal (was ~2.3 MB in v1.x).
Document the size delta in `CHANGELOG.md` so users notice the win.

---

## UX risks

### UX-1 — `md2pdf` crashes on first run when soffice is missing

Throws `FileNotFoundError` rather than a friendly "soffice not
installed; run `md2star doctor`" message. Same pattern affects
mermaid (silent "diagram disappeared"), citeproc bibliography
(`pandoc citeproc not installed`), lint (`ollama not running`).
**Need typed exceptions**: `MissingDependencyError`,
`TemplateNotFoundError`, `RemoteResourceDisabledError`,
`ConversionError`, `InvalidInputError`, `UnsafePathError`. CLI
catches them at the top and prints a one-paragraph hint pointing
at `md2star doctor`.

### UX-2 — No `md2star convert <file>` general entrypoint

Today the user picks the format via the binary: `md2docx` /
`md2pptx` / `md2pdf`. The top-level `md2star` has subcommands
`docx` / `pptx` / `pdf`. Some users would prefer `md2star convert
foo.md --to pdf` as the one-handle interface. Not breaking to keep
both. **Defer** to P1; document the existing UI clearly first.

### UX-3 — `--help` is dense

`md2docx --help` lists 8 flags + appends `pandoc --help` for
unrecognized-flag passthrough. The result is a wall of text. Add a
short "EXAMPLES" section at the bottom of the help text.

---

## Priorities

### P0 — shipped (v2.0.0 PyPI debut)

1. **BSD 3-Clause license**, replacing the Unlicense.
2. **GUI removed** for a lean wheel; restoration planned via
   `md2star[gui]` extra in v2.1.
3. **NumPy-style docstrings + module Author block** on every
   `md2star/*.py`.
4. **Templates rebuilt** from a Pandoc-clean baseline — fixes the
   v1.1.1 known issue where soffice rendered tables as a vertical
   dump.
5. **CHANGELOG / README / LISEZMOI / SECURITY / CONTRIBUTING /
   docs refresh** for the PyPI cut.
6. **`make build` + `make publish` Makefile targets** so the
   release path is two commands away.

### P1 — next sprint (v2.1)

1. **`md2star[gui]` PyPI extra** restoring the local web editor.
2. **`md2star[ai]` PyPI extra** introducing the `ollama` Python
   client and a thin typed wrapper around the existing `--lint`
   / alt-text code.
3. **`md2star templates {list,path}`** — show what templates are
   available and where they live.
4. **`$XDG_CONFIG_HOME/md2star/config.toml`** via `platformdirs`.
   CLI > config > defaults. `md2star config {path,show,init}`.
5. **Typed exceptions across the CLI** — pretty-print at the top of
   `cli.main`, never raw stacktraces for known failure modes.
6. **Migrate remaining `print(..., file=sys.stderr)` to stdlib
   `logging`** behind a single named logger, and wire `--verbose`
   / `--quiet` flags through it.
7. **Optional `--watch` flag** on `md2docx` / `md2pptx` / `md2pdf`
   that rebuilds on file save (stdlib polling).

### P2 — backlog (v2.2 +)

1. Plugin system for custom phases / filters.
2. Cloud-free batch workflows (`md2star batch *.md --to pdf`).
3. Replace the deraison.ai template with a maintained Word-authored
   one in `md2star/data/template.docx`; document its provenance.
4. Zotero integration — bib-in-repo workflow with a `--zotero`
   flag.
5. `mypy --strict` over `md2star/` (incremental adoption).
