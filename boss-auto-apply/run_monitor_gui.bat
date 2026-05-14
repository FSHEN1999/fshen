@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set PY=%~dp0.venv\Scripts\python.exe
set PYW=%~dp0.venv\Scripts\pythonw.exe
if exist "%PYW%" set PY=%PYW%
if not exist "%PY%" set PY=python

echo Starting BOSS monitor GUI...
"%PY%" -u -B monitor_gui.py
