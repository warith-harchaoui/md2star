# md2star — Examples & Syntax Reference ⭐️

Welcome to the `md2star` syntax reference! Because `md2star` extends pure Pandoc by fixing annoying layout issues (especially surrounding bullet lists and `mermaid` blocks), you can format documents dynamically without breaking workflows.

Check out our pre-rendered examples inside the [`tests/examples/`](tests/examples) folder:
- 📄 **Word Document:** [`comprehensive_document.md`](tests/examples/comprehensive_document.md) ➡️ [`comprehensive_document.docx`](tests/examples/comprehensive_document.docx)
- 📊 **PowerPoint Deck:** [`comprehensive_presentation.md`](tests/examples/comprehensive_presentation.md) ➡️ [`comprehensive_presentation.pptx`](tests/examples/comprehensive_presentation.pptx)
- 🇫🇷 **French Document:** [`guide_complet_document_fr.md`](tests/examples/guide_complet_document_fr.md) ➡️ [`guide_complet_document_fr.docx`](tests/examples/guide_complet_document_fr.docx)
- 🎨 **Branded Slides:** [`branded_slides.md`](tests/examples/branded_slides.md) + [`Presentation1.pptx`](tests/examples/Presentation1.pptx) ➡️ [`branded_slides.pptx`](tests/examples/branded_slides.pptx)

To compile all examples at once:
```bash
cd tests/examples && ./run.sh
```

---

## 1. Title and Subtitles

`md2star` automatically extracts the first `# Heading` and uses it as the document **Title** metadata. If you use `--author`, the author string alongside the localized date constructs the **Subtitle**.

```bash
md2docx document.md --author "Someone Great"
```

The date is automatically localized based on the detected language:
- 🇫🇷 French → `dimanche 10 mai 2026`
- 🇪🇸 Spanish → `domingo, 10 de mayo de 2026`
- 🇩🇪 German → `Sonntag, 10. Mai 2026`

---

## 2. Mermaid Diagrams

Standard Pandoc breaks on ````mermaid` fenced code blocks. `md2star` automatically converts them to high-resolution PNGs using the Mermaid CLI locally — no data leaves your machine.

```markdown
Here is our pipeline architecture:

` ` `mermaid
graph LR;
    Raw[Markdown Source] --> Engine[md2star Preprocessor]
    Engine --> Office[DOCX/PPTX]
` ` `
```

> [!TIP]
> Mermaid rendering requires Node.js (≥16) on your PATH. The CLI is auto-installed via `npx` on first use.

---

## 3. Flawless List Formatting

Markdown writers often glue unordered lists directly to paragraphs, which breaks Pandoc output by forcing inline blocks. `md2star`'s Python AST engine automatically inserts the correct spacing so bullet lists always render cleanly.

```markdown
Our company provides:
- Seamless DOCX wrapping
- Deep PPTX grid-structuring
- Mathematics evaluations
```

*(This will always generate properly spaced Microsoft bullet items.)*

---

## 4. Multi-Column Slides (PPTX Only)

Divide your presentation slides into layout halves using `{.column}` spans:

```markdown
# Section Slide Architecture

This is my left paragraph.

{.column}

This is my right paragraph, structurally independent on the right side of the slide.
```

---

## 5. LaTeX Mathematics

Use native LaTeX expressions inside `$$` tags. Pandoc compiles them into Word / PowerPoint native Mathematical Equation objects.

```markdown
We evaluate the standard structural equation:

$$
e^{i \times \pi}+1 = 0
$$
```

---

## 6. Corporate Bibliographies

For large technical documents, `md2star` leverages native `.bib` libraries via `--bib`:

```markdown
Standard AI scaling laws have been deeply structured inside causality research metrics [@causality-pearl].
```

**Compilation:**
```bash
md2pptx presentation.md --bib references.bib --bibliography-name "References"
```

The `--bibliography-name` flag injects an automatic heading at the end of your document containing the compiled citation list.

---

## 7. Branded Templates (PPTX)

Use any custom `.pptx` as a reference template to brand your slides. If the template already has standard Pandoc layout names (`Title Slide`, `Title and Content`, etc.), use it directly:

```bash
md2pptx slides.md --reference-doc Presentation1.pptx
```

For corporate templates with non-standard layout names, use the
[md2star-adapt](https://github.com/warith-harchaoui/md2star-adapt) sibling
tool to build a compatible reference doc, then point md2pptx at it via
`--reference-doc branded_ref.pptx`.

---

## 8. Language Detection & Date Localization

`md2star` automatically detects the language of your content and localizes dates accordingly — no configuration needed. Supported languages include French, Spanish, German, Italian, Portuguese, Dutch, Russian, Chinese, and Japanese.

```markdown
# Test du langage

J'ai un "je ne sais quoi" que je ne connais pas.
```

```bash
md2docx document.md --author "Utilisateur"
# → Subtitle: "Utilisateur, dimanche 10 mai 2026"
```

You can override with explicit metadata:
```yaml
---
lang: fr-FR
date_format: "%A %e %B %Y"
---
```
