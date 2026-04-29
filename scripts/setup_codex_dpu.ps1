Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$installScript = Join-Path $PSScriptRoot "install_dpu_rag_mvp.ps1"
$configureScript = Join-Path $PSScriptRoot "configure_codex_dpu_mcp.py"

if (-not (Test-Path $python)) {
    throw "Python venv not found at $python"
}

& $installScript
& $python $configureScript

Write-Host ""
Write-Host "DPU Codex setup is ready."
Write-Host "Restart Codex to pick up the new skill and MCP servers."
