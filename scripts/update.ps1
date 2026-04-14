$ErrorActionPreference = "Stop"

<#
md2star Updater (Windows / PowerShell)

This script safely updates md2star by pulling latest changes from GitHub 
and cleanly reinstalling the system components.
#>

Write-Host "📥 Pulling latest updates from GitHub..."
git pull origin main

Write-Host "🔄 Reinstalling md2star components..."
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1

Write-Host "✅ Update complete! You are now running the latest version."
