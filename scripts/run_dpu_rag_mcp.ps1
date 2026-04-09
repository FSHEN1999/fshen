Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".rag_mvp\venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Python venv not found at $python"
}

$env:LOCAL_RAG_HOME = $repoRoot
$env:LOCAL_RAG_DB = Join-Path $repoRoot ".rag_mvp\rag.db"

& $python -m dpu_rag_mvp.mcp_server
