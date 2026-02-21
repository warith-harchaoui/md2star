#!/usr/bin/env bash
set -euo pipefail

# md2star installer (macOS + Linux)
#
# What it installs into your Pandoc user directory:
#   ~/.pandoc/filters/strip-header-ids.lua
#   ~/.pandoc/defaults/docx-star.yaml
#   ~/.pandoc/template.docx
#
# And helper commands into:
#   ~/.local/bin/md2docx
#   ~/.local/bin/md2pptx
#
# Requirements:
#   - pandoc must be installed and available in PATH
#
# Notes:
#   - The helper commands use defaults files which in turn use templates.
#   - If you customize templates in assets/, re-run this installer.

PANDOC_DIR="${HOME}/.pandoc"
FILTERS_DIR="${PANDOC_DIR}/filters"
DEFAULTS_DIR="${PANDOC_DIR}/defaults"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "${FILTERS_DIR}" "${DEFAULTS_DIR}" "${BIN_DIR}"

# Copy filter + defaults + templates + metadata
cp -f "pandoc/filters/md2star.lua" "${FILTERS_DIR}/md2star.lua"
cp -f "pandoc/metadata.yaml" "${PANDOC_DIR}/metadata.yaml"
cp -f "assets/template.docx" "${PANDOC_DIR}/template.docx"
cp -f "assets/template.pptx" "${PANDOC_DIR}/template.pptx"

# Inject absolute paths into defaults files during installation
sed -e "s|md2star.lua|${FILTERS_DIR}/md2star.lua|g" \
    -e "s|metadata.yaml|${PANDOC_DIR}/metadata.yaml|g" \
    -e "s|reference-doc: template.docx|reference-doc: ${PANDOC_DIR}/template.docx|g" \
    "pandoc/defaults/docx-star.yaml" > "${DEFAULTS_DIR}/docx-star.yaml"

sed -e "s|md2star.lua|${FILTERS_DIR}/md2star.lua|g" \
    -e "s|metadata.yaml|${PANDOC_DIR}/metadata.yaml|g" \
    -e "s|reference-doc: template.pptx|reference-doc: ${PANDOC_DIR}/template.pptx|g" \
    "pandoc/defaults/pptx-star.yaml" > "${DEFAULTS_DIR}/pptx-star.yaml"

# Wrapper command for DOCX
cat > "${BIN_DIR}/md2docx" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# md2docx: Markdown -> DOCX -> PDF with title/author/bib/lang extraction
# Usage:
#   md2docx input.md [--author "Name"] [--bib "ref.bib"] [--lang "en-US"] [extra pandoc args...]

if [[ $# -lt 1 ]]; then
  echo "Usage: md2docx <input.md> [--author \"Name\"] [--bib \"ref.bib\"] [--lang \"en-US\"] [extra pandoc args...]"
  exit 1
fi

IN="$1"
shift || true

EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --author)
      EXTRA_ARGS+=("--metadata" "author=$2")
      shift 2
      ;;
    --bib)
      EXTRA_ARGS+=("--citeproc" "--bibliography" "$2")
      shift 2
      ;;
    --lang)
      EXTRA_ARGS+=("--metadata" "lang=$2")
      shift 2
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

OUT_DOCX="${IN%.*}.docx"
OUT_PDF="${IN%.*}.pdf"

# 1. Convert Markdown to DOCX
pandoc --defaults docx-star.yaml "$IN" -o "$OUT_DOCX" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
echo "Wrote: $OUT_DOCX"

# 2. Convert DOCX to PDF
pandoc "$OUT_DOCX" -o "$OUT_PDF"
echo "Wrote: $OUT_PDF"
SH

chmod +x "${BIN_DIR}/md2docx"

# Wrapper command for PPTX
cat > "${BIN_DIR}/md2pptx" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# md2pptx: Markdown -> PPTX -> PDF with title/author/bib/lang extraction
# Usage:
#   md2pptx input.md [--author "Name"] [--bib "ref.bib"] [--lang "en-US"] [extra pandoc args...]

if [[ $# -lt 1 ]]; then
  echo "Usage: md2pptx <input.md> [--author \"Name\"] [--bib \"ref.bib\"] [--lang \"en-US\"] [extra pandoc args...]"
  exit 1
fi

IN="$1"
shift || true

EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --author)
      EXTRA_ARGS+=("--metadata" "author=$2")
      shift 2
      ;;
    --bib)
      EXTRA_ARGS+=("--citeproc" "--bibliography" "$2")
      shift 2
      ;;
    --lang)
      EXTRA_ARGS+=("--metadata" "lang=$2")
      shift 2
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

OUT_PPTX="${IN%.*}.pptx"
OUT_PDF="${IN%.*}.pdf"

# 1. Convert Markdown to PPTX
pandoc --defaults pptx-star.yaml "$IN" -o "$OUT_PPTX" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
echo "Wrote: $OUT_PPTX"

# 2. Convert to PDF
pandoc "$IN" -o "$OUT_PDF" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
echo "Wrote: $OUT_PDF"
SH

chmod +x "${BIN_DIR}/md2pptx"

# Wrapper command for GUP
cat > "${BIN_DIR}/gup" <<SH
#!/usr/bin/env bash
# gup: Upload .docx/.pptx to Google Drive and convert to GDoc/GSlide
# Requires python3 and google-api-python-client, google-auth-oauthlib, pyyaml (pip install -r ${PANDOC_DIR}/gup/requirements.txt)
python3 "${PANDOC_DIR}/gup/src/gup.py" "\$@"
SH
chmod +x "${BIN_DIR}/gup"

# Deploy gup resources
mkdir -p "${PANDOC_DIR}/gup"
cp -rf gup/ "${PANDOC_DIR}/gup/"

echo ""
echo "✅ md2docx, md2pptx & gup installed."
echo "  Filter:   ${FILTERS_DIR}/md2star.lua"
echo "  Defaults: ${DEFAULTS_DIR}/docx-star.yaml, pptx-star.yaml"
echo "  Templates: ${PANDOC_DIR}/template.docx, template.pptx"
echo "  Commands:  ${BIN_DIR}/md2docx, md2pptx, gup"
echo ""
echo "Next step: ensure ${BIN_DIR} is on your PATH."
echo "For zsh (macOS default):"
echo '  echo '''export PATH="$HOME/.local/bin:$PATH"''' >> ~/.zshrc && source ~/.zshrc'
echo ""
echo "Try:"
echo "  md2docx notes.md"
echo "  gup --help"
