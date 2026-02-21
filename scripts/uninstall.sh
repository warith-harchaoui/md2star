#!/usr/bin/env bash
set -euo pipefail

# md2star uninstaller (macOS + Linux)
#
# Removes:
#   ~/.pandoc/filters/strip-header-ids.lua
#   ~/.pandoc/defaults/docx-star.yaml
#   ~/.pandoc/template.docx
#   ~/.local/bin/md2star

PANDOC_DIR="${HOME}/.pandoc"
BIN_DIR="${HOME}/.local/bin"

rm -f "${PANDOC_DIR}/filters/strip-header-ids.lua"
rm -f "${PANDOC_DIR}/defaults/docx-star.yaml"
rm -f "${PANDOC_DIR}/template.docx"
rm -f "${BIN_DIR}/md2star"

echo "🗑️  md2star uninstalled."
