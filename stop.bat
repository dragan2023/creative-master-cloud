@echo off
chcp 65001 >nul
title 全能创意大师 - 停止服务
color 0C

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║           全能创意大师 - 停止服务                          ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo  正在安全停止所有服务...
echo.

:: 关闭 Python 进程（后端）
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM python.exe >nul 2>&1
    echo  √ 后端服务已停止 (Python)
) else (
    echo  - 后端服务未运行
)

:: 关闭 Node 进程（前端）
tasklist /FI "IMAGENAME eq node.exe" 2>NUL | find /I /N "node.exe">NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM node.exe >nul 2>&1
    echo  √ 前端服务已停止 (Node.js)
) else (
    echo  - 前端服务未运行
)

:: 等待进程完全退出
timeout /t 2 >nul

echo.
echo ════════════════════════════════════════════════════════════
echo.
color 0A
echo  ✓ 所有服务已安全停止
echo.
echo  如需重新启动，请双击 start.bat
echo.
echo ════════════════════════════════════════════════════════════
echo.

timeout /t 3 >nul
