$ErrorActionPreference = "Stop"

<#
md2star uninstaller (Windows / PowerShell).

Asks for confirmation by default; pass -Yes to skip the prompt (CI).
Also offers -ClearCache to wipe the on-disk artifact cache.
#>

param(
    [switch]$Yes,
    [switch]$ClearCache
)

$hasPipx = (Get-Command pipx -ErrorAction SilentlyContinue) -ne $null
$pipxHasIt = $hasPipx -and ((pipx list 2>$null) -match "package md2star")

Write-Host "md2star uninstall will remove:"
if ($pipxHasIt) {
    Write-Host "  - pipx package 'md2star' and its console scripts (md2docx, md2pptx, md2star)"
} else {
    Write-Host "  - (nothing - md2star is not installed via pipx)"
}
if ($ClearCache) {
    Write-Host "  - the on-disk cache directory (`$env:LOCALAPPDATA\md2star\)"
}

if (-not $Yes) {
    $response = Read-Host "Proceed? [y/N]"
    if ($response -notmatch '^(y|yes)$') {
        Write-Host "Aborted."
        exit 0
    }
}

if ($pipxHasIt) {
    pipx uninstall md2star
}

if ($ClearCache -and (Get-Command md2star -ErrorAction SilentlyContinue)) {
    md2star clear-cache
}

# Best-effort cleanup of legacy shell-installer artifacts.
$pandocDir = Join-Path $env:APPDATA "pandoc"
$legacy = @(
    (Join-Path $pandocDir "preprocessing.py"),
    (Join-Path $pandocDir "postprocess_docx.py"),
    (Join-Path $pandocDir "preprocessing_lib"),
    (Join-Path $pandocDir "filters\md2star.lua"),
    (Join-Path $pandocDir "defaults\docx-star.yaml"),
    (Join-Path $pandocDir "defaults\pptx-star.yaml"),
    (Join-Path $pandocDir "metadata.yaml"),
    (Join-Path $pandocDir "mermaid-config.json"),
    (Join-Path $pandocDir "template.docx"),
    (Join-Path $pandocDir "template.pptx"),
    (Join-Path $pandocDir "venv"),
    (Join-Path $pandocDir "md2docx.cmd"),
    (Join-Path $pandocDir "md2pptx.cmd")
)
foreach ($path in $legacy) {
    if (Test-Path $path) { Remove-Item -Recurse -Force $path }
}

Write-Host "md2star uninstalled."
