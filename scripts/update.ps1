$ErrorActionPreference = "Stop"

<#
md2star updater (Windows / PowerShell).

Pulls latest changes from origin/main and reinstalls via pipx.
#>

Write-Host "Pulling latest changes..."
git pull origin main

Write-Host "Reinstalling via pipx..."
powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\install.ps1" -Force

Write-Host "Update complete."
