\
    $ErrorActionPreference = "Stop"

    <#
    md2star uninstaller (Windows / PowerShell)
    #>

    $pandocDir   = Join-Path $env:APPDATA "pandoc"
    $filtersDir  = Join-Path $pandocDir "filters"
    $defaultsDir = Join-Path $pandocDir "defaults"

    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $filtersDir  "strip-header-ids.lua")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $defaultsDir "docx-star.yaml")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "template.docx")
    Remove-Item -ErrorAction SilentlyContinue -Force (Join-Path $pandocDir   "md2star.cmd")

    Write-Host "🗑️  md2star uninstalled."
