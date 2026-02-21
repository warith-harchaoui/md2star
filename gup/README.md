# gdrive-upload-convert (gup)

Upload a local `.docx` or `.pptx` to a **specific Google Drive folder** and **convert it to a Google Doc or Google Slide** so that **only the converted file** exists in Drive.

## What this repo does

- Reads a local `.docx` or `.pptx`
- Uploads it to Google Drive into the folder you specify
- Automatically converts them:
    - `.docx` → `application/vnd.google-apps.document` (Google Docs)
    - `.pptx` → `application/vnd.google-apps.presentation` (Google Slides)
- Prints the created file ID (+ web link when available)

## Security note (important)

This repository **does not** ship with real credentials.
- Keep your OAuth client file (`credentials.json`) **private**
- Do **not** commit it
- The repo includes:
  - `config.example.yaml` (a safe template)
  - `.gitignore` entries for `credentials.json`, `token.json`, and `config.yaml`

### 1. Installation

From the **repository root**:
```bash
# Optional: Create environment
cd gup && conda env create -f environment.yml && conda activate gup && cd ..

# Install dependencies
pip install -r gup/requirements.txt
```

### 2. Google Cloud Setup (One-Time)

1. Create/select a Google Cloud project
2. Enable **Google Drive API**
3. Configure OAuth consent screen
4. Create OAuth client ID (**Desktop app**)
5. Download the JSON and save it as `credentials.json` at the repo root

### 3. Configuration

1. Copy `gup/config.example.yaml` to `gup/config.yaml`.
2. Edit `gup/config.yaml` to provide your authentication paths.

### 4. Usage

To upload a document, you **must** provide the target Google Drive **Folder ID** (or the full URL) via the CLI.

```bash
# Using a raw Folder ID
gup your_file.docx --folder-id "1ABC-xyz..."

# Or using the full Drive URL (convenient!)
gup your_file.docx --folder-id "https://drive.google.com/drive/folders/1ABC-xyz..."
```

#### How to find your Folder ID
Open the destination folder in your browser and copy the ID (or the whole URL) from the address bar.
`https://drive.google.com/drive/folders/`**`1ABC-xyz...`**

Optional: override the output name:

```bash
python -m src.gup /path/to/file.docx --name "My Google Doc"
```

### 5. Notes

- Some complex Office formatting may not convert perfectly.
- If you need Shared Drives support, use the optional `--supports-all-drives` flag.
