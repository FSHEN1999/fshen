@echo off
setlocal EnableExtensions
echo Stopping boss-auto-apply python processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { ($_.CommandLine -match 'boss-auto-apply') -and ($_.CommandLine -match 'main\.py') } | ForEach-Object { Write-Host ('STOP PID ' + $_.ProcessId + ' ' + $_.CommandLine); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
python -u -B run_lock.py release
if not "%BOSS_DASHBOARD_LAUNCH%"=="1" pause
