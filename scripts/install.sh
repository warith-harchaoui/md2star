#!/usr/bin/env bash
set -euo pipefail

# md2star Installer (macOS & Linux)
# Run from the repository root: bash scripts/install.sh
#
# This script automates the deployment of the md2star toolset.
# It performs the following actions:
# 1. Configures the Pandoc user data directory (~/.pandoc).
# 2. Deploys custom Lua filters for smart metadata handling.
# 3. Deploys curated DOCX and PPTX reference templates.
# 4. Injects absolute system paths into Pandoc YAML defaults to ensure 
#    reliability when running from any directory.
# 5. Installs lightweight Bash wrappers (md2docx, md2pptx, gup) into 
#    ~/.local/bin for immediate CLI access.
#
# Preamble:
# md2star is more than a converter; it's a bridge between Markdown efficiency 
# and Office professionalism. This installer ensures all architectural pieces 
# are correctly linked.

PANDOC_DIR="${HOME}/.pandoc"
FILTERS_DIR="${PANDOC_DIR}/filters"
DEFAULTS_DIR="${PANDOC_DIR}/defaults"
BIN_DIR="${HOME}/.local/bin"

# Ensure we're in the repo root (contains pandoc/, assets/, gup/)
if [[ ! -f pandoc/filters/md2star.lua || ! -f assets/template.docx ]]; then
    echo "Error: Run install.sh from the md2star repository root." >&2
    exit 1
fi

mkdir -p "${FILTERS_DIR}" "${DEFAULTS_DIR}" "${BIN_DIR}"

# Copy filter + defaults + templates + metadata + preprocessor
cp -f "pandoc/filters/md2star.lua" "${FILTERS_DIR}/md2star.lua"
cp -f "scripts/preprocessing.py" "${PANDOC_DIR}/preprocessing.py"
cp -f "pandoc/metadata.yaml" "${PANDOC_DIR}/metadata.yaml"
cp -f "assets/template.docx" "${PANDOC_DIR}/template.docx"
cp -f "assets/template.pptx" "${PANDOC_DIR}/template.pptx"

# Step 2: Inject absolute paths into defaults files.
# Pandoc requires absolute paths in defaults files if the templates are not 
# in the current working directory. We automate this bridging during install.
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
  echo "Usage: md2docx <input.md> [--author \"Name\"] [--bib \"ref.bib\"] [--bibliography-name \"References\"] [--lang \"en-US\"] [extra pandoc args...]"
  exit 1
fi

IN="$1"
shift || true

EXTRA_ARGS=()
BIB_FILE=""
BIB_NAME="Bibliography"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --author)
      EXTRA_ARGS+=("--metadata" "author=$2")
      shift 2
      ;;
    --bib)
      BIB_FILE="$2"
      EXTRA_ARGS+=("--citeproc" "--bibliography" "$2")
      shift 2
      ;;
    --bibliography-name)
      BIB_NAME="$2"
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

# 0. Preprocess Markdown (handles spacing before list items)
TEMP_MD=$(python3 "${HOME}/.pandoc/preprocessing.py" "$IN")
trap 'rm -f "$TEMP_MD"' EXIT

if [ -n "$BIB_FILE" ]; then
    printf "\n# %s\n" "$BIB_NAME" >> "$TEMP_MD"
fi

# 1. Convert Markdown to DOCX
pandoc --defaults docx-star.yaml "$TEMP_MD" -o "$OUT_DOCX" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
echo "Wrote: $OUT_DOCX"


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
  echo "Usage: md2pptx <input.md> [--author \"Name\"] [--bib \"ref.bib\"] [--bibliography-name \"References\"] [--lang \"en-US\"] [extra pandoc args...]"
  exit 1
fi

IN="$1"
shift || true

EXTRA_ARGS=()
BIB_FILE=""
BIB_NAME="Bibliography"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --author)
      EXTRA_ARGS+=("--metadata" "author=$2")
      shift 2
      ;;
    --bib)
      BIB_FILE="$2"
      EXTRA_ARGS+=("--citeproc" "--bibliography" "$2")
      shift 2
      ;;
    --bibliography-name)
      BIB_NAME="$2"
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

# 0. Preprocess Markdown (handles spacing before list items)
TEMP_MD=$(python3 "${HOME}/.pandoc/preprocessing.py" "$IN")
trap 'rm -f "$TEMP_MD"' EXIT

if [ -n "$BIB_FILE" ]; then
    printf "\n# %s\n" "$BIB_NAME" >> "$TEMP_MD"
fi

# 1. Convert Markdown to PPTX
pandoc --defaults pptx-star.yaml "$TEMP_MD" -o "$OUT_PPTX" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
echo "Wrote: $OUT_PPTX"


SH

chmod +x "${BIN_DIR}/md2pptx"

# Wrapper command for GUP
cat > "${BIN_DIR}/gup" <<SH
#!/usr/bin/env bash
# gup: Upload .docx/.pptx to Google Drive and convert to GDoc/GSlide
# Usage: gup file.docx --folder-id <FOLDER_ID>
# Requires: python3, google-api-python-client, google-auth-oauthlib, pyyaml
python3 "${PANDOC_DIR}/gup/src/gup.py" "\$@"
SH
chmod +x "${BIN_DIR}/gup"

# Deploy gup resources
mkdir -p "${PANDOC_DIR}/gup"
cp -rf gup/ "${PANDOC_DIR}/gup/"

# Install gup Python dependencies so the command works immediately
echo "--- Installing gup Python dependencies ---"
pip install -q -r gup/requirements.txt 2>/dev/null \
  || pip3 install -q -r gup/requirements.txt 2>/dev/null \
  || echo "⚠️  Could not install gup dependencies automatically. Run: pip install -r gup/requirements.txt"

# Ensure assets are copied
mkdir -p "${PANDOC_DIR}/assets"
cp -rf assets/* "${PANDOC_DIR}/assets/"

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
