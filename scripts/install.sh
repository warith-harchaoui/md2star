#!/usr/bin/env bash
set -euo pipefail

# md2star installer (macOS & Linux).
#
# Conservative by default — explains what's missing and what it WOULD
# do; does not modify the system without explicit consent.
#
# Usage:
#   bash scripts/install.sh                       # check + install md2star via pipx
#   bash scripts/install.sh --check               # check only; print nothing else
#   bash scripts/install.sh --dry-run             # print commands; run nothing
#   bash scripts/install.sh --install-system-deps # also install LibreOffice / pandoc
#   bash scripts/install.sh --install-system-deps --yes   # ... and skip prompts
#   bash scripts/install.sh --local               # install local checkout (dev path)
#   bash scripts/install.sh --force               # pipx --force on re-install
#   bash scripts/install.sh --no-libreoffice      # DEPRECATED — same as default
#                                                 #   (kept for backwards-compat)
#
# Exit codes:
#   0 — md2star installed and reachable (or --check passed)
#   1 — md2star is not / cannot be installed (Python missing, pipx
#       bootstrap failed, etc.)
#   2 — bad CLI usage
#
# After this finishes, the four console scripts (`md2docx`, `md2pptx`,
# `md2pdf`, `md2star`) live on the PATH (pipx-managed; usually under
# ~/.local/bin/).

# ─────────────────────────────────────────────────────────────────────
# CLI parsing
# ─────────────────────────────────────────────────────────────────────

usage() {
    /bin/cat <<EOF
md2star installer (conservative mode)

  bash scripts/install.sh [options]

Default behavior:
  - Check Python / pipx / pandoc / soffice are present.
  - Print a report of what's installed and what's missing.
  - Install md2star itself via pipx.
  - Do NOT install system-level dependencies (Pandoc, LibreOffice)
    unless --install-system-deps is also passed.

Options:
  --check                Only print the report; install nothing.
  --dry-run              Print the commands that would run; run nothing.
  --install-system-deps  Run the package manager (brew / apt / dnf /
                         pacman) to install missing Pandoc / LibreOffice.
                         Prompts before each install unless --yes is set.
  --yes                  Skip interactive confirmations.
  --local                Install the local repo checkout (dev path).
  --force                Pass --force to pipx (reinstall over existing copy).
  --no-libreoffice       Deprecated — same as the default (no longer
                         auto-installs LibreOffice).
  -h, --help             Show this help.

Examples:
  # See what's missing on this machine
  bash scripts/install.sh --check

  # Install everything end-to-end on a fresh machine
  bash scripts/install.sh --install-system-deps --yes

  # Get just md2star (leave Pandoc / LibreOffice to the user)
  bash scripts/install.sh
EOF
}

mode_install_pkg=true          # install md2star via pipx
mode_install_system=false      # apt/brew etc for pandoc + soffice
mode_dry_run=false
mode_assume_yes=false
mode_force=""
mode_check_only=false

for arg in "$@"; do
    case "$arg" in
        --check)               mode_check_only=true; mode_install_pkg=false ;;
        --dry-run)             mode_dry_run=true ;;
        --install-system-deps) mode_install_system=true ;;
        --yes|-y)              mode_assume_yes=true ;;
        --force)               mode_force="--force" ;;
        --no-libreoffice)      ;;  # historical alias; current default
        -h|--help)             usage; exit 0 ;;
        *)                     echo "Unknown flag: $arg" >&2; usage; exit 2 ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────
# Helpers — small, testable, side-effect-free where possible
# ─────────────────────────────────────────────────────────────────────

# say <severity> <message>
#   severity ∈ {ok, info, warn, err}
say() {
    local severity="$1"; shift
    case "$severity" in
        ok)   printf "  \033[32m✓\033[0m  %s\n" "$*" ;;
        info) printf "  \033[36mi\033[0m  %s\n" "$*" ;;
        warn) printf "  \033[33m!\033[0m  %s\n" "$*" ;;
        err)  printf "  \033[31m✗\033[0m  %s\n" "$*" ;;
        *)    printf "     %s\n" "$*" ;;
    esac
}

# run_or_explain <description> <cmd...>
#   In --dry-run mode prints the command; otherwise runs it.
run_or_explain() {
    local desc="$1"; shift
    if [[ "${mode_dry_run}" == "true" ]]; then
        printf "  [dry-run] %s — would run: %q" "${desc}" "$1"
        shift
        for arg in "$@"; do printf " %q" "${arg}"; done
        printf "\n"
    else
        "$@"
    fi
}

# confirm <prompt>
#   Returns 0 (proceed) or 1 (abort). Respects --yes / --dry-run.
confirm() {
    if [[ "${mode_assume_yes}" == "true" || "${mode_dry_run}" == "true" ]]; then
        return 0
    fi
    local response
    read -r -p "  → $1 [y/N] " response
    case "$response" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *)                 return 1 ;;
    esac
}

# detect_package_manager
#   Echo brew / apt-get / dnf / pacman / "" (unknown).
detect_package_manager() {
    if [[ "$(uname)" == "Darwin" ]] && command -v brew  >/dev/null 2>&1; then echo brew    ; return; fi
    if command -v apt-get >/dev/null 2>&1; then                              echo apt-get ; return; fi
    if command -v dnf     >/dev/null 2>&1; then                              echo dnf     ; return; fi
    if command -v pacman  >/dev/null 2>&1; then                              echo pacman  ; return; fi
    echo ""
}

# pm_install_cmd <pkg-manager> <pkg-name>
#   Echo the install command for the given package on the given manager.
pm_install_cmd() {
    local pm="$1"; local pkg="$2"
    case "$pm" in
        brew)    echo "brew install --cask ${pkg}" ;;
        apt-get) echo "sudo apt-get update && sudo apt-get install -y --no-install-recommends ${pkg}" ;;
        dnf)     echo "sudo dnf install -y ${pkg}" ;;
        pacman)  echo "sudo pacman -S --noconfirm ${pkg}" ;;
        *)       echo "" ;;
    esac
}

soffice_present() {
    command -v soffice >/dev/null 2>&1 \
        || command -v libreoffice >/dev/null 2>&1 \
        || [[ -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]]
}

# ─────────────────────────────────────────────────────────────────────
# Report phase — runs always, in every mode
# ─────────────────────────────────────────────────────────────────────

echo ""
echo "md2star installer — environment report"
echo ""

# Python
if command -v python3 >/dev/null 2>&1; then
    py_version="$(python3 --version 2>&1)"
    say ok "Python found: ${py_version}"
else
    say err "Python 3 not found. md2star requires Python ≥ 3.10."
    exit 1
fi

# pipx (we'll bootstrap it later if missing AND not in check-only mode)
if command -v pipx >/dev/null 2>&1; then
    say ok "pipx found: $(command -v pipx)"
    pipx_present=true
else
    say warn "pipx not found (will bootstrap via 'python3 -m pip install --user pipx' if needed)."
    pipx_present=false
fi

# Pandoc — required at runtime
if command -v pandoc >/dev/null 2>&1; then
    say ok "Pandoc found: $(pandoc --version | head -1)"
    pandoc_present=true
else
    say warn "Pandoc NOT found. md2star needs it for every conversion."
    pandoc_present=false
fi

# LibreOffice — optional, needed only for md2pdf
if soffice_present; then
    say ok "LibreOffice found ($(command -v soffice libreoffice 2>/dev/null | head -1 || echo '/Applications/LibreOffice.app')) — md2pdf will work."
    soffice_present_flag=true
else
    say info "LibreOffice not found (optional). md2docx / md2pptx still work; md2pdf does not."
    soffice_present_flag=false
fi

# Node — optional, needed only for mermaid blocks
if command -v node >/dev/null 2>&1; then
    say ok "Node.js found: $(node --version)"
else
    say info "Node.js not found (optional). mermaid diagrams will be kept as code fences."
fi

echo ""

# ─────────────────────────────────────────────────────────────────────
# Decide & execute
# ─────────────────────────────────────────────────────────────────────

if [[ "${mode_check_only}" == "true" ]]; then
    echo "  (--check requested; no changes were made.)"
    echo ""
    exit 0
fi

pm="$(detect_package_manager)"

# System-deps install (Pandoc + LibreOffice). OFF unless --install-system-deps.
if [[ "${mode_install_system}" == "true" ]]; then
    if [[ -z "${pm}" ]]; then
        say err "No supported package manager found (brew / apt-get / dnf / pacman). Install Pandoc / LibreOffice manually."
    else
        echo "Installing missing system dependencies via ${pm}:"
        if [[ "${pandoc_present}" != "true" ]]; then
            cmd="$(pm_install_cmd "${pm}" pandoc)"
            if confirm "Install Pandoc using: ${cmd}"; then
                run_or_explain "install pandoc" bash -lc "${cmd}"
            else
                say warn "Pandoc install skipped."
            fi
        fi
        if [[ "${soffice_present_flag}" != "true" ]]; then
            # Casks / packages differ by manager.
            case "${pm}" in
                brew)    pkg="libreoffice" ;;
                apt-get) pkg="libreoffice" ;;
                dnf)     pkg="libreoffice-headless" ;;
                pacman)  pkg="libreoffice-still" ;;
                *)       pkg="libreoffice" ;;
            esac
            cmd="$(pm_install_cmd "${pm}" "${pkg}")"
            if confirm "Install LibreOffice using: ${cmd}"; then
                run_or_explain "install libreoffice" bash -lc "${cmd}"
            else
                say warn "LibreOffice install skipped."
            fi
        fi
        echo ""
    fi
else
    if [[ "${pandoc_present}" != "true" || "${soffice_present_flag}" != "true" ]]; then
        echo "  Skipping system-dependency install (default)."
        echo "  Re-run with --install-system-deps to install missing items via ${pm:-your package manager}."
        echo ""
    fi
fi

# md2star itself
if [[ "${mode_install_pkg}" == "true" ]]; then
    if [[ "${pipx_present}" != "true" ]]; then
        if confirm "Bootstrap pipx via 'python3 -m pip install --user pipx'?"; then
            run_or_explain "bootstrap pipx" python3 -m pip install --user --quiet pipx
            run_or_explain "ensurepath"     python3 -m pipx ensurepath
            export PATH="${HOME}/.local/bin:${PATH}"
        else
            say err "pipx is required to install md2star. Aborting."
            exit 1
        fi
    fi

    repo_root="$(cd "$(dirname "$0")/.." && pwd)"
    if [[ ! -f "${repo_root}/pyproject.toml" ]]; then
        say err "Cannot find ${repo_root}/pyproject.toml — run install.sh from the repo root."
        exit 1
    fi

    echo "Installing md2star via pipx (source: ${repo_root}):"
    run_or_explain "pipx install md2star" pipx install ${mode_force} "${repo_root}"
    echo ""
fi

if [[ "${mode_dry_run}" == "true" ]]; then
    say info "Dry-run complete — no changes were applied."
else
    /bin/cat <<EOF
md2star ready. Try:

  md2star doctor      # full environment report
  md2docx <input.md>  # markdown → DOCX
  md2pptx <input.md>  # markdown → PPTX
  md2pdf  <input.md>  # markdown → PDF (needs LibreOffice)

If a command is not found, restart your shell so the pipx PATH loads.
EOF
fi
