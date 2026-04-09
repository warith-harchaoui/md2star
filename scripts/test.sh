#!/usr/bin/env bash
set -euo pipefail

# md2star test suite
#
# Ensures all core features work as expected by exercising the
# md2docx and md2pptx wrappers against sample Markdown files and
# inspecting the resulting Office documents for expected content.
#
# Usage:
#   bash scripts/test.sh       (standalone)
#   make test                  (via Makefile)
#
# Exit code: 0 if all assertions pass, 1 otherwise.

MD2DOCX="${HOME}/.local/bin/md2docx"
MD2PPTX="${HOME}/.local/bin/md2pptx"
DOCX_DIR="assets/docx"
PPTX_DIR="assets/pptx"

# Ensure we're in the repo root
if [[ ! -f "$DOCX_DIR/basic.md" ]]; then
    echo "Error: Run test.sh from the md2star repository root." >&2
    exit 1
fi

# Re-install the tool so we always test the latest code
echo "--- Installing tool for testing ---"
bash scripts/install.sh > /dev/null

error_count=0

# ── Assertion helper for DOCX ──────────────────────────────────────
# DOCX is an OOXML ZIP. We extract all XML and grep for the pattern
# (case-insensitive). More reliable than pandoc -t plain, which may
# omit metadata/subtitle content from the output.
assert_contains_docx() {
    local file="$1"
    local pattern="$2"
    local msg="$3"
    if [ ! -f "$file" ]; then
        echo "  [FAIL] $msg (File '$file' not found)"
        error_count=$((error_count + 1))
        return
    fi
    if unzip -p "$file" | grep -ai "$pattern" > /dev/null; then
        echo "  [PASS] $msg"
    else
        echo "  [FAIL] $msg (Pattern '$pattern' not found in $file)"
        error_count=$((error_count + 1))
    fi
}

# ── Assertion helper for PPTX ──────────────────────────────────────
# Extracts all internal XML from the .pptx (an OOXML ZIP archive)
# and checks that the expected text substring appears.
assert_contains_pptx() {
    local file="$1"
    local pattern="$2"
    local msg="$3"
    if [ ! -f "$file" ]; then
        echo "  [FAIL] $msg (File '$file' not found)"
        error_count=$((error_count + 1))
        return
    fi
    # unzip -p dumps every file inside the ZIP to stdout.
    # We pipe into grep -ai (case-insensitive, binary-safe).
    # We avoid grep -q because it can trigger SIGPIPE under set -o pipefail.
    if unzip -p "$file" | grep -ai "$pattern" > /dev/null; then
        echo "  [PASS] $msg"
    else
        echo "  [FAIL] $msg (Pattern '$pattern' not found in $file)"
        error_count=$((error_count + 1))
    fi
}

# ── TEST 1: Basic DOCX conversion ─────────────────────────────────
# Verify that the first H1 heading becomes the document title.
echo ""
echo "--- Running Basic Test (DOCX) ---"
$MD2DOCX "$DOCX_DIR/basic.md" > /dev/null
assert_contains_docx "$DOCX_DIR/basic.docx" "Basic Title" "Title extracted to DOCX"

# ── TEST 2: Author injection ──────────────────────────────────────
# Verify that --author embeds the name in the subtitle.
echo ""
echo "--- Running Author Test (DOCX) ---"
$MD2DOCX "$DOCX_DIR/with_author.md" --author "Tester" > /dev/null
assert_contains_docx "$DOCX_DIR/with_author.docx" "Tester" "Author injected to DOCX"

# ── TEST 3: Bibliography rendering ────────────────────────────────
# Verify that --bib triggers citeproc and the cited author appears.
echo ""
echo "--- Running Bibliography Test (DOCX & PPTX) ---"
$MD2DOCX "$DOCX_DIR/with_bib.md" --bib "assets/references.bib" --bibliography-name "References" > /dev/null
assert_contains_docx "$DOCX_DIR/with_bib.docx" "Pearl" "Bibliography rendered in DOCX"
assert_contains_docx "$DOCX_DIR/with_bib.docx" "References" "Custom bibliography heading injected in DOCX"

$MD2PPTX "$DOCX_DIR/with_bib.md" --bib "assets/references.bib" --bibliography-name "References" > /dev/null
assert_contains_pptx "$DOCX_DIR/with_bib.pptx" "Pearl" "Bibliography rendered in PPTX"
assert_contains_pptx "$DOCX_DIR/with_bib.pptx" "References" "Custom bibliography heading injected in PPTX"

# ── TEST 4: Language & date localisation ──────────────────────────
# Temporarily switch metadata to French; verify the format appears
# including the dynamic year.
echo ""
echo "--- Running Language/Date Test (DOCX) ---"
printf "author: EMANON\ndate_format: '%%d %%B %%Y'\nlang: fr-FR\n" > pandoc/metadata.yaml
bash scripts/install.sh > /dev/null
$MD2DOCX "$DOCX_DIR/with_lang.md" --author "User" > /dev/null
assert_contains_docx "$DOCX_DIR/with_lang.docx" "$(date +%Y)" "Date correctly rendered using date_format layout"

# ── TEST 5: Math formula rendering ────────────────────────────────
# Verify that LaTeX math content survives the conversion.
echo ""
echo "--- Running Math Test (DOCX) ---"
$MD2DOCX "$DOCX_DIR/math.md" > /dev/null
assert_contains_docx "$DOCX_DIR/math.docx" "math" "Math rendered in DOCX"

# ── TEST 6: Extensive PPTX example ────────────────────────────────
# Verify that a rich presentation converts correctly.
echo ""
echo "--- Running Extensive Test (PPTX) ---"
$MD2PPTX "$PPTX_DIR/example.md" > /dev/null
assert_contains_pptx "$PPTX_DIR/example.pptx" "Slides can have videos" "Extensive PPTX example parsed"

# ── Reset metadata to defaults ────────────────────────────────────
printf "author: EMANON\ndate_format: '%%m/%%d/%%y'\nlang: en-US\n" > pandoc/metadata.yaml
bash scripts/install.sh > /dev/null

# ── Summary ────────────────────────────────────────────────────────
echo ""
if [ $error_count -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    # Keep test outputs in assets/ as living examples for the repository
    exit 0
else
    echo "❌ $error_count TEST(S) FAILED"
    exit 1
fi
