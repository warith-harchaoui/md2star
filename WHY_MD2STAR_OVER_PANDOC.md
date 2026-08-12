# Why md2star over "just use Pandoc"

> The honest case for md2star existing at all, given that it *is* Pandoc
> underneath. Written to answer the recurring question: "This is a wrapper
> around Pandoc, why not just tell people to run Pandoc?"
>
> Current with the shipped tool (as of v2.11.0): the forward path is still
> Pandoc plus a styling layer, but the tool now also runs the *reverse* path
> and guarantees a round-trip: two places where "just use Pandoc" has no
> answer.

## The one-sentence answer

Pandoc is a **converter**; md2star is a **deliverable**. Pandoc turns
Markdown into a valid `.docx`; md2star turns Markdown into a `.docx` you can
send to a client without opening Word, and reads it back into editable
Markdown when it comes home. The gap between "valid" and "shippable," and the
gap between "one-way export" and "reversible source of truth," are exactly the
product.

## Concede the obvious first

md2star does not out-Pandoc Pandoc. Pandoc is the universal document engine,
it is world-class, and md2star **calls it** for the actual conversion. On the
things Pandoc is built for (breadth of formats, citation processing (CSL),
LaTeX-native math, a clean readers/writers architecture), Pandoc wins and
md2star inherits those wins rather than competing with them. Any defense that
pretends otherwise is dishonest and loses the room.

So the claim is narrow and defensible: **for the specific job of "Markdown
source of truth to a polished DOCX/PPTX/PDF, offline, with clean git diffs,
and back again," md2star saves you the 200 lines of glue, the template, the
reverse-extraction pipeline, and the toolchain archaeology that raw Pandoc
makes you build yourself.**

## What raw Pandoc actually leaves on your desk

Run `pandoc report.md -o report.docx` and you get a technically-correct file
that still needs hand-editing before it is shareable:

1. **No template, no brand.** Default Word styling: Calibri, no cover, no
   heading hierarchy that matches your org. md2star ships a curated reference
   `.docx`/`.pptx` so the output looks deliberate on the first run.
2. **Tables leak.** The classic v1.x-era bug, cells collapsing into a
   vertical paragraph dump, is precisely the kind of Pandoc+template
   interaction md2star has already debugged and pinned to a known-good
   baseline (`postprocess.py:strip_table_normal_for_pdf`, fixed in v2.0.0).
   You do not get to skip that debugging with raw Pandoc; you just get to do
   it yourself.
3. **Diagrams don't render.** Mermaid in a fenced block is inert text to
   Pandoc. md2star renders it to a cached PNG with a branded palette and
   embeds it. That is a whole pre-processing stage a bare `pandoc` invocation
   does not have.
4. **PDF means "install LaTeX."** Pandoc's default PDF path is a full LaTeX
   toolchain. md2star routes DOCX → LibreOffice instead, so PDF works without
   a TeX install: a materially smaller ask on a colleague's machine.
5. **No localized dates, sane table widths, list spacing.** The hundred small
   typographic defaults that separate "export" from "document" are the curated
   styling layer, not the converter (a 10-language date/locale layer, A4-aware
   image caps, PPTX slide isolation).
6. **You own the toolchain glue.** Detecting pandoc/soffice/node/ollama, giving
   a real error when they're missing (`md2star doctor`), wiring image
   embedding and bibliography injection: with raw Pandoc that is your shell
   script to write and maintain across macOS/Linux/Windows.

None of these are Pandoc *flaws*. They are deliberately out of scope for a
universal converter. md2star is the opinionated layer that fills them in for
one well-chosen niche.

## The place "just use Pandoc" has no answer: the round trip

This is the strongest part of the case and the newest, so state it plainly.

**md2star is reversible, and proves it in CI.** A finished document is not a
dead end you have to retype: `md2star twin <file>` reads **any PDF, or
anything LibreOffice can convert to one**, back into an *editable* `<stem>.md`
plus an `assets/` folder. Tables return as GFM pipe tables, every embedded
raster is scraped out and re-linked, and (opt-in, `[ocr]`) node-and-edge
figures are re-authored as **Mermaid** via a target-matching eyeball loop:
render a candidate with the same `mmdc` the forward path uses, compare it
against the scraped original with a local vision model, iterate until it
matches, keep the original PNG as a commented fallback so ground truth is
never lost.

Pandoc does not do this. Its readers/writers are format-to-format on
structured inputs; it does not OCR a scanned PDF, scrape rasters, or
reconstruct diagrams. Reaching for "just use Pandoc" here means reaching for
an entirely *different* toolchain (Kreuzberg, OCR, a VLM, and a
render/compare loop), which is exactly the pipeline md2star already assembles
and tests.

And the forward and reverse paths are wired together into a **guarantee**, not
a vibe: `md → docx → pdf → text` is the exact identity `g(f(x)) = x` for
prose, bullet lists, multi-page docs, and footnotes, enforced by
`tests/test_roundtrip_ocr.py` on a real LibreOffice + Kreuzberg toolchain in
CI; and `md → docx → md` reaches an idempotent fixed point (`g(g(x)) = g(x)`).
"Your content is trapped in a binary" is the standard, correct fear about
Office formats. md2star is the answer to it, and that answer is *not* a
Pandoc flag.

## The reproducibility argument

A raw-Pandoc workflow is a personal shell script: your flags, your template
path, your image-render step, your PDF route, your reverse-extraction hack,
undocumented and unversioned. md2star packages that decision set as an
installable tool with a pinned template, tests, and CI across four Python
versions and three OSes. "It works on my machine" becomes "it works from
`pipx install md2star`." For a small async team or one person across several
devices, that portability *is* the value.

**One pipeline, many front-ends.** The same `_convert` code path is reachable
from four surfaces: the argparse CLIs (`md2docx`/`md2pptx`/`md2pdf`), the
click CLI (`md2star-x`), a FastAPI server (`md2star-api`, plus a browser
bench at `/gui` and a full Overleaf-style editor at `md2star gui`), and an MCP
server (`md2star-mcp`) so an agent can call it as a tool. Raw Pandoc gives you
one CLI; wiring an HTTP/MCP/GUI surface over it consistently, so they can't
drift, is again glue you'd own yourself.

## Where Pandoc is the right answer (say so)

- You need a format or conversion path md2star doesn't expose: reach for
  Pandoc directly, it's the superset.
- You already have your own template + PDF toolchain and are happy owning the
  glue: md2star would just be indirection.
- Citation-heavy academic work with a LaTeX-native PDF: Pandoc (or Quarto /
  Overleaf) is a better fit than md2star's styling-first path.
- You only ever go *one way* and never need the document back as Markdown:
  the reverse-path argument doesn't apply to you, so weigh md2star on the
  styling layer alone.

Recommending the right tool builds the credibility that makes the rest of the
argument land. md2star sits *on top of* Pandoc; it never asks you to give
Pandoc up.

## Bottom line

"Just use Pandoc" is right about the engine and wrong about the job. Pandoc
gets you a file that parses; md2star gets you a document you'd put your name
on: reproducibly, offline, from a Markdown source that stays greppable and
diff-friendly, and that you can *get back* when the document is all you have
left. The wrapper is not the weakness; the curated, tested, cross-platform,
round-trip-guaranteed opinion *is* the product.
