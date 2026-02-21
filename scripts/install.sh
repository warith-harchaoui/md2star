#!/usr/bin/env bash
set -euo pipefail

# md2star installer (macOS + Linux)
#
# What it installs into your Pandoc user directory:
#   ~/.pandoc/filters/strip-header-ids.lua
#   ~/.pandoc/defaults/docx-star.yaml
#   ~/.pandoc/template.docx
#
# And a small helper command into:
#   ~/.local/bin/md2star
#
# Requirements:
#   - pandoc must be installed and available in PATH
#
# Notes:
#   - The helper command uses the defaults file, which in turn uses template.docx.
#   - If you customize assets/template.docx in this repo, re-run this installer.

PANDOC_DIR="${HOME}/.pandoc"
FILTERS_DIR="${PANDOC_DIR}/filters"
DEFAULTS_DIR="${PANDOC_DIR}/defaults"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${FILTERS_DIR}" "${DEFAULTS_DIR}" "${BIN_DIR}"

# Copy filter + defaults + template
cp -f "pandoc/filters/strip-header-ids.lua" "${FILTERS_DIR}/strip-header-ids.lua"
cp -f "pandoc/defaults/docx-star.yaml" "${DEFAULTS_DIR}/docx-star.yaml"
cp -f "assets/template.docx" "${PANDOC_DIR}/template.docx"

# Wrapper command (uses defaults + template automatically)
cat > "${BIN_DIR}/md2star" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# md2star: Markdown -> DOCX with:
#  - heading IDs stripped (no Google Docs bookmark markers)
#  - a shared DOCX style template
#
# Usage:
#   md2star input.md [extra pandoc args...]
#
# Output:
#   input.docx (same directory as input)

if [[ $# -lt 1 ]]; then
  echo "Usage: md2star <input.md> [extra pandoc args...]"
  echo "Output: <input>.docx"
  exit 1
fi

IN="$1"
shift || true
OUT="${IN%.*}.docx"

pandoc --defaults docx-star.yaml "$IN" -o "$OUT" "$@"
echo "Wrote: $OUT"
SH

chmod +x "${BIN_DIR}/md2star"

echo ""
echo "✅ md2star installed."
echo "  Filter:   ${FILTERS_DIR}/strip-header-ids.lua"
echo "  Defaults: ${DEFAULTS_DIR}/docx-star.yaml"
echo "  Template: ${PANDOC_DIR}/template.docx"
echo "  Command:  ${BIN_DIR}/md2star"
echo ""
echo "Next step: ensure ${BIN_DIR} is on your PATH."
echo "For zsh (macOS default):"
echo '  echo '''export PATH="$HOME/.local/bin:$PATH"''' >> ~/.zshrc && source ~/.zshrc'
echo ""
echo "Try:"
echo "  md2star notes.md"
