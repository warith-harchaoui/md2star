#!/usr/bin/env bash
set -euo pipefail

# md2star test suite
# Ensures all core features work as expected.

MD2DOCX="${HOME}/.local/bin/md2docx"
MD2PPTX="${HOME}/.local/bin/md2pptx"
SAMPLES_DIR="tests/samples"

echo "--- Installing tool for testing ---"
bash scripts/install.sh > /dev/null

error_count=0

assert_contains_docx() {
    local file="$1"
    local pattern="$2"
    local msg="$3"
    if [ ! -f "$file" ]; then
        echo "  [FAIL] $msg (File '$file' not found)"
        error_count=$((error_count + 1))
        return
    fi
    # Use --standalone to include metadata (like Title) in plain text output
    if pandoc --standalone "$file" -t plain | grep -qi "$pattern"; then
        echo "  [PASS] $msg"
    else
        echo "  [FAIL] $msg (Pattern '$pattern' not found in $file)"
        error_count=$((error_count + 1))
    fi
}

assert_contains_pptx() {
    local file="$1"
    local pattern="$2"
    local msg="$3"
    if [ ! -f "$file" ]; then
        echo "  [FAIL] $msg (File '$file' not found)"
        error_count=$((error_count + 1))
        return
    fi
    # unzip -p dumps all internal XML files to stdout, allowing us to grep for text
    # We avoid grep -q because it can cause SIGPIPE with set -o pipefail
    if unzip -p "$file" | grep -ai "$pattern" > /dev/null; then
        echo "  [PASS] $msg"
    else
        echo "  [FAIL] $msg (Pattern '$pattern' not found in $file)"
        error_count=$((error_count + 1))
    fi
}

echo ""
echo "--- Running Basic Test (DOCX) ---"
$MD2DOCX "$SAMPLES_DIR/basic.md" > /dev/null
assert_contains_docx "$SAMPLES_DIR/basic.docx" "Basic Title" "Title extracted to DOCX"

echo ""
echo "--- Running Basic Test (PPTX) ---"
$MD2PPTX "$SAMPLES_DIR/basic.md" > /dev/null
assert_contains_pptx "$SAMPLES_DIR/basic.pptx" "Basic Title" "Title extracted to PPTX"

echo ""
echo "--- Running Author Test (DOCX) ---"
$MD2DOCX "$SAMPLES_DIR/with_author.md" --author "Tester" > /dev/null
assert_contains_docx "$SAMPLES_DIR/with_author.docx" "Tester" "Author injected to DOCX"

echo ""
echo "--- Running Author Test (PPTX) ---"
$MD2PPTX "$SAMPLES_DIR/with_author.md" --author "Tester" > /dev/null
assert_contains_pptx "$SAMPLES_DIR/with_author.pptx" "Tester" "Author injected to PPTX"

echo ""
echo "--- Running Bibliography Test (DOCX) ---"
# Use the provided asset snapshot for robust testing
$MD2DOCX "$SAMPLES_DIR/with_bib.md" --bib "assets/deraison.bib" > /dev/null
# Check for a known author in the deraison.bib snapshot
assert_contains_docx "$SAMPLES_DIR/with_bib.docx" "Pearl" "Bibliography rendered in DOCX"

echo ""
echo "--- Running Bibliography Test (PPTX) ---"
$MD2PPTX "$SAMPLES_DIR/with_bib.md" --bib "assets/deraison.bib" > /dev/null
assert_contains_pptx "$SAMPLES_DIR/with_bib.pptx" "Pearl" "Bibliography rendered in PPTX"

echo ""
echo "--- Running Language/Date Test ---"
# Set metadata for test
printf "author: EMANON\ndate_format: '%%d %%B %%Y'\nlang: fr-FR\n" > pandoc/metadata.yaml
bash scripts/install.sh > /dev/null
$MD2DOCX "$SAMPLES_DIR/with_lang.md" --author "User" > /dev/null
assert_contains_docx "$SAMPLES_DIR/with_lang.docx" "février" "Date rendered in French (DOCX)"
$MD2PPTX "$SAMPLES_DIR/with_lang.md" --author "User" > /dev/null
assert_contains_pptx "$SAMPLES_DIR/with_lang.pptx" "février" "Date rendered in French (PPTX)"

echo ""
echo "--- Running Math Test ---"
$MD2DOCX "$SAMPLES_DIR/math.md" > /dev/null
assert_contains_docx "$SAMPLES_DIR/math.docx" "math" "Math rendered in DOCX"
$MD2PPTX "$SAMPLES_DIR/math.md" > /dev/null
assert_contains_pptx "$SAMPLES_DIR/math.pptx" "math" "Math rendered in PPTX"

# Reset metadata
printf "author: EMANON\ndate_format: '%%m/%%d/%%y'\nlang: en-US\n" > pandoc/metadata.yaml
bash scripts/install.sh > /dev/null

echo ""
if [ $error_count -eq 0 ]; then
    echo "✅ ALL TESTS PASSED"
    # Cleanup test outputs
    rm -f "$SAMPLES_DIR"/*.docx "$SAMPLES_DIR"/*.pptx "$SAMPLES_DIR"/*.pdf
    exit 0
else
    echo "❌ $error_count TESTS FAILED"
    exit 1
fi
