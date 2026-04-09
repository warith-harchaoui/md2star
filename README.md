# md2star ✍️⭐️

> **md2star** is an efficient bridge from Markdown to docx and pptx.

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Lua](https://img.shields.io/badge/lua-5.3-blue.svg)
![Bash](https://img.shields.io/badge/bash-4+-lightgray.svg)
![PowerShell](https://img.shields.io/badge/powershell-7+-blue.svg)

`md2star` is a streamlined, cross-platform toolset designed for authors who demand the speed of **Markdown** and the corporate formats of **Microsoft Office** (`.docx` and `.pptx`). By combining the power of **Pandoc** with curated styling logic, it automates the tedious parts of document preparation.

---

## ✨ Features

- **🚀 Frictionless Conversion for your ideas**: Write your ideas in Markdown files in your favorite lightweight text editor (`emacs`, `vim`, `Sublime Text`, `Atom`, `Obsidian`, etc.), and let our tool instantly generate `.docx` and `.pptx` documents following the corporate and favorite style files of your choice.
- **📐 LaTeX Math Support**: Robust rendering of complex formulas in both documents and slides.
- **🏷️ Intelligent Metadata**: 
  - Automatic **Title Extraction** from your first `# Heading`.
  - Smart **Subtitle Injection** for Author, Date, and Category metadata.
- **📚 Scientific-Ready**: Native **BibTeX** integration for professional research citations (for corporate environment, not academic publications) which is the only way to manage great quantities of references to the best of my knowledge in a reliable fashion.

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
*Generates `myfile.docx`*.

### 2. Scientific Paper (with Citations and Math Formulas)
```bash
md2docx work.md --author "Dr. Renegade Researcher" --bib references.bib --bibliography-name "References" --lang en-US
```
*Generates `work.docx`*.


### 3. Presentation Slides
```bash
md2pptx slides.md --author "Speaker Name"
```
*Generates `slides.pptx`*.

---

## 💡 Examples
See `md2star` in action! Below are the actual `.docx` and `.pptx` files generated dynamically during our test suite from sample Markdown files:

**Word Documents Examples**
- Basic Title [assets/docx/basic.docx](assets/docx/basic.docx) *(from [basic.md](assets/docx/basic.md))*
  ```bash
  md2docx assets/docx/basic.md
  ```
- Author Injected [assets/docx/with_author.docx](assets/docx/with_author.docx) *(from [with_author.md](assets/docx/with_author.md))*
  ```bash
  md2docx assets/docx/with_author.md --author "Tester"
  ```
- Bibliography [assets/docx/with_bib.docx](assets/docx/with_bib.docx) *(from [with_bib.md](assets/docx/with_bib.md))*
  ```bash
  md2docx assets/docx/with_bib.md --bib "assets/references.bib" --bibliography-name "References"
  ```
- Language & Date (French) [assets/docx/with_lang.docx](assets/docx/with_lang.docx) *(from [with_lang.md](assets/docx/with_lang.md))* 
  ```bash
  md2docx assets/docx/with_lang.md --author "User"
  ```
- Math Formulas [assets/docx/math.docx](assets/docx/math.docx) *(from [math.md](assets/docx/math.md))*
  ```bash
  md2docx assets/docx/math.md
  ```

**PowerPoint Slides Examples**
- Extensive Example [assets/pptx/example.pptx](assets/pptx/example.pptx) *(from [example.md](assets/pptx/example.md))*
  ```bash
  md2pptx assets/pptx/example.md
  ```

---

## 🗂️ Project Structure

```
md2star/
├── assets/                  # Example Markdown, templates, and generated outputs (see assets/README.md)
│   ├── docx/                #   DOCX test fixtures (basic, author, bib, lang, math)
│   ├── pptx/                #   PPTX test fixtures
│   ├── template.docx        #   Reference styling template for DOCX
│   └── template.pptx        #   Reference styling template for PPTX

├── pandoc/                  # Pandoc configuration
│   ├── defaults/            #   YAML defaults (docx-star, pptx-star)
│   ├── filters/md2star.lua  #   Lua filter (title, subtitle, locale)
│   ├── metadata.yaml        #   Global metadata defaults
│   └── README.md
├── scripts/                 # Install/uninstall/test shell scripts
│   ├── install.sh
│   ├── uninstall.sh
│   ├── preprocessing.py
│   ├── test.sh
│   └── README.md
├── tests/                   # Python unit tests (pytest; see tests/README.md)
│   └── test_preprocessing.py
├── Makefile
└── README.md
```

---

## 🧪 Quality & Reliability

![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

`md2star` is built for reliability. Our automated test suite covers:
- [x] **Metadata Accuracy**: Title, Author, and Subtitle verification.
- [x] **Cross-Format Integrity**: Parity between DOCX and PPTX outputs.
- [x] **Bibliography Rendering**: Using the curated [references.bib](assets/references.bib) snapshot.
- [x] **Locale Localization**: French date rendering and international headers.

### Integration tests (shell)

Requires **Pandoc** installed:
```bash
make test
```

### Unit tests (Python)

Requires **pytest** (`pip install pytest`):
```bash
python -m pytest tests/ -v
```

For more details, see [tests/README.md](tests/README.md).

---

## ⚙️ Customization

### Metadata Defaults
Adjust your global defaults in `pandoc/metadata.yaml`:
```yaml
author: "Your Default Name"
date_format: "%A, %e %B %Y"
lang: "en-US"
```

Chosen conventions:

  + `date_format` uses an `strftime()`-style format string.
See [C/POSIX date-time formatting documentation](https://pubs.opengroup.org/onlinepubs/9699919799/functions/strftime.html) for more information.

  + `lang` uses a BCP 47 language tag (e.g., `en-US`, `fr-FR`).
See [RFC 5646 documentation](https://datatracker.ietf.org/doc/html/rfc5646) for more information.

### Styling Templates
Modify the master templates in `assets/` to change fonts, margins, or logos globally:
- [template.docx](assets/template.docx)
- [template.pptx](assets/template.pptx)

During installation, these are copied to `~/.pandoc/` (or `%APPDATA%\pandoc` on Windows). See [assets/README.md](assets/README.md) for details.

---

## 📚 Developer Documentation

For contributors and advanced users interested in the inner workings of our Python logic and AST parsing hooks, check our internal API guides:
- [Developer Guide](docs/developer_guide.md)

---

## 📦 Related Projects

- **[Pandoc](https://pandoc.org/)**: The engine that makes document conversion universal.
- **[Obsidian](https://obsidian.md/)**: Our recommended environment for writing high-fidelity Markdown.
- **[Zotero](https://www.zotero.org/)**: The ideal research companion for managing your `.bib` bibliographies.

---

## 🔧 Troubleshooting

| Issue | Solution |
|------|----------|
| `md2docx: command not found` | Add `~/.local/bin` to your PATH (see install output) |
| `pandoc: command not found` | Install [Pandoc](https://pandoc.org/installing.html) |
| French dates show in English | Ensure `fr_FR.UTF-8` locale is installed (`locale -a`) |
| PPTX template layout warnings | Normal if template lacks standard slide layouts; output still valid |

---

## 🤝 Contributing

1. Fork & clone the repository.
2. Run `make install` to set up locally.
3. Make your changes.
4. Run `make test` and `python -m pytest tests/ -v` to verify.
5. Open a pull request.

---

## 📄 License

Distributed under the **BSD 3-Clause License**. Crafted with precision for the modern author.
