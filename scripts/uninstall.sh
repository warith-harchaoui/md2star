#!/usr/bin/env bash
set -euo pipefail

# md2star Uninstaller (macOS & Linux)
#
# This script safely removes all md2star components from your system:
# 1. Custom Lua filters (md2star.lua)
# 2. YAML default configurations (docx-star.yaml, pptx-star.yaml)
# 3. Curated templates and metadata
# 4. GUp utility and assets
# 5. CLI wrappers (md2docx, md2pptx, gup)

PANDOC_DIR="${HOME}/.pandoc"
BIN_DIR="${HOME}/.local/bin"

rm -f "${PANDOC_DIR}/filters/md2star.lua"
rm -f "${PANDOC_DIR}/metadata.yaml"
rm -f "${PANDOC_DIR}/defaults/docx-star.yaml"
rm -f "${PANDOC_DIR}/defaults/pptx-star.yaml"
rm -f "${PANDOC_DIR}/template.docx"
rm -f "${PANDOC_DIR}/template.pptx"
rm -rf "${PANDOC_DIR}/gup"
rm -rf "${PANDOC_DIR}/assets"

# Remove CLI wrappers
rm -f "${BIN_DIR}/md2docx"
rm -f "${BIN_DIR}/md2pptx"
rm -f "${BIN_DIR}/gup"

echo "🗑️  md2docx, md2pptx & gup uninstalled successfully."
