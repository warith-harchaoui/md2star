# pandoc/

Pandoc configuration files used by md2star.

## Structure

```
pandoc/
├── defaults/
│   ├── docx-star.yaml   # Pandoc defaults for DOCX conversion
│   └── pptx-star.yaml   # Pandoc defaults for PPTX conversion
├── filters/
│   └── md2star.lua       # Lua filter: title extraction, subtitle injection, heading-ID cleanup
└── metadata.yaml         # Global metadata (author, date_format, lang)
```

## How it fits together

During `make install`, the installer (`scripts/install.sh`):

1. Copies these files into `~/.pandoc/` (the Pandoc user-data directory).
2. Rewrites the defaults YAML files with **absolute paths** so they work from any working directory.

The CLI wrappers (`md2docx`, `md2pptx`) then invoke Pandoc with:

```bash
pandoc --defaults docx-star.yaml input.md -o output.docx
```

## Key files

### `metadata.yaml`

Global defaults for `author`, `date_format` (strftime pattern), and `lang` (BCP 47 tag).  The placeholder author `"EMANON"` is hidden by the Lua filter.

### `md2star.lua`

A Pandoc Lua filter that:

- Extracts the first `# Heading` as the document title.
- Hides the "EMANON" placeholder author.
- Localises the date using the `lang` tag.
- Injects an "Author, Date" subtitle styled as `custom-style: Subtitle`.
- Strips heading IDs to avoid clutter in Office output.

### `docx-star.yaml` / `pptx-star.yaml`

Pandoc defaults files that wire up the filter, metadata, and reference templates in a single `--defaults` flag.
