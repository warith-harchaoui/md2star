\
    $ErrorActionPreference = "Stop"

    <#
    md2star Uninstaller (Windows / PowerShell)

    This script safely removes all md2star components from your system:
    1. Custom Lua filters
    2. YAML default configurations
    3. Curated templates and metadata
    4. CLI wrappers (md2docx.cmd, md2pptx.cmd)
    #>

    $pandocDir   = Join-Path $env:APPDATA "pandoc"
    $filtersDir  = Join-Path $pandocDir "filters"
    $defaultsDir = Join-Path $pandocDir "defaults"

    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $filtersDir  "md2star.lua")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "metadata.yaml")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $defaultsDir "docx-star.yaml")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $defaultsDir "pptx-star.yaml")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "template.docx")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "template.pptx")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "md2docx.cmd")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "md2pptx.cmd")

    

    if (Test-Path (Join-Path $pandocDir "assets")) { Remove-Item -ErrorAction SilentlyContinue -Force -Recurse (Join-Path $pandocDir "assets") }

    Write-Host "🗑️  md2docx & md2pptx uninstalled successfully."
