# md2star — roadmap

Where the project is going, in priority order. Each item lists a
target release and a one-line rationale. See `docs/audit.md` for the
detailed audit these priorities came from.

## P0 — shipped (v2.0.0, PyPI debut)

- [x] **License → BSD 3-Clause** to match scikit-learn and the
      broader scientific-Python conventions.
- [x] **GUI removed** so the wheel stays lean (~200 KB instead of
      ~3.3 MB) for the PyPI debut. The CLI is the complete v2.0
      product; the GUI lives in git history (last commit before
      removal) and is slated to come back as the `md2star[gui]`
      extra in v2.1 (see P1).
- [x] **Honest audit** (`docs/audit.md`) — engineering forces / risks /
      priorities, each pinned to a file.
- [x] **`md2star doctor`** — environment diagnostic; exit non-zero only
      when Core deps (Python / md2star / Pandoc) are broken.
- [x] **Offline by default + opt-in remote flags** —
      `--offline`, `--allow-remote-templates`, `--allow-remote-images`.
      Typed exceptions in `md2star/errors.py`.
- [x] **Conservative installer** — `--check`, `--dry-run`, `--yes`,
      `--install-system-deps`. Default behavior reports state only.
- [x] **CI** — lint (ruff) + cli-smoke + build matrix alongside the
      existing pytest + integration + shellcheck jobs.
- [x] **`docs/installation.md` + README + LISEZMOI + SECURITY +
      CONTRIBUTING refresh** for the PyPI cut.
- [x] **Coding-style enforcement** — NumPy docstrings, module
      headers with author link, full type annotations.

## P1 — shipped

- [x] **`md2star templates {list,path}`** (v2.1.0) — shows every
      resolution candidate (per-project / cached / bundled) and
      prints the absolute path of the active template for a given
      format. `md2star templates --help`.
- [x] **Typed exceptions wired into `cli.main`** (v2.1.0) — the
      top-level `handle_known_error` / `_render_error` handler
      pretty-prints any `Md2starError` as a headline plus an
      indented `hint` line and exits on a per-subclass exit-code
      map (e.g. `MissingDependencyError` → 127). Unknown exceptions
      still surface a real traceback so genuine bugs get filed. See
      `md2star/errors.py`.
- [x] **Structured stdlib `logging` in the CLI core** (v2.4.0) — a
      single named logger + stderr `StreamHandler` (`md2star/logging.py`,
      `configure()`) replaces the ad-hoc `print(..., file=sys.stderr)`
      calls, with `--verbose` / `--quiet` wired through it. Stdlib
      only, no new runtime deps. Note: `--verbose` / `--quiet`
      shipped; a granular `--log-level` flag did **not** and is
      not currently planned.

## P1 — next release (v2.1)

- [x] **Local GUI restored — `md2star gui`** (v2.6.0). The
      Overleaf-style web editor is back with live PDF preview
      (PDF.js), a root-confined folder browser, in-session template
      upload, and draft auto-save. Shipped **bundled in the core
      package** (Option A) rather than as a separate `md2star[gui]`
      wheel (Option B): the ~4 MB vendor tree (Tailwind, CodeMirror,
      PDF.js, Montserrat + Roboto Serif) lives under
      `md2star/data/gui/` and the whole thing is pure stdlib
      `http.server` — zero extra Python deps. This trades the lean
      ~200 KB wheel (now ~2.3 MB) for a one-command GUI that needs no
      extra install; splitting it back into an opt-in wheel (Option B,
      to reclaim the small core) stays available as a later
      optimization. Path confinement covered by
      `tests/test_gui_security.py`.
- [ ] **`md2star[ai]` PyPI extra.** Today the `--lint` /
      AI-alt-text passes shell out to the local `ollama` binary
      via stdlib `urllib.request` — zero Python deps. The
      `[ai]` extra would pull the `ollama` Python client
      (https://pypi.org/project/ollama/) and let us swap the
      hand-rolled HTTP calls for a typed client (modest code
      cleanup, future-proof if AI deps grow heavier). Symmetric
      with the `[gui]` extra.
- [ ] **User config file** — `$XDG_CONFIG_HOME/md2star/config.toml`
      via `platformdirs`. Precedence: CLI > config > defaults.
      `md2star config {path,show,init}`.
- [ ] **Optional `--watch` flag** on `md2docx` / `md2pptx` /
      `md2pdf` that rebuilds on file save (stdlib polling).
      Terminal alternative to the editor-loop iteration mode the
      GUI used to provide.

## P2 — backlog (v2.2 +)

- [ ] **`md2star convert <file> --to <fmt>`** as a unified entrypoint
      alongside the existing `md2docx` / `md2pptx` / `md2pdf` binaries.
- [ ] **Template rebuild** — replace `md2star/data/template.docx` with
      a hand-authored Word doc free of the `TableNormal0` style that
      breaks soffice table rendering. See `CHANGELOG.md` v1.1.1
      "Known issues".
- [ ] **Reusable GitHub Actions workflow** for rendering markdown to
      DOCX/PPTX/PDF on push. Lets phone-only contributors push edits
      and get rendered artifacts attached to the workflow run.
- [ ] **Zotero integration** — bib-in-repo workflow with a `--zotero
      {repo,local,bbt-api}` flag; cross-device by construction
      (no extra sync infra).
- [ ] **Git awareness inside the `[gui]` extra** — read-only sidebar
      with branch + uncommitted-changes count, then opt-in
      commit-on-save, then opt-in push-on-save. Designed as a
      three-phase rollout (read-only → commit-on-save → push-on-save)
      so the failure modes can be isolated per phase.

## P3 — exploratory

- [ ] **`mypy --strict` over `md2star/`**, incremental adoption.
- [ ] **Plugin system** for custom preprocessor phases / Lua filters
      / Office postprocessors. Public API surface; semantic-version
      guarantees.
- [ ] **Batch processing** — `md2star batch *.md --to pdf` with
      parallel rendering and a progress bar.
- [ ] **Community vs Premium edition split** — managed render
      endpoint at `render.md2star.app`, billing via Stripe, team
      governance features. **Not committed**; only if there's
      measurable demand AND the author wants to operate a SaaS.

## Non-goals

A roadmap is also about what we are NOT going to do. md2star will
NOT:

- Become a markdown-to-HTML website generator. Use Hugo / Astro /
  the `front-publish` Claude skill instead.
- Try to be Word / Pages / Keynote. The goal is "write markdown,
  get a polished Office doc"; if you want WYSIWYG editing, that's
  not us.
- Add proprietary file formats. We stay in markdown in / OOXML out.
- Accept telemetry. Ever.
- Implement DRM, watermarking, or any other "control what the user
  does after export" feature.
