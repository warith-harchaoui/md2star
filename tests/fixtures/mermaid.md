# Mermaid diagram fixture

This fixture exercises md2star's local mermaid rendering path. The
diagram is rendered via `npx -y @mermaid-js/mermaid-cli`; the
resulting PNG is cached in `$XDG_CACHE_HOME/md2star/mermaid/` and
embedded as a normal image reference in the produced DOCX/PPTX/PDF.

When Node.js is not on `PATH`, the rendering quietly falls back to
keeping the raw code fence (so the document still converts; only
the diagram is missing). The integration test marks the mermaid
case as `pytest.skip` when `node` is unavailable.

## Architecture

```mermaid
flowchart LR
  md[Markdown source] --> pre[Preprocessor]
  pre --> pandoc[Pandoc]
  pandoc --> docx[DOCX]
  docx --> soffice[soffice --headless]
  soffice --> pdf[PDF]
```
