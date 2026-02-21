# md2star ✍️⭐️

> **An efficient bridge from Markdown to docx, Google Doc, pptx, Google Slides and PDFs.**

`md2star` is a streamlined, cross-platform toolset designed for authors who demand the speed of **Markdown** and the professionalism of **Microsoft Office** and **PDF** layouts. By combining the power of **Pandoc** with curated styling logic, it automates the tedious parts of document preparation.

---

## ✨ Features

- **🚀 High-Speed Conversion**: Instant `.docx` and `.pptx` generation from your Markdown source.
- **📄 Instant PDF Export**: Every conversion automatically produces a high-fidelity PDF for easy sharing.
- **🏷️ Intelligent Metadata**: 
  - Automatic **Title Extraction** from your first `# Heading`.
  - Smart **Subtitle Injection** for Author, Date, and Category metadata.
- **📚 Academic-Ready**: Native **BibTeX** integration for professional research citations.
- **🌍 Global Localization**: Multi-language support with automatic date formatting (e.g., `fr-FR`, `en-US`).
- **☁️ Cloud Integrated**: Optional `gup` utility for direct upload and conversion to **Google Docs** and **Google Slides** thanks to you OAuth credentials (see [gup/README.md](gup/README.md) for more information).

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

### 2. Research Paper (with Citations)
```bash
md2docx paper.md --author "Dr. Researcher" --bib references.bib --lang en-US
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
date_format: "%d %B %Y"
lang: "en-US"
```

### Styling Templates
Modify the master templates in `assets/` to change fonts, margins, or logos globally:
- [template.docx](assets/template.docx)
- [template.pptx](assets/template.pptx)

---

## 📦 Related Projects

- **[Pandoc](https://pandoc.org/)**: The engine that makes document conversion universal.
- **[Obsidian](https://obsidian.md/)**: Our recommended environment for writing high-fidelity Markdown.
- **[Zotero](https://www.zotero.org/)**: The ideal research companion for managing your `.bib` bibliographies.
- **[deraison.ai/ai-books](https://deraison.ai/ai-books)**: The research hub powering our sample AI bibliographies (for the sake of giving an example only)

---

## 📄 License

Distributed under the **MIT License**. Crafted with precision for the modern author.
