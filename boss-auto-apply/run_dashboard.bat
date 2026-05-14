@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set PY=%~dp0.venv\Scripts\python.exe
set PYW=%~dp0.venv\Scripts\pythonw.exe
if exist "%PYW%" set PY=%PYW%
if not exist "%PY%" set PY=python

echo Starting local dashboard...
echo URL: http://127.0.0.1:8765
start "" "%PY%" -u -B dashboard.py
timeout /t 1 /nobreak >nul
start "" http://127.0.0.1:8765
