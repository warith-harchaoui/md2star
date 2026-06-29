#!/usr/bin/env bash
set -euo pipefail

# md2star uninstaller (macOS & Linux).
#
# Removes the pipx-managed md2star install. Asks for confirmation by default
# so a stray invocation can't silently wipe an unrelated install — pass
# --yes to skip the prompt (use this in CI).
#
# Also offers to clear the on-disk cache (XDG_CACHE_HOME/md2star/) where
# downscaled images, downloaded remote images, and mermaid renders live.

assume_yes=false
clear_cache=false
for arg in "$@"; do
    case "$arg" in
        -y|--yes) assume_yes=true ;;
        --clear-cache) clear_cache=true ;;
        -h|--help)
            cat <<EOF
md2star uninstaller

  bash scripts/uninstall.sh [--yes] [--clear-cache]

Options:
  -y, --yes        do not prompt for confirmation.
  --clear-cache    also remove the XDG cache (downscaled images, mermaid PNGs).
EOF
            exit 0 ;;
        *) echo "Unknown flag: $arg" >&2; exit 2 ;;
    esac
done

# Detect what would actually be removed so the user sees a real preview.
if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "package md2star"; then
    target="pipx package 'md2star' and its console scripts (md2docx, md2pptx, md2star)"
else
    target="(nothing — md2star is not installed via pipx)"
fi

echo "md2star uninstall will remove:"
echo "  - ${target}"
if [[ "$clear_cache" == true ]]; then
    echo "  - the on-disk cache directory (\$XDG_CACHE_HOME/md2star/)"
fi

if [[ "$assume_yes" != true ]]; then
    read -r -p "Proceed? [y/N] " response
    case "$response" in
        [yY]|[yY][eE][sS]) ;;
        *) echo "Aborted."; exit 0 ;;
    esac
fi

if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q "package md2star"; then
    pipx uninstall md2star
fi

if [[ "$clear_cache" == true ]] && command -v md2star >/dev/null 2>&1; then
    md2star clear-cache || true
fi

# Best-effort legacy cleanup for users coming from the old shell-installer
# scheme (~/.pandoc + ~/.local/bin wrappers). Silent if the files aren't there.
legacy_files=(
    "${HOME}/.local/bin/md2docx"
    "${HOME}/.local/bin/md2pptx"
    "${HOME}/.pandoc/preprocessing.py"
    "${HOME}/.pandoc/postprocess_docx.py"
    "${HOME}/.pandoc/preprocessing_lib"
    "${HOME}/.pandoc/filters/md2star.lua"
    "${HOME}/.pandoc/defaults/docx-star.yaml"
    "${HOME}/.pandoc/defaults/pptx-star.yaml"
    "${HOME}/.pandoc/metadata.yaml"
    "${HOME}/.pandoc/mermaid-config.json"
    "${HOME}/.pandoc/template.docx"
    "${HOME}/.pandoc/template.pptx"
    "${HOME}/.pandoc/venv"
)
for path in "${legacy_files[@]}"; do
    [[ -e "$path" ]] && rm -rf "$path"
done

echo "md2star uninstalled."
