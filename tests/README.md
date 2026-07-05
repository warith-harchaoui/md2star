# Tests

Pytest unit suite + a shell integration runner. The `conftest.py` autouse
fixture redirects `$MD2STAR_CACHE_DIR` to a per-test `tmp_path`, so cache
artifacts never escape the test directory.

## Layout

| File | What it covers |
|------|----------------|
| `conftest.py` | Cache-isolation fixture. |
| `test_preprocessing.py` | The 11-phase Markdown preprocessor (~80 tests): list spacing, HTML→pipe-table conversion, mermaid rendering, math unwrap, image normalization, PPTX slide isolation, `--skip-phase`, language detection. |
| `test_lua_filter.py` | The Pandoc Lua filter — drives `pandoc --lua-filter` against fixture Markdown. Skipped when pandoc is not on PATH. |
| `test_postprocess.py` | `inject_table_styles` round-trips against a synthesised DOCX zip. |
| `test_roundtrip.py` | `md → docx → md` fidelity: content survival + the fixed-point (`g(g(x)) == g(x)`) idempotence guarantee, read back with Pandoc's native DOCX reader. Skipped when pandoc is not on PATH. |
| `examples/` | Multi-page demo `.md` sources (Markdown only — the corresponding `.docx` / `.pptx` outputs are regenerable via `run.sh` and not committed). |

## Running

```bash
# Once: create the dev venv and install editable.
make dev
source .venv/bin/activate

# All tests.
python -m pytest tests/ -v

# A single file.
python -m pytest tests/test_preprocessing.py -v

# The integration suite (needs pandoc + the installed CLI on PATH).
make test                   # or: bash scripts/test.sh
```

## What is asserted

- **Metadata flow**: title extraction, author injection, subtitle composition (Lua filter).
- **Cross-format integrity**: DOCX and PPTX zips contain the expected text strings.
- **Bibliography**: citeproc against the curated `assets/references.bib`.
- **Date localisation**: French weekday / month rendering via the in-filter dictionary.
- **Preprocessor invariants**: list spacing, fenced-block preservation, HTML-table conversion, pipe-table separator scaling, image width injection, language detection, mermaid fallback, math-in-code unwrap, PPTX slide isolation, `--skip-phase` plumbing.
