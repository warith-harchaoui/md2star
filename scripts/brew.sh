#!/usr/bin/env bash
set -euo pipefail

# md2star Homebrew bootstrap (macOS).
#
# One-shot install of md2star and its system tools via Homebrew, then the
# package itself via pipx. Idempotent — every step checks first, so re-running
# is safe and only fills in what is missing. This is the macOS convenience path
# that complements the cross-platform `scripts/install.sh`.
#
# Usage:
#   bash scripts/brew.sh                 # pandoc + pipx + md2star (DOCX/PPTX ready)
#   bash scripts/brew.sh --with-pdf      # also install LibreOffice (md2pdf)
#   bash scripts/brew.sh --with-mermaid  # also install Node.js (```mermaid```)
#   bash scripts/brew.sh --with-ai       # also install Ollama (--lint / alt-text)
#   bash scripts/brew.sh --all           # everything above
#   bash scripts/brew.sh --dry-run       # print the commands; run nothing
#
# Exit codes:
#   0 — md2star installed and reachable
#   1 — Homebrew is missing (install it from https://brew.sh/) or a step failed
#   2 — bad CLI usage
#
# After this finishes, the four console scripts (`md2docx`, `md2pptx`,
# `md2pdf`, `md2star`) live on the PATH (pipx-managed, usually ~/.local/bin/).

# ─────────────────────────────────────────────────────────────────────
WITH_PDF=0
WITH_MERMAID=0
WITH_AI=0
DRY_RUN=0

# Parse flags. `--all` turns on every optional system tool at once; the rest
# are additive so a user can pick exactly what their pipeline needs.
while [ "$#" -gt 0 ]; do
    case "$1" in
        --with-pdf) WITH_PDF=1 ;;
        --with-mermaid) WITH_MERMAID=1 ;;
        --with-ai) WITH_AI=1 ;;
        --all) WITH_PDF=1; WITH_MERMAID=1; WITH_AI=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) sed -n '3,26p' "$0"; exit 0 ;;
        *) echo "brew.sh: unknown argument '$1'" >&2; exit 2 ;;
    esac
    shift
done

# `run` is the single choke point for side effects: in --dry-run we only print,
# otherwise we execute. Keeping every mutating command behind it makes the
# dry-run guarantee auditable at a glance.
run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "+ $*"
    else
        echo "+ $*"
        "$@"
    fi
}

# Homebrew is the hard prerequisite for this script; bail early with the
# canonical install pointer rather than emitting a confusing later failure.
if ! command -v brew >/dev/null 2>&1; then
    echo "brew.sh: Homebrew not found. Install it from https://brew.sh/ then re-run." >&2
    exit 1
fi

# `brew_install <formula>` is idempotent: skip when the formula is already
# present so re-runs are fast and never error on "already installed".
brew_install() {
    if brew list --formula "$1" >/dev/null 2>&1; then
        echo "= $1 already installed"
    else
        run brew install "$1"
    fi
}

# `brew_cask <cask>` mirrors brew_install for GUI apps (LibreOffice ships as a
# cask, not a formula).
brew_cask() {
    if brew list --cask "$1" >/dev/null 2>&1; then
        echo "= $1 (cask) already installed"
    else
        run brew install --cask "$1"
    fi
}

# Core: pandoc drives every conversion; pipx isolates md2star in its own venv
# and puts the four console scripts on PATH.
brew_install pandoc
brew_install pipx
run pipx ensurepath

# Optional system tools, gated by the flags above. Each is only needed for one
# feature, so we keep them off by default to stay minimal.
[ "$WITH_PDF" -eq 1 ] && brew_cask libreoffice       # md2pdf (DOCX → PDF via soffice)
[ "$WITH_MERMAID" -eq 1 ] && brew_install node       # ```mermaid``` diagram rendering
[ "$WITH_AI" -eq 1 ] && brew_install ollama          # --lint + AI alt-text

# Install (or upgrade) md2star itself. `pipx install` is idempotent; we add
# `--force` only implicitly via re-run semantics — a plain re-run reports it is
# already installed rather than erroring.
if pipx list 2>/dev/null | grep -q "package md2star "; then
    echo "= md2star already installed via pipx (run 'pipx upgrade md2star' to update)"
else
    run pipx install md2star
fi

# Confirm the install landed. `md2star doctor` is the authoritative check — it
# reports Python/pandoc/LibreOffice/Node/Ollama status in one shot.
if [ "$DRY_RUN" -eq 0 ]; then
    echo
    echo "md2star installed. Verifying environment:"
    md2star doctor || true
fi
