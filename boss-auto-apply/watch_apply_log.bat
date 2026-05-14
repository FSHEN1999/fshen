@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist data\run.log (
  echo data\run.log not found yet.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content -Path 'data\run.log' -Encoding UTF8 -Wait -Tail 40"
