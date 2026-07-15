# Footnotes Demonstration

## Introduction
This document shows how **md2star** carries Markdown footnotes straight
through to native Microsoft Word footnotes. No special preprocessing is
involved — Pandoc's default Markdown reader has the `footnotes`
extension enabled, so the standard syntax simply works and Word renders
each note at the bottom of the page with a clickable superscript marker.

## 1. Reference-style Footnotes
The most common form places a short label at the point of reference and
defines the note body later in the source.[^bench] The label is only an
identifier — Word renumbers the visible markers automatically, so the
name you pick never appears in the output.[^label]

A second reference in the same paragraph proves the numbering is
sequential and independent of label order.[^adv]

[^bench]: Measured on the internal benchmark suite, 2026-Q2 run.
[^label]: Labels may be numeric (`[^1]`), words (`[^bench]`), or hyphenated (`[^note-a]`).
[^adv]: See the red-team appendix for the full adversarial protocol.

## 2. Inline Footnotes
When the note is short, the inline form keeps definition and reference
together on one line.^[Ten seeds, variance under one percent.] This is
handy for quick asides that would clutter the source if defined
separately.

## 3. Footnotes Inside Lists
Footnotes attach cleanly to list items as well:

- First finding, with a supporting citation.[^first]
- Second finding, unqualified.
- Third finding, with a caveat.[^third]

[^first]: Derived from the 2026-Q1 cohort, n = 1,204.
[^third]: Holds only under the stated temperature range.

## Conclusion
Because footnotes are a native Pandoc feature, they behave identically
to every other Markdown element in the pipeline — extract the title,
localize the date, and let Pandoc emit the `word/footnotes.xml` part
that Word reads back as true bottom-of-page footnotes.
