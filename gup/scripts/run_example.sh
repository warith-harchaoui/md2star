#!/usr/bin/env bash
set -euo pipefail
python -m src.upload_convert --docx "$1"
