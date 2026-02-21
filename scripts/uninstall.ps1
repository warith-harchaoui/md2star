\
    $ErrorActionPreference = "Stop"

    <#
    md2star uninstaller (Windows / PowerShell)
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

    Write-Host "🗑️  md2docx & md2pptx uninstalled."
