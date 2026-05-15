$ErrorActionPreference = "Stop"

$taskName = "DPU_Codex_Session_RAG_Sync"
$syncScript = Join-Path $PSScriptRoot "sync_codex_sessions_to_rag.ps1"

if (-not (Test-Path $syncScript)) {
    throw "Sync script not found at $syncScript"
}

$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$syncScript`""

schtasks.exe /Create /TN $taskName /SC MINUTE /MO 30 /TR $taskCommand /F | Out-Host
schtasks.exe /Query /TN $taskName /FO LIST /V | Out-Host
