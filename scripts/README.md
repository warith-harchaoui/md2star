# scripts/

Shell scripts and Python helpers that power the md2star toolset.

**Run from the repository root.** All paths are relative to the project directory.

## Contents

| File               | Description                                                        |
|--------------------|--------------------------------------------------------------------|
| `install.sh`       | macOS/Linux installer — deploys filters, templates, and CLI wrappers to `~/.pandoc` and `~/.local/bin`. |
| `install.ps1`      | Windows (PowerShell) equivalent of `install.sh`.                   |
| `uninstall.sh`     | macOS/Linux uninstaller — removes all deployed files.              |
| `uninstall.ps1`    | Windows (PowerShell) equivalent of `uninstall.sh`.                 |
| `preprocessing.py` | Markdown pre-processor that ensures blank lines before list items. |
| `test.sh`          | Integration test suite exercising `md2docx` and `md2pptx`.         |

## Quick reference

```bash
# Install
bash scripts/install.sh

# Uninstall
bash scripts/uninstall.sh

# Run tests
bash scripts/test.sh
```
