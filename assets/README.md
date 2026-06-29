# assets/

Sample Markdown inputs used by the integration test suite, the example
runner (`run.sh`), and the documentation in `EXAMPLES.md`.

## Layout

```
assets/
├── docx/                   # DOCX test fixtures (Markdown sources)
│   ├── basic.md            # Minimal document — title extraction
│   ├── with_author.md      # --author injection into subtitle
│   ├── with_bib.md         # Bibliography with --bib + --bibliography-name
│   ├── with_lang.md        # Localised dates (French)
│   └── math.md             # LaTeX math formulas
├── pptx/
│   └── example.md          # Extensive PPTX demo (slides, lists, images)
├── logo.png                # Project logo (referenced from README)
├── references.bib          # BibTeX entries used by with_bib.*
└── run.sh                  # Batch compiler: builds every sample .docx / .pptx
```

The corresponding `.docx` / `.pptx` outputs are committed as living
examples (small ~2 MB DOCX, one larger PPTX). They are regenerated
in-place by `run.sh` and by the integration test suite; commit any
intentional changes you spot in the diff. To rebuild them locally:

```bash
cd assets
./run.sh
```

## Reference templates

The default `template.docx` and `template.pptx` are shipped inside the
Python wheel at `md2star/data/template.{docx,pptx}`. Edit those files (not
copies in `assets/`) to change the global default fonts, margins, or
branding, then `make reinstall` so the change takes effect for already-
installed CLIs.

For per-project branding, drop a `template.{docx,pptx}` next to your input
`.md` and md2star will pick it up automatically as `--reference-doc`. If
neither exists, md2star fetches the default once from
`https://deraison.ai/template.{docx,pptx}` and caches it next to your
Markdown.
