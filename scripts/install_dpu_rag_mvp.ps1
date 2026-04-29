Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$ragVenv = Join-Path $repoRoot ".rag_mvp\venv"
$ragPython = Join-Path $ragVenv "Scripts\python.exe"
$ragDb = Join-Path $repoRoot ".rag_mvp\rag.db"

if (-not (Test-Path $python)) {
    throw "Python venv not found at $python"
}

if (-not (Test-Path $ragPython)) {
    & $python -m venv $ragVenv
}

& $ragPython -m pip install --upgrade pip
& $ragPython -m pip install mcp mcp-server-git mcp-server-fetch

$env:LOCAL_RAG_HOME = $repoRoot
$env:LOCAL_RAG_DB = $ragDb
$env:PYTHONIOENCODING = "utf-8"

& $python -m dpu_rag_mvp build
& $python -m dpu_rag_mvp status
