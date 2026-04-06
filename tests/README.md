# Tests

This directory contains the automated test suite for md2star.

## Overview

| File | Purpose |
|------|---------|
| `test_preprocessing.py` | Unit tests for the Markdown preprocessor (list spacing) |
| `test_json_to_bib.py` | Unit tests for the JSON→BibTeX converter |
| `test_gup.py` | Unit tests for the Google Drive upload utility |

## Running Tests

### Unit tests (Python)

Requires **pytest**:

```bash
pip install pytest
python -m pytest tests/ -v
```

Run a specific test file:

```bash
python -m pytest tests/test_preprocessing.py -v
```

### Integration tests (shell)

Requires **Pandoc** installed. These exercise the full `md2docx` and `md2pptx` pipelines:

```bash
make test
```

Or directly:

```bash
bash scripts/test.sh
```

## What Is Tested

- **Metadata accuracy**: Title extraction, author injection, subtitle formatting
- **Cross-format integrity**: DOCX and PPTX outputs match expected content
- **Bibliography rendering**: Citeproc integration with `.bib` files
- **Locale localisation**: French date rendering and international headers
- **Math formulas**: LaTeX math survives conversion
- **List preprocessing**: Blank lines before list items for correct Pandoc parsing
