# Security model

This document describes md2star's security posture, the threats it
defends against, and the threats it explicitly does NOT. If you find
an issue not covered here, please report it via
<https://github.com/warith-harchaoui/md2star/security/advisories>
(GitHub's private vulnerability disclosure flow) rather than a
public issue.

## TL;DR

- **Offline by default.** No network calls without an explicit flag.
- **Untrusted markdown is largely safe**, with one big caveat: it can
  cause your local LibreOffice / Pandoc to parse files. Bugs in
  those upstreams (rare but real) become bugs in md2star.

## Network behavior

No markdown file you process can cause a network call on its own. The
one phase where md2star itself may reach the network, with no markdown
involvement, is the reference-template fetch, on by default since
v2.5.0.

| Phase                          | Default | Opt-out / opt-in flag        |
|--------------------------------|---------|------------------------------|
| Download `![](https://…)` imgs | DENY    | `--allow-remote-images`      |
| Fetch deraison.ai template     | ALLOW   | `--no-remote-templates`      |
| Hit Ollama for `--lint`        | DENY    | `--lint`                     |
| Render mermaid via `npx`       | local   | (uses local `npx`; no flag)  |

The template fetch happens only when no local `template.{docx,pptx}`
exists, targets the fixed `deraison.ai` host (never a markdown-supplied
URL), caches the result under XDG, and falls back to the bundled
template if the download fails, so it never breaks a conversion.

`--offline` (a top-level flag) is the hard kill-switch: it forces every
network-touching phase off, including the template fetch and the
opt-ins above. Use it in scripts and CI to make the refusal explicit.

When a remote image reference is encountered without the
opt-in flag, md2star logs **one** stderr warning per document
naming the blocked URL and the `--allow-remote-images` flag, then
leaves the markdown reference in place (so pandoc still sees the
URL and embeds it where the output format permits, e.g. HTML).

## Markdown content threats

Markdown is mostly safe to process. The exceptions:

- **Remote images** (gated, see above).
- **Mermaid blocks**: `npx @mermaid-js/mermaid-cli` is invoked
  against the literal markdown source. A maliciously-crafted mermaid
  body could exploit a bug in `mmdc` (we wrap stderr but don't sanitise
  the input). Mitigation: disable mermaid by passing
  `--skip-phase line_pass` if you process untrusted markdown.
- **HTML pass-through**: Pandoc allows raw `<script>` tags in
  markdown. They have no effect in DOCX/PPTX/PDF output (Office
  formats can't execute JavaScript), but if you ever feed the
  pandoc HTML output back into a browser, you'd want to sanitise
  it first. Out of scope for md2star itself.
- **Bibliography**: `--bib` runs `pandoc --citeproc` against the
  supplied `.bib` file. BibTeX parsers have historically had bugs;
  treat third-party `.bib` files with the same care as third-party
  PDFs.

## Process-level security

- **Subprocess timeouts**: Pandoc and soffice run with a bounded
  120 s timeout; mermaid rendering (`mmdc`) is bounded to 60 s. LLM
  calls for `--lint` go through `best-engine-ai-helper`, which applies
  its own request timeout (120 s by default, `SPREZZATURE_LLM_TIMEOUT`
  to override) rather than md2star spawning `ollama` itself. We do not
  enable `shell=True` anywhere.
- **No `eval` / `exec`** on user content.
- **No reads of `$HOME` config files** outside the documented
  `$XDG_CACHE_HOME/md2star/` cache.
- **No writes outside the user's source directory** (CLI mode).

## Dependencies

md2star's external dependencies (Pandoc, LibreOffice, Node, Ollama)
are large surface areas we do not control. Vulnerabilities in any
of them become exposure for md2star users. We recommend:

- Keep Pandoc / LibreOffice up to date via your OS package manager.
- Run `md2star doctor` after upgrading any of them to confirm the
  version md2star is talking to.

## Reporting a vulnerability

Open a private advisory at
<https://github.com/warith-harchaoui/md2star/security/advisories>.

Please include:

- A minimal reproduction (markdown file, command line).
- The md2star version (`md2star --version`).
- The output of `md2star doctor`.
- Your assessment of severity and exploitability.

There is no bug bounty (md2star is an unpaid open-source project),
but we appreciate responsible disclosure and will credit reporters
in `CHANGELOG.md` if they wish.
