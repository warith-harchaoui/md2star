# scripts/

Thin shell wrappers around `pipx` for installing and uninstalling md2star,
plus the integration test runner and the Python developer tools.

| File | Description |
|------|-------------|
| `install.sh` | macOS / Linux installer. Verifies pandoc + bootstraps pipx + runs `pipx install .` on the local checkout. |
| `install.ps1` | Windows (PowerShell) equivalent of `install.sh`. |
| `uninstall.sh` | macOS / Linux uninstaller. Prompts `[y/N]`, runs `pipx uninstall md2star`, optionally clears the XDG cache, and cleans up legacy `~/.pandoc/` artifacts from pre-1.0 installs. |
| `uninstall.ps1` | Windows equivalent. |
| `update.ps1` | Windows: `git pull` + `pipx install --force .`. |
| `test.sh` | Integration suite — exercises `md2docx` / `md2pptx` against `assets/docx/*.md` and `assets/pptx/*.md`, inspects the OOXML for expected content. |

## Developer tools (Python)

Not part of an install — these are run from a checkout, and the first three
gate the build.

| File | Description |
|------|-------------|
| `audit_comments.py` | Comment-density auditor (house rule 4): fails below the 15 % floor, reports against the 25 % target. |
| `check_triggers.py` | Verifies the skill's trigger catalogue stays in sync with the CLI surface. |
| `compile_catalogs.py` | Compiles `md2star/data/locales/<lang>/*.po` into the `.mo` files `md2star.i18n` loads. |
| `positioning.py` | Regenerates `LANDSCAPE.md`'s positioning map from `assets/landscape.csv`. |
| `bench_vlm_judge.py` | Benches the eyeball loop's vision judge — strict-JSON vs. lenient parsing, on a corpus whose ground truth `pptx_audit` confirms. Needs Ollama + LibreOffice + a designer template; see `docs/design/pptx-template-intelligence.md` §10.7. |

## Quick reference

```bash
make install            # pipx install . (from this checkout)
make uninstall          # pipx uninstall md2star (prompts y/N)
make test               # integration suite (needs pandoc + installed CLI)
make dev                # local .venv for hacking on the code
```

The Python source lives in `md2star/` (one importable package). The
console scripts (`md2docx`, `md2pptx`, `md2star`) are registered via
`pyproject.toml` `[project.scripts]` and implemented in `md2star/cli.py` —
not heredoc'd into these install scripts.
