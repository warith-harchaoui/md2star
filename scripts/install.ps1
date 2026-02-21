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
    Copy-Item -Force "scripts\preprocessing.py"   (Join-Path $pandocDir  "preprocessing.py")
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
      echo Usage: md2docx input.md [--author \"Name\"] [--bib \"ref.bib\"] [--bibliography-name \"References\"] [--lang \"en-US\"] [extra pandoc args...]
      exit /b 1
    )

    set "IN=%~1"
    shift

    set "EXTRA_ARGS="
    set "BIB_FILE="
    set "BIB_NAME=Bibliography"
    :args_loop
    if "%~1"=="" goto args_done
    if "%~1"=="--author" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --metadata author=\"%~2\""
      shift
      shift
      goto args_loop
    )
    if "%~1"=="--bib" (
      set "BIB_FILE=%~2"
      set "EXTRA_ARGS=!EXTRA_ARGS! --citeproc --bibliography=\"%~2\""
      shift
      shift
      goto args_loop
    )
    if "%~1"=="--bibliography-name" (
      set "BIB_NAME=%~2"
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
    )

    :: 0. Preprocess Markdown (handles spacing before list items)
    for /f "delims=" %%I in ('python "%APPDATA%\pandoc\preprocessing.py" "%IN%"') do set "TEMP_MD=%%I"

    if defined BIB_FILE (
      echo.>>"!TEMP_MD!"
      echo # !BIB_NAME!>>"!TEMP_MD!"
    )

    :: 1. Convert Markdown to DOCX
    pandoc --defaults docx-star.yaml "!TEMP_MD!" -o "!OUT_DOCX!" !EXTRA_ARGS!
    echo Wrote: !OUT_DOCX!


    
    del /f /q "!TEMP_MD!"
    "@ | Set-Content -Encoding ASCII $docxCmdPath

    # md2pptx helper
    @"
    @echo off
    setlocal enabledelayedexpansion

    if "%~1"=="" (
      echo Usage: md2pptx input.md [--author \"Name\"] [--bib \"ref.bib\"] [--bibliography-name \"References\"] [--lang \"en-US\"] [extra pandoc args...]
      exit /b 1
    )

    set "IN=%~1"
    shift

    set "EXTRA_ARGS="
    set "BIB_FILE="
    set "BIB_NAME=Bibliography"
    :args_loop_pptx
    if "%~1"=="" goto args_done_pptx
    if "%~1"=="--author" (
      set "EXTRA_ARGS=!EXTRA_ARGS! --metadata author=\"%~2\""
      shift
      shift
      goto args_loop_pptx
    )
    if "%~1"=="--bib" (
      set "BIB_FILE=%~2"
      set "EXTRA_ARGS=!EXTRA_ARGS! --citeproc --bibliography=\"%~2\""
      shift
      shift
      goto args_loop_pptx
    )
    if "%~1"=="--bibliography-name" (
      set "BIB_NAME=%~2"
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
    )

    :: 0. Preprocess Markdown (handles spacing before list items)
    for /f "delims=" %%I in ('python "%APPDATA%\pandoc\preprocessing.py" "%IN%"') do set "TEMP_MD=%%I"

    if defined BIB_FILE (
      echo.>>"!TEMP_MD!"
      echo # !BIB_NAME!>>"!TEMP_MD!"
    )

    :: 1. Convert Markdown to PPTX
    pandoc --defaults pptx-star.yaml "!TEMP_MD!" -o "!OUT_PPTX!" !EXTRA_ARGS!
    echo Wrote: !OUT_PPTX!


    
    del /f /q "!TEMP_MD!"
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
