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
      headers with author link, full type annotations,
      `os-helper`-based logging (`osh.info` / `osh.warning` /
      `osh.error` / `osh.debug`) instead of bare `print()`.

## P1 — next release (v2.1)

- [ ] **`md2star[gui]` PyPI extra.** Bring the Overleaf-style local
      web editor back, this time as an opt-in extra so the core
      wheel stays small. `pipx install 'md2star[gui]'` pulls the
      ~3 MB vendor tree (Tailwind, CodeMirror, PDF.js, Roboto
      Serif) and registers the `md2star gui` subcommand. The
      historical code lives in git — restore + adapt rather than
      rewrite.
- [ ] **`md2star[ai]` PyPI extra.** Today the `--lint` /
      AI-alt-text passes shell out to the local `ollama` binary
      via stdlib `urllib.request` — zero Python deps. The
      `[ai]` extra would pull the `ollama` Python client
      (https://pypi.org/project/ollama/) and let us swap the
      hand-rolled HTTP calls for a typed client (modest code
      cleanup, future-proof if AI deps grow heavier). Symmetric
      with the `[gui]` extra.
- [ ] **`md2star templates {list,path}`** — show bundled / user
      templates and the resolution path.
- [ ] **User config file** — `$XDG_CONFIG_HOME/md2star/config.toml`
      via `platformdirs`. Precedence: CLI > config > defaults.
      `md2star config {path,show,init}`.
- [ ] **Typed exceptions wired into `cli.main`** — pretty-print at
      the top with a `hint` line and an exit-code map. No raw
      tracebacks for known failures.
- [ ] **Structured `logging` via os-helper.** Replace remaining
      direct `print(..., file=sys.stderr)` calls in the CLI core
      with `osh.info` / `osh.warning` / `osh.error` / `osh.debug`,
      with `--verbose` / `--quiet` toggles wired through
      `osh.verbosity()`.
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
      (no extra sync infra). Detailed design in `.private/todo.md`.
- [ ] **Git awareness inside the `[gui]` extra** — read-only sidebar
      with branch + uncommitted-changes count, then opt-in
      commit-on-save, then opt-in push-on-save. Three-phase
      rollout designed in `.private/GIT.md`.

## P3 — exploratory

- [ ] **`mypy --strict` over `md2star/`**, incremental adoption.
- [ ] **Plugin system** for custom preprocessor phases / Lua filters
      / Office postprocessors. Public API surface; semantic-version
      guarantees.
- [ ] **Batch processing** — `md2star batch *.md --to pdf` with
      parallel rendering and a progress bar.
- [ ] **Community vs Premium edition split** — managed render
      endpoint at `render.md2star.app`, billing via Stripe, team
      governance features. Detailed business-model study in
      `.private/GIT.md`. **Not committed**; only if there's
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
