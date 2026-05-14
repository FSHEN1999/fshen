@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

"%PY%" -u -B storage.py
