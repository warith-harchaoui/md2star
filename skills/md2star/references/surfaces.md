# md2star non-CLI surfaces

md2star exposes the same conversion pipeline through five surfaces. The CLI is
the default; reach for the others when the situation calls for it.

## 1. CLI — argparse (default) and click

- **argparse** (`md2docx`/`md2pptx`/`md2pdf`/`md2star …`): the primary surface,
  including the Pandoc `--help` passthrough. Documented in `cli-reference.md`.
- **click** (`md2star-x`): a modern click front-end over the same conversions
  (`md2star-x docx|pptx|pdf|gui|doctor`). Same delegation to the core pipeline;
  use it when a click-style UX (grouped commands, rich `--help`) is preferred.

## 2. HTTP API — FastAPI (`md2star[api]`)

```bash
pip install 'md2star[api]'
md2star-api                                   # serves on :8000, docs at /docs
curl -F 'file=@report.md' 'http://localhost:8000/convert?fmt=docx' -o out.docx
```

Endpoints: `GET /health`, `GET /doctor`, `POST /convert?fmt=docx|pptx|pdf`
(multipart upload). Use when another service needs conversions over HTTP.

## 3. MCP server — FastAPI-MCP (`md2star[mcp]`)

```bash
pip install 'md2star[mcp]'
md2star-mcp                                   # Model Context Protocol server
```

Wraps the FastAPI app so an MCP-capable agent (Claude Desktop, etc.) can call
`convert` / `doctor` as tools. Use when the agent host speaks MCP rather than
shelling out to the CLI.

## 4. Bundled GUI — `md2star gui`

Localhost-only Overleaf-style editor (Markdown left, live PDF preview right,
folder browser, template upload, draft autosave). Ships in the core wheel; the
`pip install 'md2star[gui]'` command is a self-documenting alias for the same
wheel. Use when a human wants an interactive editor.

## 5. Minimal GUI — `minimal-gui/server.py`

A single-file, zero-dependency stdlib preview server (`minimal-gui/`) that
exposes `md → PDF` on one `/render` endpoint. Run `python3 minimal-gui/server.py`.
Use as a hackable, embeddable minimal preview when the full GUI is overkill.

## Choosing a surface

| Situation | Surface |
|-----------|---------|
| Agent can shell out | CLI (argparse or click) |
| Human wants an editor | GUI (`md2star gui`) |
| Embeddable minimal preview | `minimal-gui/server.py` |
| Another service needs HTTP | API (`md2star-api`) |
| Agent host speaks MCP | MCP (`md2star-mcp`) |
