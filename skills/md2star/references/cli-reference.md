# md2star CLI reference

Full command surface for the `md2star` skill. Read this when a conversion needs
more than the defaults (branding, citations, offline, phase control).

## Commands and aliases

| Alias | Subcommand | Output | Extra requirement |
|-------|------------|--------|-------------------|
| `md2docx f.md` | `md2star docx f.md` | `.docx` | Pandoc |
| `md2pptx f.md` | `md2star pptx f.md` | `.pptx` | Pandoc |
| `md2pdf f.md`  | `md2star pdf f.md`  | `.pdf`  | Pandoc + LibreOffice (`soffice`) |
| —              | `md2star gui`       | browser editor | LibreOffice for live preview |
| —              | `md2star twin f.pdf` | editable Markdown twin | `[ocr]` extra |
| —              | `md2star audit d.pptx [--json] [--strict]` | layout defects, exit 1 on one | `[pptx]` extra |
| —              | `md2star doctor [--json]` | environment report | — |
| —              | `md2star templates {list,path}` | template introspection | — |
| —              | `md2star cache-dir` / `clear-cache` | cache management | — |

## Shared flags (all three converters)

- `-o, --output OUT` — output path (default: input stem + format extension).
- `--author NAME` — document author metadata.
- `--bib PATH` — BibTeX file; enables Pandoc `citeproc` for `[@key]` references.
- `--bibliography-name NAME` — heading for the generated references section.
- `--lang CODE` — language (e.g. `en`, `fr`); auto-detected if omitted.
- `--date DATE` — document date metadata.
- `--lint` / `--no-lint` — opt-in local-LLM pass (syntax fixes + empty-alt
  drafting). OFF by default so conversions stay deterministic.
- `--reference-doc PATH` — brand output with a `template.docx`/`template.pptx`.
- `--skip-phase NAME` — skip one preprocessing phase (see below).
- `--offline` — never touch the network (no remote templates, no remote images).
- `--no-remote-templates` — do not fetch the deraison.ai default template.
- `--allow-remote-images` — download `http(s)://` images for embedding.
- `-v/--verbose`, `-q/--quiet`, `-V/--version`. `-h` works as well as `--help`,
  on `md2star` and on every subcommand.

## pptx-only flags (template-intelligent assembly)

- `--smart-layout` — map each slide onto a designer template's own named
  layouts instead of Pandoc's ~7 generic ones. Needs `--template` and the
  `[pptx]` extra.
- `--template designer.pptx` — the designer's own deck (not md2star's).
- `--reference-slides` — clone the template's own example pages, not just their
  background.
- `--no-visual-confirm` — skip the VLM visual tie-break (cheaper).
- `--eyeball-iterations N` — N bounded revision passes after assembly.

## Pandoc passthrough

Any flag md2star does not define is forwarded to Pandoc **verbatim, and last**,
so it overrides md2star's own choices: `md2docx report.md --toc
--metadata=subject:Q3`. The short flags md2star defines (`-o`, `-v`, `-q`,
`-V`) are md2star's — spell Pandoc's long form to forward it (`--variable`, not
`-V`). Put the input file before the flags when an unknown option takes a
separate value: `--metadata key:val in.md` is ambiguous to any parser, while
`--metadata=key:val` is not.

## Template resolution order

1. `--reference-doc` if given.
2. A local `template.docx` / `template.pptx` next to the input.
3. XDG-cached copy from a previous run.
4. The deraison.ai default (fetched + cached) unless `--no-remote-templates`
   / `--offline`.
5. The bundled template shipped in the wheel (always-available fallback).

## Preprocessing pipeline (phases)

Markdown is transformed before Pandoc sees it: image-width normalization,
remote-image embedding (opt-in), HTML `<table>` → pipe-table conversion, Mermaid
rendering, math handling, and the opt-in LLM lint. Each phase is skippable with
`--skip-phase NAME`; run with `-v` to see the phase list for the current file.

## Exit codes

`0` success · `1` conversion/tool failure (missing Pandoc/LibreOffice, bad
template) · `2` bad CLI usage · `130` interrupted (Ctrl-C).
