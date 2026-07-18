#!/usr/bin/env bash
set -euo pipefail

# Refresh every third-party asset the md2star GUI loads.
#
# Bumps the pinned versions below as appropriate and re-runs this script;
# the result is committed into md2star/data/gui/vendor/ so the GUI works
# fully offline. The script is idempotent — re-running it overwrites the
# previous fetch.
#
# Dependencies:
#   - curl  (PDF.js + Tailwind + Google Fonts)
#   - node + npx  (esbuild bundle for CodeMirror)

# ── Pinned versions ──────────────────────────────────────────────────
PDFJS_VERSION="4.10.38"
CM_STATE_VERSION="6.5.1"
CM_VIEW_VERSION="6.36.2"
CM_COMMANDS_VERSION="6.7.1"
CM_LANG_MD_VERSION="6.3.1"
CM_LANG_VERSION="6.10.8"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="${REPO_ROOT}/md2star/data/gui/vendor"

# ── Pre-flight ───────────────────────────────────────────────────────
if ! command -v curl >/dev/null; then
    echo "vendor_gui: curl is required (used for PDF.js + Tailwind + fonts)." >&2
    exit 127
fi
if ! command -v npx >/dev/null; then
    echo "vendor_gui: node + npx are required (used to bundle CodeMirror)." >&2
    exit 127
fi

mkdir -p "${VENDOR}/pdfjs" "${VENDOR}/fonts/jetbrains-mono"

# ── PDF.js ───────────────────────────────────────────────────────────
echo "[1/4] PDF.js ${PDFJS_VERSION}"
curl -fsSL -o "${VENDOR}/pdfjs/pdf.min.mjs" \
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@${PDFJS_VERSION}/build/pdf.min.mjs"
curl -fsSL -o "${VENDOR}/pdfjs/pdf.worker.min.mjs" \
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@${PDFJS_VERSION}/build/pdf.worker.min.mjs"

# ── Tailwind Play CDN (forms + typography plugins) ───────────────────
echo "[2/4] Tailwind Play CDN bundle"
curl -fsSL -o "${VENDOR}/tailwind.js" \
    'https://cdn.tailwindcss.com?plugins=forms,typography'

# ── Fonts — Montserrat (sans) + Roboto Serif (serif) ────────────────
# Editor monospace uses the OS's own system mono stack (ui-monospace /
# SFMono / Menlo / Consolas), so no third web font ships.
echo "[3/4a] Montserrat (from front-ui skill — variable + static fallbacks)"
FRONT_UI_MONT="${HOME}/.claude/skills/front-ui/assets/fonts/montserrat"
if [[ -d "${FRONT_UI_MONT}" ]]; then
    mkdir -p "${VENDOR}/fonts/montserrat"
    cp -f "${FRONT_UI_MONT}"/*.woff2 "${FRONT_UI_MONT}/fonts.css" \
          "${FRONT_UI_MONT}/OFL.txt" "${VENDOR}/fonts/montserrat/" 2>/dev/null || true
else
    echo "  WARNING: front-ui skill not at ${FRONT_UI_MONT}; Montserrat not refreshed." >&2
fi

echo "[3/4b] Roboto Serif (from Google Fonts — variable, weights 400/500/600/700)"
mkdir -p "${VENDOR}/fonts/roboto-serif"
TMP_CSS="$(mktemp)"
curl -fsSL -H 'User-Agent: Mozilla/5.0' \
     -o "${TMP_CSS}" \
     'https://fonts.googleapis.com/css2?family=Roboto+Serif:opsz,wght@8..144,400;8..144,500;8..144,600;8..144,700&display=swap'
grep -oE 'https://fonts.gstatic.com/[^)]+\.woff2' "${TMP_CSS}" | sort -u \
    | while read -r url; do
        fname="${url##*/}"
        curl -fsSL -o "${VENDOR}/fonts/roboto-serif/${fname}" "${url}"
    done
sed -E 's|https://fonts.gstatic.com/[^)]+/([^)/]+\.woff2)|./\1|g' \
    "${TMP_CSS}" > "${VENDOR}/fonts/roboto-serif/fonts.css"
rm -f "${TMP_CSS}"
if curl -fsSL -o "${VENDOR}/fonts/roboto-serif/OFL.txt.tmp" \
        'https://raw.githubusercontent.com/googlefonts/RobotoSerif/main/OFL.txt'; then
    mv "${VENDOR}/fonts/roboto-serif/OFL.txt.tmp" \
       "${VENDOR}/fonts/roboto-serif/OFL.txt"
else
    rm -f "${VENDOR}/fonts/roboto-serif/OFL.txt.tmp"
    echo "  WARNING: could not refresh Roboto Serif OFL.txt; keeping existing copy." >&2
fi

# ── CodeMirror 6 single-file bundle (one EditorState constructor) ────
echo "[4/4] CodeMirror bundle via esbuild"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
cat > "${WORK}/entry.js" <<'JS'
export { EditorState } from "@codemirror/state";
export { EditorView, keymap, lineNumbers, highlightActiveLine }
  from "@codemirror/view";
export { defaultKeymap, indentWithTab, history, historyKeymap }
  from "@codemirror/commands";
export { markdown } from "@codemirror/lang-markdown";
export { syntaxHighlighting, defaultHighlightStyle, indentUnit }
  from "@codemirror/language";
JS
(
    cd "${WORK}"
    npm init -y >/dev/null
    npm install --silent --save-dev \
        esbuild \
        "@codemirror/state@${CM_STATE_VERSION}" \
        "@codemirror/view@${CM_VIEW_VERSION}" \
        "@codemirror/commands@${CM_COMMANDS_VERSION}" \
        "@codemirror/lang-markdown@${CM_LANG_MD_VERSION}" \
        "@codemirror/language@${CM_LANG_VERSION}" \
        >/dev/null 2>&1
    npx esbuild entry.js \
        --bundle --format=esm --minify --target=es2020 \
        --legal-comments=external \
        --outfile="${VENDOR}/codemirror.js" 2>&1 \
        | grep -E '^\s+|kb' | tail -3
)

echo ""
echo "Vendored assets:"
(
    cd "${VENDOR}" || exit 1
    # find feeds du via xargs so file names with whitespace stay quoted.
    find . -type f -print0 | sort -z | xargs -0 du -h | column -t
)
