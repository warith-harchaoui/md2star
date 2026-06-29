# scripts/

Thin shell wrappers around `pipx` for installing and uninstalling md2star,
plus the integration test runner.

| File | Description |
|------|-------------|
| `install.sh` | macOS / Linux installer. Verifies pandoc + bootstraps pipx + runs `pipx install .` on the local checkout. |
| `install.ps1` | Windows (PowerShell) equivalent of `install.sh`. |
| `uninstall.sh` | macOS / Linux uninstaller. Prompts `[y/N]`, runs `pipx uninstall md2star`, optionally clears the XDG cache, and cleans up legacy `~/.pandoc/` artifacts from pre-1.0 installs. |
| `uninstall.ps1` | Windows equivalent. |
| `update.ps1` | Windows: `git pull` + `pipx install --force .`. |
| `test.sh` | Integration suite — exercises `md2docx` / `md2pptx` against `assets/docx/*.md` and `assets/pptx/*.md`, inspects the OOXML for expected content. |

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
