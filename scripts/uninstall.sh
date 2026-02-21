#!/usr/bin/env bash
set -euo pipefail

# md2star uninstaller (macOS + Linux)
#
# Removes:
#   ~/.pandoc/filters/strip-header-ids.lua
#   ~/.pandoc/defaults/docx-star.yaml
#   ~/.pandoc/template.pptx
#   ~/.local/bin/md2docx
#   ~/.local/bin/md2pptx

PANDOC_DIR="${HOME}/.pandoc"
BIN_DIR="${HOME}/.local/bin"

rm -f "${PANDOC_DIR}/filters/md2star.lua"
rm -f "${PANDOC_DIR}/metadata.yaml"
rm -f "${PANDOC_DIR}/defaults/docx-star.yaml"
rm -f "${PANDOC_DIR}/defaults/pptx-star.yaml"
rm -f "${PANDOC_DIR}/template.docx"
rm -f "${PANDOC_DIR}/template.pptx"
rm -f "${BIN_DIR}/md2docx"
rm -f "${BIN_DIR}/md2pptx"

echo "🗑️  md2docx & md2pptx uninstalled."
