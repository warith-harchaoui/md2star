$ErrorActionPreference = "Stop"

<#
md2star installer (Windows / PowerShell).

Thin wrapper around pipx — installs the local checkout (or the published
package once PyPI release is live), verifies pandoc is on PATH, and
auto-installs LibreOffice (soffice) when missing so the md2pdf path
works out of the box.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Force
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -NoLibreOffice
#>

param(
    [switch]$Force,
    [switch]$Local,
    [switch]$NoLibreOffice
)

# 1. Pandoc is required at runtime; fail fast with a helpful pointer.
if (-not (Get-Command pandoc -ErrorAction SilentlyContinue)) {
    Write-Error @"
md2star: pandoc not found on PATH. Install it first:

  winget install --id JohnMacFarlane.Pandoc
  # or:
  https://pandoc.org/installing.html

Then re-run this installer.
"@
    exit 127
}

# 1b. LibreOffice (soffice) — required for md2pdf. Auto-install via
#     winget when missing; skip with -NoLibreOffice.
$sofficePresent =
    (Get-Command soffice -ErrorAction SilentlyContinue) -ne $null -or
    (Get-Command libreoffice -ErrorAction SilentlyContinue) -ne $null -or
    (Test-Path "C:\Program Files\LibreOffice\program\soffice.exe") -or
    (Test-Path "C:\Program Files (x86)\LibreOffice\program\soffice.exe")
if (-not $sofficePresent) {
    if ($NoLibreOffice) {
        Write-Warning "-NoLibreOffice passed; md2pdf disabled."
    } elseif (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "md2star: LibreOffice not found — installing via winget..."
        winget install --id TheDocumentFoundation.LibreOffice `
            --accept-source-agreements --accept-package-agreements
    } else {
        Write-Warning @"
md2star: LibreOffice not found and winget is unavailable. Install it manually:

  https://www.libreoffice.org/download/

md2pdf will not work until you do. Pass -NoLibreOffice to suppress this
message.
"@
    }
}

# 2. pipx is the standard 'install Python apps globally without venv pain'
#    tool; bootstrap it if missing.
if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
    Write-Host "md2star: bootstrapping pipx (one-time)..."
    python -m pip install --user --quiet pipx
    python -m pipx ensurepath
    # ensurepath only edits the user PATH for future shells; expose pipx in
    # *this* shell too so the install command below works.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 3. Install md2star.
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pipxArgs = @("install", $repoRoot.Path)
if ($Force) { $pipxArgs += "--force" }

Write-Host "md2star: installing from $($repoRoot.Path)"
& pipx @pipxArgs

Write-Host ""
Write-Host "md2star installed. Try:"
Write-Host "  md2docx <input.md>"
Write-Host "  md2pptx <input.md>"
Write-Host "  md2star --help"
Write-Host ""
Write-Host "If md2docx is not found, restart your shell so the pipx-managed PATH loads."
