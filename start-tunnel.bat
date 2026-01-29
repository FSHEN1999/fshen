@echo off
echo ========================================
echo   Cloudflare Tunnel - 德州扑克后端
echo ========================================
echo.
echo 正在启动隧道...
echo.
cloudflared tunnel --url http://localhost:8000 --loglevel info
