# Installing md2star

This page is the single source of truth for getting md2star running.
The matrix below tells you which dependencies you actually need for
each feature, and the per-OS sections give the exact commands.

## Quick start

If you have **Python ≥ 3.10** and **Pandoc** already installed:

```bash
pipx install md2star                # pulls the package from PyPI
md2star doctor                      # prints a report; should show all green
md2docx README.md                   # smoke test → produces README.docx
```

That gets you `md2docx`, `md2pptx`, `md2pdf`, and `md2star` on your
PATH, plus the click front-end `md2star-x` (`click` is a core
dependency). If you cloned the repository instead, `bash
scripts/install.sh` runs the same check and then `pipx install .`
from the local copy (**conservative by default** — it does not
auto-install Pandoc / LibreOffice; pass `--install-system-deps` to
have it run the platform's package manager).

### Optional install profiles

The core wheel already ships the four CLIs, the `md2star-x` click
front-end, and the bundled `md2star gui`. A few opt-in extras layer on
Python packages for other surfaces:

| Extra | Command | What it adds |
|-------|---------|--------------|
| `api` | `pip install 'md2star[api]'` | FastAPI HTTP server (`md2star-api`). |
| `mcp` | `pip install 'md2star[mcp]'` | FastAPI-MCP server (`md2star-mcp`). |
| `ai`  | `pip install 'md2star[ai]'`  | Official `ollama` client for the opt-in `--lint` / alt-text passes (they otherwise work via a zero-dependency `urllib` fallback). |
| `gui` | `pip install 'md2star[gui]'` | Self-documenting alias — resolves to the **same** wheel as plain `md2star`; the GUI is already bundled and adds no Python packages. |

md2star also packages itself as a **Claude Skill / OpenCode skill**
under `skills/md2star/` so an agent can drive it — see
[`skills/README.md`](../skills/README.md) for the copy-into-place
install.

## Installation matrix

Pick the features you actually need; install only those dependencies.
`md2star doctor` will tell you what's working at any point.

| Feature                | Requires                                           | Notes                                                              |
|------------------------|----------------------------------------------------|--------------------------------------------------------------------|
| `md2docx` (DOCX)        | + Pandoc                                          | Pandoc does all the heavy lifting; md2star adds the polish.        |
| `md2pptx` (PPTX)        | + Pandoc                                          | Same as DOCX.                                                      |
| `md2pdf`  (PDF)         | + Pandoc + LibreOffice (`soffice`)                | PDF goes through DOCX → soffice headless conversion.               |
| Mermaid diagrams        | + Node.js ≥ 16 (provides `npx`)                   | `npx -y @mermaid-js/mermaid-cli` downloaded on first use.          |
| `--lint` LLM auto-fix   | + Ollama + a small Gemma model                    | Off by default; opt-in via the `--lint` flag.                      |
| AI-drafted alt text     | + Ollama + a vision model (default: gemma4:e2b)   | Same `--lint` flag; `MD2STAR_ALT_TEXT_MODEL` overrides the model.  |
| `md2star gui` (editor)  | nothing extra                                     | Offline localhost-only web editor, bundled in core since v2.6.0.   |

**Network policy:** since v2.5.0 the deraison.ai reference template is
fetched **by default** when no local `template.{docx,pptx}` exists
(cached under XDG, bundled fallback on failure); opt out with
`--no-remote-templates`. Remote image downloads still require the
explicit `--allow-remote-images` flag. Pass `--offline` as the hard
kill-switch that forbids every network touch.

## Per-OS installation

- macOS 🍎 : `brew install pandoc pipx`
  (install `brew` thanks to [brew.sh](https://brew.sh/))

  ```bash
  pipx ensurepath
  pipx install md2star

  # Optional: PDF output
  brew install --cask libreoffice
  # Optional: Mermaid diagrams
  brew install node
  # Optional: --lint and AI alt-text
  brew install ollama
  ```

  Or run the one-shot idempotent Homebrew bootstrap, which installs
  pandoc + pipx + md2star and (with flags) the optional system tools:

  ```bash
  bash scripts/brew.sh                 # core: pandoc + pipx + md2star
  bash scripts/brew.sh --with-pdf      # + LibreOffice (md2pdf)
  bash scripts/brew.sh --with-mermaid  # + Node.js (mermaid)
  bash scripts/brew.sh --with-ai       # + Ollama (--lint / alt-text)
  bash scripts/brew.sh --all           # everything above
  bash scripts/brew.sh --dry-run       # print the commands, run nothing
  ```

- Ubuntu 🐧 : `sudo apt-get install -y pandoc pipx`

  ```bash
  pipx ensurepath
  pipx install md2star

  # Optional dependencies
  sudo apt-get install -y --no-install-recommends libreoffice nodejs
  curl -fsSL https://ollama.com/install.sh | sh   # ollama
  ```

- Fedora / RHEL 🐧 : `sudo dnf install -y pandoc pipx`

  ```bash
  pipx ensurepath
  pipx install md2star

  sudo dnf install -y libreoffice-headless nodejs
  curl -fsSL https://ollama.com/install.sh | sh   # ollama
  ```

- Arch / Manjaro 🐧 : `sudo pacman -S --noconfirm pandoc python-pipx`

  ```bash
  pipx ensurepath
  pipx install md2star

  sudo pacman -S --noconfirm libreoffice-still nodejs ollama
  ```

- Windows 🪟 : `winget install --id JohnMacFarlane.Pandoc`

  ```powershell
  python -m pip install --user pipx
  python -m pipx ensurepath
  pipx install md2star

  # Optional dependencies
  winget install --id TheDocumentFoundation.LibreOffice
  winget install --id OpenJS.NodeJS
  winget install --id Ollama.Ollama
  ```

### From a clone (development path)

```bash
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star
bash scripts/install.sh           # macOS / Linux
powershell -ExecutionPolicy Bypass -File scripts\install.ps1   # Windows
```

## Verification

After installation, run:

```bash
md2star doctor          # full environment report
md2star --help          # subcommand list
md2star gui             # launch the offline localhost web editor (Ctrl-C to stop)
md2docx --help          # per-format flags
md2star-x doctor        # same diagnostic via the click front-end
```

The single-file, zero-dependency **minimal GUI** — a hackable stdlib
preview server that exposes `md → PDF` on one endpoint — runs straight
from the repo without installing anything extra:

```bash
python3 minimal-gui/server.py   # then open the printed http://127.0.0.1 URL
```

A healthy install shows `OK` on every Core row and ends with:

```
Result:
  DOCX export        OK
  PPTX export        OK
  PDF export         OK         (PARTIAL if soffice missing)
  Mermaid diagrams   OK         (UNAVAILABLE if Node missing)
```

To do an actual conversion smoke-test:

```bash
md2docx assets/example.md           # → assets/example.docx
md2pdf  assets/example.md           # → assets/example.pdf (needs LibreOffice)
```

## Troubleshooting

| Symptom                                                  | Likely cause                                         | Fix                                                                                       |
|----------------------------------------------------------|------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `md2docx: command not found`                             | `~/.local/bin` (pipx PATH) not on `$PATH`            | Restart your shell; `pipx ensurepath` updates rc files but the running shell is unaware.  |
| `pandoc: command not found`                              | Pandoc not installed                                 | Per-OS install instructions above; rerun `md2star doctor` to confirm.                     |
| `md2pdf: LibreOffice not found`                          | `soffice` not on PATH                                | Install LibreOffice per-OS above. The `md2pdf` path requires it.                          |
| `md2pdf` table cells render empty in the PDF             | Known issue — soffice ↔ bundled template interaction | See `CHANGELOG.md` v1.1.1. Workaround: export the `.docx`, open in Word.                  |
| Mermaid block stays as code, no image                    | Node.js not on PATH, or `npx` fetch failed           | Install Node.js per-OS above. The first run downloads `@mermaid-js/mermaid-cli` via npx.  |
| `md2docx … --bib refs.bib` produces no bibliography      | Pandoc citeproc not enabled in your build            | Check `pandoc --version` lists `+citeproc`; install a newer Pandoc if not.                |
| `md2star: skipped remote image https://…`                | Default offline mode blocks remote images            | Pass `--allow-remote-images` to opt in, or download the image locally.                    |
| `md2star: --lint requested but Ollama not installed`     | `--lint` needs a local Ollama daemon                 | Install [Ollama](https://ollama.com/); md2star pulls the model on first run.              |
| Pipx warning about Python version on macOS               | Homebrew Python upgraded; pipx points at the old one | `pipx reinstall md2star --python "$(which python3)"`.                                     |

## Updating

```bash
# Any OS, PyPI install
pipx upgrade md2star

# macOS / Linux from a clone
cd md2star && git pull && make update

# Windows from a clone
cd md2star ; git pull ; powershell -ExecutionPolicy Bypass -File scripts\update.ps1
```

## Uninstalling

```bash
pipx uninstall md2star                       # PyPI install
bash scripts/uninstall.sh                    # cloned install (prompts before removal)
bash scripts/uninstall.sh --yes              # silent
bash scripts/uninstall.sh --clear-cache      # also wipe $XDG_CACHE_HOME/md2star/
```

This removes the pipx-managed `md2star` package and all its console
scripts (`md2docx`, `md2pptx`, `md2pdf`, `md2star`, `md2star-x`, and —
when the `api`/`mcp` extras are installed — `md2star-api` /
`md2star-mcp`). It does NOT uninstall Pandoc / LibreOffice / Node /
Ollama — those are system-wide and the user may want to keep them.
