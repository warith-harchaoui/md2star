# Assets

Example Markdown files, reference templates, and generated outputs used by md2star.

## Structure

```
assets/
├── docx/           # DOCX test fixtures and examples
│   ├── basic.md    # Minimal document (title extraction)
│   ├── with_author.md
│   ├── with_bib.md
│   ├── with_lang.md
│   └── math.md
├── pptx/           # PPTX test fixtures
│   └── example.md
├── references.bib  # Sample bibliography (used in with_bib tests)
├── template.docx   # Reference styling template for DOCX
└── template.pptx   # Reference styling template for PPTX
```

## Templates

`template.docx` and `template.pptx` define the default fonts, margins, heading styles, and subtitle formatting for generated documents. During installation, they are copied to `~/.pandoc/` (or `%APPDATA%\pandoc` on Windows).

To customize output styling, edit these templates in `assets/` and run `make reinstall`.

## DOCX Examples

| File | Demonstrates |
|------|--------------|
| `basic.md` | Title extraction from first H1 |
| `with_author.md` | `--author` injection into subtitle |
| `with_bib.md` | Bibliography with `--bib` and `--bibliography-name` |
| `with_lang.md` | Localised dates (e.g. French) via `lang` metadata |
| `math.md` | LaTeX math formulas |

## Generated Outputs

The integration test suite (`make test`) produces `.docx` and `.pptx` files in `assets/docx/` and `assets/pptx/`. These serve as living examples and are kept in the repository for reference.
