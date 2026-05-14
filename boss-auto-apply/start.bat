@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set PY=%~dp0.venv\Scripts\python.exe
if not exist "%PY%" set PY=python

set APPLY_LIMIT=2
set WATCH_INTERVAL=180
set WATCH_ROUNDS=0
set CHECK_ONLY=0

if /i "%~1"=="--check" (
  set CHECK_ONLY=1
) else (
  if not "%~1"=="" set APPLY_LIMIT=%~1
  if not "%~2"=="" set WATCH_INTERVAL=%~2
  if not "%~3"=="" set WATCH_ROUNDS=%~3
)

echo ========================================
echo BOSS Auto Apply - Daily Start
echo.
echo Flow:
echo   1. Apply %APPLY_LIMIT% testing / QA jobs as one batch
echo   2. Slowly check unread HR chats, AI replies, and send resume if needed
echo   3. Wait %WATCH_INTERVAL%s, then apply the next %APPLY_LIMIT% jobs
echo   4. Repeat until stopped, or until WATCH_ROUNDS is reached
echo.
echo Usage:
echo   start.bat                 default: apply 5, watch 180s, then apply 5 again
echo   start.bat 10 300 0        apply 10 per loop, wait 300s, loop forever
echo   start.bat --check         syntax and doctor only
echo ========================================
echo.

if not exist logs mkdir logs

echo [1/3] Syntax check...
"%PY%" -B -m py_compile main.py auth.py search.py apply.py chat_actions.py chat_processor.py reply_engine.py ai_reply.py jd_matcher.py doctor.py dashboard.py storage.py run_lock.py
if errorlevel 1 (
  echo [ERROR] Syntax check failed. Stop.
  pause
  exit /b 1
)

echo [2/3] Doctor...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "if (Test-Path '.\.env.local.ps1') { . '.\.env.local.ps1' };" ^
  "$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1';" ^
  "$env:BOSS_PROFILE_NAME='chrome_profile_fengshen';" ^
  "$env:BOSS_CHROME_PORT='9222'; $env:BOSS_COOKIE_FALLBACK='0';" ^
  "$env:BOSS_AI_REPLY='1'; $env:BOSS_RAG_ENABLE='1';" ^
  "if (-not $env:BOSS_AI_PROVIDER) { $env:BOSS_AI_PROVIDER='qwen' };" ^
  "if (-not $env:BOSS_QWEN_BASE_URL) { $env:BOSS_QWEN_BASE_URL='https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1' };" ^
  "if (-not $env:BOSS_QWEN_MODEL) { $env:BOSS_QWEN_MODEL='qwen3.6-plus' };" ^
  "& '%PY%' -u -B doctor.py"

if "%CHECK_ONLY%"=="1" (
  echo [OK] Check mode passed. No apply/watch started.
  exit /b 0
)

echo.
echo [3/3] Start apply then slow AI chat watch...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "if (Test-Path '.\.env.local.ps1') { . '.\.env.local.ps1' };" ^
  "$env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1';" ^
  "$env:BOSS_FAST_MODE='1';" ^
  "$env:BOSS_PROFILE_NAME='chrome_profile_fengshen';" ^
  "$env:BOSS_CHROME_PORT='9222'; $env:BOSS_COOKIE_FALLBACK='0';" ^
  "$env:BOSS_AI_REPLY='1'; $env:BOSS_RAG_ENABLE='1';" ^
  "if (-not $env:BOSS_AI_PROVIDER) { $env:BOSS_AI_PROVIDER='qwen' };" ^
  "if (-not $env:BOSS_QWEN_BASE_URL) { $env:BOSS_QWEN_BASE_URL='https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1' };" ^
  "if (-not $env:BOSS_QWEN_MODEL) { $env:BOSS_QWEN_MODEL='qwen3.6-plus' };" ^
  "if (-not $env:BOSS_QWEN_API_KEY) { Write-Host '[WARN] BOSS_QWEN_API_KEY missing; AI will fallback to Hermes/rules.' };" ^
  "$lock = Start-Process -FilePath '%PY%' -ArgumentList '-u','-B','run_lock.py','acquire','start' -Wait -PassThru -NoNewWindow;" ^
  "if ($lock.ExitCode -ne 0) { exit $lock.ExitCode };" ^
  "try { & '%PY%' -u -B main.py --apply-watch --no-resume-sweep --limit %APPLY_LIMIT% --interval %WATCH_INTERVAL% --rounds %WATCH_ROUNDS%; exit $LASTEXITCODE }" ^
  "finally { & '%PY%' -u -B run_lock.py release | Out-Host }"

set EXIT_CODE=%ERRORLEVEL%
echo.
echo Run finished with exit code %EXIT_CODE%.
"%PY%" -u -B main.py --report
echo.
if not "%BOSS_DASHBOARD_LAUNCH%"=="1" pause
exit /b %EXIT_CODE%
