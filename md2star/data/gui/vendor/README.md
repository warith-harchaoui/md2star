# md2star GUI — vendored assets

Every file in this directory is a third-party asset the GUI loads at
runtime. Vendoring them (instead of pointing at a CDN) means:

- The editor works **fully offline** — `md2star gui` does not call out to
  jsdelivr / fonts.googleapis.com / cdn.tailwindcss.com / unpkg.
- A CDN going down (or rate-limiting, or rerouting the URL) cannot
  silently break the editor.
- Reproducible: the bytes you ship today are the bytes the user runs
  in five years.

The trade-off is repo size (~3.4 MB) and a periodic refresh chore
when the upstream packages publish security patches.

## Contents

| File / dir                       | Source                                                   | License        |
|----------------------------------|----------------------------------------------------------|----------------|
| `pdfjs/pdf.min.mjs`              | `pdfjs-dist@4.10.38` (Mozilla, via jsdelivr)             | Apache-2.0     |
| `pdfjs/pdf.worker.min.mjs`       | `pdfjs-dist@4.10.38`                                     | Apache-2.0     |
| `tailwind.js`                    | Tailwind Play CDN with `?plugins=forms,typography`       | MIT            |
| `codemirror.js`                  | esbuild bundle of @codemirror/{state,view,commands,…}    | MIT            |
| `codemirror.js.LEGAL.txt`        | Per-module legal comments, harvested by esbuild           | MIT            |
| `fonts/roboto/`                  | Vendored from the `sprezzature-ui` skill (upstream:      | SIL OFL 1.1    |
|                                  | <github.com/googlefonts/roboto-classic>)                 |                |
| `fonts/roboto-serif/`            | Vendored from the `sprezzature-ui` skill (upstream:      | SIL OFL 1.1    |
|                                  | <github.com/googlefonts/RobotoSerif>)                    |                |
| `fonts/roboto-mono/`             | Vendored from the `sprezzature-ui` skill (upstream:      | SIL OFL 1.1    |
|                                  | <github.com/googlefonts/robotomono>)                     |                |

The GUI follows the **three-Roboto rule**: **Roboto** for sans (UI chrome +
body), **Roboto Serif** for serif (`class="font-serif"` — long-form prose,
rendered Markdown), and **Roboto Mono** for code (the editor pane, `<kbd>`,
`<code>`). Each family is a single self-hosted variable woff2 (weights
100–900). Total vendor tree: ~3.1 MB.

CodeMirror is bundled as **one** file on purpose: shipping the five
sub-packages (`state`, `view`, `commands`, `lang-markdown`, `language`)
separately would give each its own `EditorState` constructor, and
`instanceof` checks across module instances would silently break the
editor. The bundle is built with `esbuild --bundle --format=esm
--minify --target=es2020`, ~488 kB.

## Pinned versions

Bumping any of these is one line of `scripts/vendor_gui.sh` + a
`make vendor`:

```text
PDFJS_VERSION       = 4.10.38
CM_STATE_VERSION    = 6.5.1
CM_VIEW_VERSION     = 6.36.2
CM_COMMANDS_VERSION = 6.7.1
CM_LANG_MD_VERSION  = 6.3.1
CM_LANG_VERSION     = 6.10.8
```

Tailwind Play CDN is unversioned by design (it tracks Tailwind 3 latest);
the `tailwind.js` file is whatever `cdn.tailwindcss.com?plugins=…` served
the last time someone ran `make vendor`.

## Refresh

```bash
make vendor          # idempotent — overwrites this directory
```

Requirements: `curl`, `node`, `npx`. The script lives in
`scripts/vendor_gui.sh`; read it to see exactly what gets fetched and
how the CodeMirror bundle is built.

Commit the refreshed `vendor/` to git so end users don't have to run
`make vendor` themselves — that's the whole point of vendoring.

## Why not unpkg / esm.sh at runtime?

Both work for prototyping. esm.sh in particular is great because it
auto-bundles the package + its deps and emits ES modules. The problem
for `md2star gui`:

- esm.sh is a single point of failure outside our control.
- esm.sh's URL shape (`?bundle&deps=…`) changes occasionally; pinned
  URLs can return a different bundle six months later.
- The user explicitly asked for the editor to work offline.

This directory is the answer.
