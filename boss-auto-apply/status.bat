@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" -u -B status.py
pause
