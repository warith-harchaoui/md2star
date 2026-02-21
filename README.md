# md2star ✍️⭐️

**md2star** is a small, cross-platform wrapper around **Pandoc** that converts **Markdown → DOCX** for a smooth workflow:

1. Write in Markdown (any editor: Emacs / Vim / Sublime / VS Code / etc.)
2. Run `md2star` to generate a `.docx`
3. Upload to Google Drive → open as Google Docs

The goal: **write as fast as you think** (optionally with tools like Cotypist), without the friction of slow editors like Google Docs or Microsoft Word.

---

## What problem does it solve?

When you write in Google Docs / Word, the editor latency can become the bottleneck: UI friction, formatting distractions.

md2star keeps the writing loop fast:
- Markdown for drafting
- DOCX output for sharing / Drive conversion
- A consistent visual style via a shared Word template

---

## What md2star does (and does not)

✅ **Does**
- Converts `your_note.md` → `your_note.docx`
- Applies a shared **DOCX style template** (`template.docx`)
- Removes heading identifiers so Google Docs typically **does not show bookmark markers** next to headings

⚠️ **Trade-off**
- If you rely on internal Markdown links like `[Jump](#my-heading)`, those targets won’t exist anymore (by design).

---

## Install

md2star requires **Pandoc**. Then md2star installs a small wrapper command plus a template into your Pandoc user directory.

### 🍎 macOS

**1) Install Pandoc**
```bash
brew install pandoc
```

**2) Install md2star**
```bash
git clone https://github.com/<you>/md2star.git
cd md2star
bash scripts/install.sh
```

**3) Ensure the command is on your PATH (zsh default)**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Optional convenience:
```bash
make install
```

---

### 🐧 Ubuntu / Debian (Linux)

**1) Install Pandoc**
```bash
sudo apt-get update
sudo apt-get install -y pandoc
```

**2) Install md2star**
```bash
git clone https://github.com/<you>/md2star.git
cd md2star
bash scripts/install.sh
```

**3) Ensure the command is on your PATH (bash common)**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Optional convenience:
```bash
make install
```

---

### 🪟 Windows

**1) Install Pandoc**
```powershell
winget install --id JohnMacFarlane.Pandoc -e
```

**2) Install md2star**
```powershell
git clone https://github.com/<you>/md2star.git
cd md2star
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

**3) Add md2star to PATH (recommended)**  
Add this directory to your PATH so `md2star` works from any folder:
- `%APPDATA%\pandoc`

(You can do it via Windows Settings → Environment Variables → Path.)

---

## Usage

Convert a Markdown file:

```bash
md2star notes.md
```

Output:
- `notes.docx` (next to `notes.md`)

Pass extra Pandoc flags (md2star forwards them to Pandoc):

```bash
md2star notes.md --metadata title="My Document"
```

Tip: you can integrate `md2star` into your editor build command / a Makefile / a git pre-share routine.

---

## Customize the DOCX style template

md2star ships with `assets/template.docx` as a shared styling baseline.

**Customize it once:**
1. Open `assets/template.docx` in Word / LibreOffice / Google Doc
2. Modify styles (Normal, Heading 1/2/3, spacing, fonts, etc.)
3. Save

**Then reinstall to deploy the updated template:**

macOS / Linux:
```bash
bash scripts/install.sh
```

Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

---

## Uninstall

🍎 macOS / 🐧 Linux (Ubuntu):
```bash
bash scripts/uninstall.sh
# or: make uninstall
```

🪟 Windows:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1
```

---

## Files installed (for reference)

🍎 macOS / 🐧 Linux (Ubuntu):
- `~/.pandoc/filters/strip-header-ids.lua`
- `~/.pandoc/defaults/docx-star.yaml`
- `~/.pandoc/template.docx`
- `~/.local/bin/md2star`

🪟 Windows:
- `%APPDATA%\pandoc\filters\strip-header-ids.lua`
- `%APPDATA%\pandoc\defaults\docx-star.yaml`
- `%APPDATA%\pandoc\template.docx`
- `%APPDATA%\pandoc\md2star.cmd`

---

## CI lint (advanced users)

`.github/workflows/lint.yml` checks:
- required files exist
- bash scripts parse on macOS/Linux runners
- PowerShell scripts parse on Windows runners

---

## License

**NO LICENSE** — all rights reserved.
