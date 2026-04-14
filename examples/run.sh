#!/bin/bash
# run.sh - Compiles all Markdown examples into DOCX and PPTX formats
# Defaults to author "Richard Feynman" and links the master ../assets/references.bib.

# Fail if any command errors
set -e

# Smart navigation: always run from the examples/ directory regardless of where the script is called
cd "$(dirname "$0")"

echo "🚀 Starting compilation..."

# 1. Comprehensive Document
echo "Compiling comprehensive_document.md..."
md2docx comprehensive_document.md --author "Richard Feynman" --bib "../assets/references.bib" --bibliography-name "References"
md2pptx comprehensive_document.md --author "Richard Feynman" --bib "../assets/references.bib" --bibliography-name "References"

# 2. Comprehensive Presentation
echo "Compiling comprehensive_presentation.md..."
md2docx comprehensive_presentation.md --author "Richard Feynman" --bib "../assets/references.bib" --bibliography-name "References"
md2pptx comprehensive_presentation.md --author "Richard Feynman" --bib "../assets/references.bib" --bibliography-name "References"

# 3. Guide Complet Document (French)
echo "Compiling guide_complet_document_fr.md..."
md2docx guide_complet_document_fr.md --author "Richard Feynman" --bib "../assets/references.bib" --bibliography-name "Références"
md2pptx guide_complet_document_fr.md --author "Richard Feynman" --bib "../assets/references.bib" --bibliography-name "Références"

echo "✅ All examples compiled successfully by Richard Feynman!"
