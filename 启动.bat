@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title 全能创意大师 - 启动助手
color 0A

echo.
echo ========================================================
echo         全能创意大师 - 正在启动...
echo ========================================================
echo.

:: 直接调用 start.bat（已包含完整的环境检测和启动逻辑）
call "%~dp0start.bat"
exit /b %errorlevel%
