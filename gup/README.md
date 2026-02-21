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

## 1) Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Google Cloud setup (one-time)

1. Create/select a Google Cloud project
2. Enable **Google Drive API**
3. Configure OAuth consent screen
4. Create OAuth client ID (**Desktop app**)
5. Download the JSON and save it as `credentials.json` at the repo root

## 3) Configure

Copy the example config:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and set your destination Drive folder id.

### How to get a folder ID
Open the folder in Drive and copy the ID from the URL:
`https://drive.google.com/drive/folders/<FOLDER_ID>`

## 4) Run

```bash
python -m src.gup /path/to/file.docx
# or
python -m src.gup /path/to/slides.pptx
```

Optional: override the output name:

```bash
python -m src.gup /path/to/file.docx --name "My Google Doc"
```

## 5) Notes

- Some complex Office formatting may not convert perfectly.
- If you need Shared Drives support, use the optional `--supports-all-drives` flag.
