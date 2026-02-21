# md2star ✍️⭐️

> **An efficient bridge from Markdown to docx, Google Doc, pptx, Google Slides and PDFs.**

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Lua](https://img.shields.io/badge/lua-5.3-blue.svg)
![Bash](https://img.shields.io/badge/bash-4+-lightgray.svg)
![PowerShell](https://img.shields.io/badge/powershell-7+-blue.svg)

`md2star` is a streamlined, cross-platform toolset designed for authors who demand the speed of **Markdown** and the corporate formats of **Microsoft Office** and **PDF** layouts. By combining the power of **Pandoc** with curated styling logic, it automates the tedious parts of document preparation.

---

## ✨ Features

- **🚀 Frictionless Conversion for your ideas**: Write your ideas in Markdown files in your favorite lightweight text editor (`emacs`, `vim`, `Sublime Text`, `Atom`, `Obsidian`, etc.), and let our tool instantly generate `.docx` and `.pptx` documents.
- **📄 Instant PDF Export**: Every conversion automatically produces a high-fidelity PDF. 
  > [!TIP]
  > For an "Office" look without LaTeX, set `PANDOC_PDF_ENGINE=typst` or `weasyprint` if installed.
- **🔢 LaTeX Math Support**: Robust rendering of complex formulas in both documents and slides.
- **🏷️ Intelligent Metadata**: 
  - Automatic **Title Extraction** from your first `# Heading`.
  - Smart **Subtitle Injection** for Author, Date, and Category metadata.
- **📚 Scientific-Ready**: Native **BibTeX** integration for professional research citations (for corporate environment, not academic publications).
- **🌍 Global Localization**: Multi-language support with automatic date formatting (e.g., `fr-FR`, `en-US`).
- **☁️ Cloud Integrated**: Optional `gup` utility for direct upload and conversion to **Google Docs** and **Google Slides**. Requires a target `folder_id` from your Drive URL (see [gup/README.md](gup/README.md) for setup).

---

## 🛠️ Installation

### 🍎 macOS & 🐧 Linux
```bash
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star
make install
```

### 🪟 Windows
```powershell
git clone https://github.com/warith-harchaoui/md2star.git
cd md2star
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

---

## 📖 Usage Guide

### 1. Simple Export
```bash
md2docx myfile.md
```
*Generates `myfile.docx` and `myfile.pdf` using default metadata.*

### 2. Scientific Paper (with Citations and Math Formulas)
```bash
md2docx work.md --author "Dr. Renegade Researcher" --bib references.bib --lang en-US
```

### 3. Presentation Slides
```bash
md2pptx slides.md --author "Speaker Name"
```

---

## 🧪 Quality & Reliability

![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

`md2star` is built for reliability. Our automated test suite covers:
- [x] **Metadata Accuracy**: Title, Author, and Subtitle verification.
- [x] **Cross-Format Integrity**: Parity between DOCX and PPTX outputs.
- [x] **Bibliography Rendering**: Using the curated [deraison.bib](assets/deraison.bib) snapshot.
- [x] **Locale Localization**: French date rendering and international headers.

To run the suite yourself:
```bash
make test
```

---

## ⚙️ Customization

### Metadata Defaults
Adjust your global defaults in `pandoc/metadata.yaml`:
```yaml
author: "Your Default Name"
date_format: "%A, %e %B %Y"
lang: "en-US"
```

`date_format` uses an `strftime()`-style format string.
See [C/POSIX date-time formatting documentation](https://pubs.opengroup.org/onlinepubs/9699919799/functions/strftime.html) for more information.

`lang` uses a BCP 47 language tag (e.g., `en-US`, `fr-FR`).
See [RFC 5646 documentation](https://datatracker.ietf.org/doc/html/rfc5646) for more information.

### Styling Templates
Modify the master templates in `assets/` to change fonts, margins, or logos globally:
- [template.docx](assets/template.docx)
- [template.pptx](assets/template.pptx)

---

## 📦 Related Projects

- **[Pandoc](https://pandoc.org/)**: The engine that makes document conversion universal.
- **[Obsidian](https://obsidian.md/)**: Our recommended environment for writing high-fidelity Markdown.
- **[Zotero](https://www.zotero.org/)**: The ideal research companion for managing your `.bib` bibliographies.
- **[deraison.ai/ai-books](https://deraison.ai/ai-books)**: Some nice AI references (for the sake of giving an example only)

---

## 📄 License

Distributed under the **MIT License**. Crafted with precision for the modern author.
