[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Stopping ngrok tunnels..." -ForegroundColor Cyan
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "ngrok.exe" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "Stopping MockAPI docker service..." -ForegroundColor Cyan
Push-Location $projectRoot
try {
    docker compose down
} finally {
    Pop-Location
}

Write-Host "Stopped." -ForegroundColor Green
