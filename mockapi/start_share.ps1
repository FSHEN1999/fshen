[CmdletBinding()]
param(
    [int]$PublicPort = 8002,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendRoot = Join-Path $projectRoot "frontend"
$ngrokConfigPath = Join-Path $env:LOCALAPPDATA "ngrok\ngrok.yml"

function Write-Step($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor Cyan
}

function Wait-HttpReady($url, $timeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 8
            return $response
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Timed out waiting for $url"
}

function Stop-NgrokProcesses() {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq "ngrok.exe" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Start-NgrokTunnel($publicPort) {
    $result = [ordered]@{
        Success = $false
        Url = $null
        Log = $null
        Provider = "ngrok"
    }

    if (!(Test-Path $ngrokConfigPath)) {
        return $result
    }

    Stop-NgrokProcesses

    $outLog = Join-Path $env:TEMP "mockapi-ngrok-share-out.log"
    $errLog = Join-Path $env:TEMP "mockapi-ngrok-share-err.log"
    Remove-Item -LiteralPath $outLog, $errLog -ErrorAction SilentlyContinue

    Start-Process `
        -WindowStyle Hidden `
        -FilePath "ngrok" `
        -ArgumentList "http $publicPort --log stdout" `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog

    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        $logText = ""
        if (Test-Path $outLog) {
            $logText = (Get-Content -Path $outLog -ErrorAction SilentlyContinue) -join "`n"
        }
        $match = [regex]::Match($logText, 'https://[-a-z0-9]+\.ngrok-free\.(app|dev)')
        if ($match.Success) {
            $result.Success = $true
            $result.Url = $match.Value
            $result.Log = $outLog
            return $result
        }
        Start-Sleep -Seconds 2
    }

    $result.Log = $outLog
    return $result
}

Write-Step "Preparing MockAPI share service"

if (-not $SkipFrontendBuild) {
    Write-Step "Building frontend assets"
    Push-Location $frontendRoot
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

Write-Step "Stopping existing public tunnels"
Stop-NgrokProcesses

Write-Step "Starting Docker service"
Push-Location $projectRoot
try {
    docker compose up -d --build
} finally {
    Pop-Location
}

Write-Step "Waiting for container health"
$healthUrl = "http://127.0.0.1:$PublicPort/api/health"
$rootUrl = "http://127.0.0.1:$PublicPort/"
$health = Wait-HttpReady -url $healthUrl
$root = Wait-HttpReady -url $rootUrl
Write-Host "Local health : $($health.StatusCode) $healthUrl" -ForegroundColor Green
Write-Host "Local root   : $($root.StatusCode) $rootUrl" -ForegroundColor Green

Write-Step "Creating ngrok tunnel"
$tunnel = Start-NgrokTunnel -publicPort $PublicPort

if (-not $tunnel.Success) {
    Write-Host ""
    Write-Host "ngrok did not return a public URL. Recent log:" -ForegroundColor Yellow
    if ($tunnel.Log -and (Test-Path $tunnel.Log)) {
        Get-Content -Path $tunnel.Log -Tail 20
    }
    throw "ngrok tunnel creation failed"
}

Write-Step "Verifying public URL"
$publicHealth = Wait-HttpReady -url "$($tunnel.Url)/api/health" -timeoutSeconds 45
$publicRoot = Wait-HttpReady -url "$($tunnel.Url)/" -timeoutSeconds 45

Write-Host ""
Write-Host "Tunnel type   : $($tunnel.Provider)" -ForegroundColor Green
Write-Host "Share URL     : $($tunnel.Url)" -ForegroundColor Green
Write-Host "Public health : $($publicHealth.StatusCode) $($tunnel.Url)/api/health" -ForegroundColor Green
Write-Host "Public root   : $($publicRoot.StatusCode) $($tunnel.Url)/" -ForegroundColor Green
Write-Host ""
Write-Host "Container     : docker compose ps" -ForegroundColor DarkGray
Write-Host "Tunnel logs   : $($tunnel.Log)" -ForegroundColor DarkGray
