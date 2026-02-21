\
    $ErrorActionPreference = "Stop"

    <#
    md2star Installer (Windows / PowerShell)

    This script automates the deployment of the md2star toolset on Windows.
    It performs the following actions:
    1. Configures the Pandoc user data directory (%APPDATA%\pandoc).
    2. Deploys custom Lua filters for smart metadata handling.
    3. Deploys curated DOCX and PPTX reference templates.
    4. Injects absolute system paths into Pandoc YAML defaults to ensure 
       reliability when running from any directory.
    5. Installs the Windows CMD wrappers (md2docx.cmd, md2pptx.cmd, gup.cmd) 
       into %APPDATA%\pandoc for immediate CLI access once added to PATH.

    Preamble:
    md2star bridges the gap between Markdown efficiency and Office professionalism.
    This installer ensures all structural pieces are correctly linked on Windows systems.
    #>

    $pandocDir   = Join-Path $env:APPDATA "pandoc"
    $filtersDir  = Join-Path $pandocDir "filters"
    $defaultsDir = Join-Path $pandocDir "defaults"

    New-Item -ItemType Directory -Force -Path $filtersDir  | Out-Null
    New-Item -ItemType Directory -Force -Path $defaultsDir | Out-Null

    Copy-Item -Force "pandoc\filters\md2star.lua" (Join-Path $filtersDir "md2star.lua")
    Copy-Item -Force "pandoc\metadata.yaml"      (Join-Path $pandocDir "metadata.yaml")
    Copy-Item -Force "assets\template.docx"       (Join-Path $pandocDir "template.docx")
    Copy-Item -Force "assets\template.pptx"       (Join-Path $pandocDir "template.pptx")

    # Inject absolute paths into defaults files during installation
    $filterPath = (Join-Path $filtersDir "md2star.lua") -replace '\\', '/'
    $metadataPath = (Join-Path $pandocDir "metadata.yaml") -replace '\\', '/'
    $templatePathDocx = (Join-Path $pandocDir "template.docx") -replace '\\', '/'
    $templatePathPptx = (Join-Path $pandocDir "template.pptx") -replace '\\', '/'
    
    (Get-Content "pandoc\defaults\docx-star.yaml") -replace 'md2star.lua', $filterPath `
                                                    -replace 'metadata.yaml', $metadataPath `
                                                    -replace 'reference-doc: template.docx', "reference-doc: $templatePathDocx" |
        Set-Content (Join-Path $defaultsDir "docx-star.yaml")

    (Get-Content "pandoc\defaults\pptx-star.yaml") -replace 'md2star.lua', $filterPath `
                                                    -replace 'metadata.yaml', $metadataPath `
                                                    -replace 'reference-doc: template.pptx', "reference-doc: $templatePathPptx" |
        Set-Content (Join-Path $defaultsDir "pptx-star.yaml")

    # Helper commands placed in %APPDATA%\pandoc for simplicity
    $docxCmdPath = Join-Path $pandocDir "md2docx.cmd"
    $pptxCmdPath = Join-Path $pandocDir "md2pptx.cmd"

    # md2docx helper
    @"
    @echo off
    setlocal enabledelayedexpansion

    if "%~1"=="" (
      echo Usage: md2docx input.md [--author \"Name\"] [--bib \"ref.bib\"] [--lang \"en-US\"] [extra pandoc args...]
      exit /b 1
    )

    set "IN=%~1"
    shift

    set "EXTRA_ARGS="
    :args_loop
    if "%~1"=="" goto args_done
    if "%~1"=="--author" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --metadata author=\"%~2\""
      shift
      shift
      goto args_loop
    )
    if "%~1"=="--bib" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --citeproc --bibliography=\"%~2\""
      shift
      shift
      goto args_loop
    )
    if "%~1"=="--lang" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --metadata lang=\"%~2\""
      shift
      shift
      goto args_loop
    )
    set "EXTRA_ARGS=!EXTRA_ARGS! %1"
    shift
    goto args_loop
    :args_done

    for %%F in ("%IN%") do (
      set "OUT_DOCX=%%~dpnF.docx"
      set "OUT_PDF=%%~dpnF.pdf"
    )

    :: 1. Convert Markdown to DOCX
    pandoc --defaults docx-star.yaml "%IN%" -o "!OUT_DOCX!" !EXTRA_ARGS!
    echo Wrote: !OUT_DOCX!

    :: 2. Convert DOCX to PDF (Using Pandoc)
    pandoc "!OUT_DOCX!" -o "!OUT_PDF!"
    echo Wrote: !OUT_PDF!
    "@ | Set-Content -Encoding ASCII $docxCmdPath

    # md2pptx helper
    @"
    @echo off
    setlocal enabledelayedexpansion

    if "%~1"=="" (
      echo Usage: md2pptx input.md [--author \"Name\"] [--bib \"ref.bib\"] [--lang \"en-US\"] [extra pandoc args...]
      exit /b 1
    )

    set "IN=%~1"
    shift

    set "EXTRA_ARGS="
    :args_loop_pptx
    if "%~1"=="" goto args_done_pptx
    if "%~1"=="--author" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --metadata author=\"%~2\""
      shift
      shift
      goto args_loop_pptx
    )
    if "%~1"=="--bib" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --citeproc --bibliography=\"%~2\""
      shift
      shift
      goto args_loop_pptx
    )
    if "%~1"=="--lang" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --metadata lang=\"%~2\""
      shift
      shift
      goto args_loop_pptx
    )
    set "EXTRA_ARGS=!EXTRA_ARGS! %1"
    shift
    goto args_loop_pptx
    :args_done_pptx

    for %%F in ("%IN%") do (
      set "OUT_PPTX=%%~dpnF.pptx"
      set "OUT_PDF=%%~dpnF.pdf"
    )

    :: 1. Convert Markdown to PPTX
    pandoc --defaults pptx-star.yaml "%IN%" -o "!OUT_PPTX!" !EXTRA_ARGS!
    echo Wrote: !OUT_PPTX!

    :: 2. Convert to PDF (trying to avoid default LaTeX look)
    :: If the user has typst or another engine, they can set PANDOC_PDF_ENGINE
    if defined PANDOC_PDF_ENGINE (set "PDF_ENGINE=%PANDOC_PDF_ENGINE%") else (set "PDF_ENGINE=pdflatex")
    pandoc "%IN%" -o "!OUT_PDF!" --pdf-engine="!PDF_ENGINE!" !EXTRA_ARGS!
    echo Wrote: !OUT_PDF!
    "@ | Set-Content -Encoding ASCII $pptxCmdPath

    # gup helper
    $gupCmdPath = Join-Path $pandocDir "gup.cmd"
    @"
    @echo off
    python "${pandocDir}\gup\src\gup.py" %*
    "@ | Set-Content -Encoding ASCII $gupCmdPath

    # Deploy gup resources
    $gupTargetDir = Join-Path $pandocDir "gup"
    if (!(Test-Path $gupTargetDir)) { New-Item -ItemType Directory -Force -Path $gupTargetDir | Out-Null }
    Copy-Item -Force -Recurse "gup\*" $gupTargetDir

    # Ensure assets are copied
    $assetsTargetDir = Join-Path $pandocDir "assets"
    if (!(Test-Path $assetsTargetDir)) { New-Item -ItemType Directory -Force -Path $assetsTargetDir | Out-Null }
    Copy-Item -Force -Recurse "assets\*" $assetsTargetDir

    Write-Host ""
    Write-Host "✅ md2docx, md2pptx & gup installed."
    Write-Host "  Filter:   $filtersDir\md2star.lua"
    Write-Host "  Defaults: $defaultsDir\docx-star.yaml, pptx-star.yaml"
    Write-Host "  Templates: $pandocDir\template.docx, template.pptx"
    Write-Host "  Commands:  $docxCmdPath, $pptxCmdPath, $gupCmdPath"
    Write-Host ""
    Write-Host "Recommended: add this folder to PATH to use the commands anywhere:"
    Write-Host "  $pandocDir"
    Write-Host ""
    Write-Host "Try:"
    Write-Host "  md2docx notes.md"
    Write-Host "  gup --help"
