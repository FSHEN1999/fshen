$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$exportScript = Join-Path $PSScriptRoot "export_codex_sessions_to_rag.py"
$logDir = Join-Path $repoRoot ".rag_mvp\logs"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "codex_session_sync_$timestamp.log"

if (-not (Test-Path $python)) {
    throw "Python venv not found at $python"
}
if (-not (Test-Path $exportScript)) {
    throw "Export script not found at $exportScript"
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Push-Location $repoRoot
try {
    "[$(Get-Date -Format o)] Export Codex sessions" | Tee-Object -FilePath $logFile
    & $python $exportScript 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Codex session export failed with exit code $LASTEXITCODE"
    }

    "[$(Get-Date -Format o)] Rebuild DPU RAG index" | Tee-Object -FilePath $logFile -Append
    & $python -m dpu_rag_mvp build 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "DPU RAG build failed with exit code $LASTEXITCODE"
    }

    "[$(Get-Date -Format o)] Sync complete" | Tee-Object -FilePath $logFile -Append
}
finally {
    Pop-Location
}
