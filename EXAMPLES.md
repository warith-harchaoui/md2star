# md2star Examples & Syntax Reference ⭐️

Welcome to the `md2star` syntax reference! Because `md2star` extends pure Pandoc by fixing annoying layout crashes (especially surrounding bullet lists and `mermaid` blocks), you can format documents dynamically without breaking workflows. 

Check out our pre-rendered examples inside the [`examples/`](examples) folder:
- 📄 **Word Document:** [`comprehensive_document.md`](examples/comprehensive_document.md) ➡️ [`comprehensive_document.docx`](examples/comprehensive_document.docx)
- 📊 **PowerPoint Deck:** [`comprehensive_presentation.md`](examples/comprehensive_presentation.md) ➡️ [`comprehensive_presentation.pptx`](examples/comprehensive_presentation.pptx)

The underlying syntax models for both platforms share the exact same logic.

---

## 1. Title and Subtitles

`md2star` automatically strips the first `# Heading` of your document and securely pushes it into your Office/PDF files as the master `Title` layout metadata. 

If you use `--author`, your author string alongside your localized date constructs the **Subtitle**.

```bash
# How it compiles from CLI
md2docx document.md --author "Someone Great"
```

---

## 2. Dynamic Mermaid Execution

With normal Pandoc, inserting a ````mermaid` fenced code-block breaks conversion. `md2star` completely prevents this! It uses the Python `preprocessing.py` hook to securely convert your structure to high-definition PNGs.

```markdown
Here is our pipeline architecture:

` ` `mermaid
graph LR;
    Raw[Markdown Source] --> Engine[md2star Preprocessor]
    Engine --> Office[DOCX/PPTX]
` ` `
```

> [!TIP] 
> No installation required for Mermaid rendering; `md2star` communicates securely via the open-source `Kroki.io` framework.

---

## 3. Flawless List Formatting

Usually, Markdown writers build unordered lists "glued" directly to the underlying paragraph, ruining output layout by forcing Pandoc to recognize them as inline blocks. `md2star`'s Python AST engine auto-spans these securely so you never have to worry about spacing fixes again!

```markdown
Our company provides:
- Seamless DOCX wrapping 
- Deep PPTX grid-structuring
- Mathematics evaluations
```
*(This will always correctly generate spaced Microsoft bullet items).*

---

## 4. Multi-Column Slides (PPTX Only)

You can cleanly divide your presentation slides into layout halves by using `{.column}` spans.

```markdown
# Section Slide Architecture

This is my left paragraph. 

{.column}

This is my right paragraph. Since we divided it, it rests structurally independent on the far side of the slide natively!
```

---

## 5. LaTeX Mathematical Typings

Use native latex representations inside `$$` tags. During export, Pandoc natively compiles them into Word's or PowerPoint's Mathematical Equation objects natively!

```markdown
We evaluate the standard structural equation:


$$
\exp(i \times \pi)+1 = 0
$$
```

---

## 6. Corporate Bibliographies

When compiling large technical research documents, `md2star` leverages native `.bib` libraries using `--bib`.

```markdown
Standard AI scaling laws have been deeply structured inside causality research metrics [@causality-pearl].
```

**Compilation trigger:**
```bash
md2pptx presentation.md --bib references.bib --bibliography-name "References"
```
The `--bibliography-name` injects an automatic `# References` heading dynamically exactly at the last page of your Office file containing the compiled Chicago/APA list formatting!
