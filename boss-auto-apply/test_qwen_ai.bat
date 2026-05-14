@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '.\.env.local.ps1') { . '.\.env.local.ps1' }; & '%PY%' -u -B test_ai_provider.py"
pause
