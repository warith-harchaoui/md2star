\
    $ErrorActionPreference = "Stop"

    <#
    md2star installer (Windows / PowerShell)

    What it installs into your Pandoc user directory:
      %APPDATA%\pandoc\filters\strip-header-ids.lua
      %APPDATA%\pandoc\defaults\docx-star.yaml
      %APPDATA%\pandoc\template.docx

    It also creates a helper command:
      %APPDATA%\pandoc\md2star.cmd

    Requirements:
      - pandoc must be installed and available in PATH

    Notes:
      - To run `md2star` from anywhere, add %APPDATA%\pandoc to your PATH.
      - If you customize assets\template.docx in this repo, re-run this installer.
    #>

    $pandocDir   = Join-Path $env:APPDATA "pandoc"
    $filtersDir  = Join-Path $pandocDir "filters"
    $defaultsDir = Join-Path $pandocDir "defaults"

    New-Item -ItemType Directory -Force -Path $filtersDir  | Out-Null
    New-Item -ItemType Directory -Force -Path $defaultsDir | Out-Null

    Copy-Item -Force "pandoc\filters\strip-header-ids.lua" (Join-Path $filtersDir "strip-header-ids.lua")
    Copy-Item -Force "pandoc\defaults\docx-star.yaml"      (Join-Path $defaultsDir "docx-star.yaml")
    Copy-Item -Force "assets\template.docx"               (Join-Path $pandocDir "template.docx")

    # Helper command placed in %APPDATA%\pandoc for simplicity
    $cmdPath = Join-Path $pandocDir "md2star.cmd"

    @"
    @echo off
    setlocal enabledelayedexpansion

    if "%~1"=="" (
      echo Usage: md2star input.md [extra pandoc args...]
      echo Output: input.docx
      exit /b 1
    )

    set "IN=%~1"
    shift

    for %%F in ("%IN%") do set "OUT=%%~dpnF.docx"

    pandoc --defaults docx-star.yaml "%IN%" -o "%OUT%" %*
    echo Wrote: %OUT%
    "@ | Set-Content -Encoding ASCII $cmdPath

    Write-Host ""
    Write-Host "✅ md2star installed."
    Write-Host "  Filter:   $filtersDir\strip-header-ids.lua"
    Write-Host "  Defaults: $defaultsDir\docx-star.yaml"
    Write-Host "  Template: $pandocDir\template.docx"
    Write-Host "  Command:  $cmdPath"
    Write-Host ""
    Write-Host "Recommended: add this folder to PATH to use md2star anywhere:"
    Write-Host "  $pandocDir"
    Write-Host ""
    Write-Host "Try:"
    Write-Host "  md2star notes.md"
