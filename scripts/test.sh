#!/usr/bin/env bash
set -euo pipefail

# md2star integration test suite.
#
# Exercises the md2docx / md2pptx CLIs against sample Markdown files and
# inspects the generated Office documents (OOXML zips) for the expected
# content. Exits 0 on full success, 1 on the first failure batch.
#
# Usage:
#   bash scripts/test.sh        (standalone)
#   make test                   (via Makefile)
#
# Requirements:
#   - pandoc on PATH
#   - md2star installed (via `make install` or `make dev` + activated venv)
#
# Notes:
#   - We DO NOT mutate pandoc/data/metadata.yaml mid-run any more. Per-test
#     language overrides go through the CLI (`--lang fr-FR` plus pandoc's
#     own `--metadata date_format=...`) so an interrupted run leaves the
#     repo clean.

MD2DOCX=${MD2DOCX:-md2docx}
MD2PPTX=${MD2PPTX:-md2pptx}
DOCX_DIR="assets/docx"
PPTX_DIR="assets/pptx"

if [[ ! -f "$DOCX_DIR/basic.md" ]]; then
    echo "Error: run scripts/test.sh from the md2star repository root." >&2
    exit 1
fi

if ! command -v "$MD2DOCX" >/dev/null 2>&1; then
    cat >&2 <<EOF
Error: \`$MD2DOCX\` not found on PATH.

Install the package first:
  make install            (system-wide via pipx)
  make dev && source .venv/bin/activate
                          (local dev venv; then re-run this script)
EOF
    exit 127
fi

error_count=0

# ── DOCX assertion helper ───────────────────────────────────────────
# DOCX is an OOXML zip. We extract every internal file and grep for the
# pattern (case-insensitive, binary-safe). More reliable than Pandoc's
# plaintext writer, which omits some metadata.
assert_contains_docx() {
    local file="$1"
    local pattern="$2"
    local msg="$3"
    if [[ ! -f "$file" ]]; then
        echo "  [FAIL] $msg (file '$file' not found)"
        error_count=$((error_count + 1))
        return
    fi
    if unzip -p "$file" | grep -ai "$pattern" > /dev/null; then
        echo "  [PASS] $msg"
    else
        echo "  [FAIL] $msg (pattern '$pattern' not found in $file)"
        error_count=$((error_count + 1))
    fi
}

# ── PPTX assertion helper ───────────────────────────────────────────
assert_contains_pptx() {
    local file="$1"
    local pattern="$2"
    local msg="$3"
    if [[ ! -f "$file" ]]; then
        echo "  [FAIL] $msg (file '$file' not found)"
        error_count=$((error_count + 1))
        return
    fi
    if unzip -p "$file" | grep -ai "$pattern" > /dev/null; then
        echo "  [PASS] $msg"
    else
        echo "  [FAIL] $msg (pattern '$pattern' not found in $file)"
        error_count=$((error_count + 1))
    fi
}

# ── TEST 1: Basic DOCX ─────────────────────────────────────────────
# Verify that the first H1 heading becomes the document title.
echo ""
echo "--- Basic DOCX ---"
$MD2DOCX "$DOCX_DIR/basic.md" > /dev/null
assert_contains_docx "$DOCX_DIR/basic.docx" "Basic Title" "Title extracted to DOCX"

# ── TEST 2: Author injection ───────────────────────────────────────
echo ""
echo "--- Author DOCX ---"
$MD2DOCX "$DOCX_DIR/with_author.md" --author "Tester" > /dev/null
assert_contains_docx "$DOCX_DIR/with_author.docx" "Tester" "Author injected to DOCX"

# ── TEST 3: Bibliography ───────────────────────────────────────────
echo ""
echo "--- Bibliography DOCX & PPTX ---"
$MD2DOCX "$DOCX_DIR/with_bib.md" --bib "assets/references.bib" \
    --bibliography-name "References" > /dev/null
assert_contains_docx "$DOCX_DIR/with_bib.docx" "Pearl" "Bibliography rendered in DOCX"
assert_contains_docx "$DOCX_DIR/with_bib.docx" "References" "Custom bibliography heading in DOCX"

$MD2PPTX "$DOCX_DIR/with_bib.md" --bib "assets/references.bib" \
    --bibliography-name "References" > /dev/null
assert_contains_pptx "$DOCX_DIR/with_bib.pptx" "Pearl" "Bibliography rendered in PPTX"
assert_contains_pptx "$DOCX_DIR/with_bib.pptx" "References" "Custom bibliography heading in PPTX"

# ── TEST 4: Language & date localisation ───────────────────────────
# Pass language + date_format directly through the CLI so we never mutate
# the bundled metadata.yaml on disk. The `--metadata date_format=...` flag
# is forwarded verbatim to pandoc.
echo ""
echo "--- Language/Date DOCX (fr-FR) ---"
$MD2DOCX "$DOCX_DIR/with_lang.md" --author "User" \
    --lang "fr-FR" \
    --metadata "date_format=%d %B %Y" > /dev/null
assert_contains_docx "$DOCX_DIR/with_lang.docx" "$(date +%Y)" \
    "Date rendered using requested date_format"

# ── TEST 5: Math ───────────────────────────────────────────────────
echo ""
echo "--- Math DOCX ---"
$MD2DOCX "$DOCX_DIR/math.md" > /dev/null
assert_contains_docx "$DOCX_DIR/math.docx" "math" "Math rendered in DOCX"

# ── TEST 6: Extensive PPTX example ─────────────────────────────────
echo ""
echo "--- Extensive PPTX ---"
$MD2PPTX "$PPTX_DIR/example.md" > /dev/null
assert_contains_pptx "$PPTX_DIR/example.pptx" "Slides can have videos" \
    "Extensive PPTX example parsed"

# ── Summary ────────────────────────────────────────────────────────
echo ""
if [[ $error_count -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "$error_count TEST(S) FAILED"
    exit 1
fi
