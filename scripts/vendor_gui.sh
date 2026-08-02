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

mkdir -p "${VENDOR}/pdfjs"

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

# ── Fonts — the three-Roboto set (sans + serif + mono) ──────────────
# One super-family, three self-hosted variable woff2s, copied straight
# from the sprezzature-ui skill so the GUI matches the house style and
# stays fully offline (no Google Fonts / CDN fetch).
echo "[3/4] Fonts — Roboto (sans) + Roboto Serif (serif) + Roboto Mono (mono)"
SPREZZ_FONTS="${HOME}/.claude/skills/sprezzature-ui/assets/fonts"
if [[ -d "${SPREZZ_FONTS}" ]]; then
    for fam in roboto roboto-serif roboto-mono; do
        mkdir -p "${VENDOR}/fonts/${fam}"
        cp -f "${SPREZZ_FONTS}/${fam}"/*.woff2 \
              "${SPREZZ_FONTS}/${fam}/fonts.css" \
              "${SPREZZ_FONTS}/${fam}/OFL.txt" \
              "${VENDOR}/fonts/${fam}/" 2>/dev/null || true
    done
else
    echo "  WARNING: sprezzature-ui skill not at ${SPREZZ_FONTS}; fonts not refreshed." >&2
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
