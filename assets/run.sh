#!/bin/bash
# run.sh - Compiles all Markdown assets into DOCX and PPTX formats
# This file serves as a cheat-sheet and batch compiler for the assets examples.

# Fail if any command errors
set -e

# Smart navigation: always run from the assets/ directory
cd "$(dirname "$0")"

echo "🚀 Starting compilation of assets..."

# 1. Basic DOCX
echo "Compiling docx/basic.md..."
md2docx docx/basic.md

# 2. Author Injected DOCX
echo "Compiling docx/with_author.md..."
md2docx docx/with_author.md --author "Bob"

# 3. Bibliography DOCX
echo "Compiling docx/with_bib.md..."
md2docx docx/with_bib.md --bib references.bib --bibliography-name "References"

# 4. Language & Date (French) DOCX
echo "Compiling docx/with_lang.md..."
md2docx docx/with_lang.md --author "Jean"

# 5. Math Formulas DOCX
echo "Compiling docx/math.md..."
md2docx docx/math.md

# 6. Extensive PPTX Example
echo "Compiling pptx/example.md..."
md2pptx pptx/example.md

echo "✅ All assets compiled successfully!"
