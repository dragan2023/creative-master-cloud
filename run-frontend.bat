@echo off
REM 前端服务启动脚本
cd /d "%~dp0frontend"

:: 检查 node_modules 是否存在
if not exist "node_modules" (
    echo [ERROR] Frontend dependencies not installed!
    echo Please run start.bat first to install dependencies.
    echo.
    pause
    exit /b 1
)

:: 启动前端服务（Vite 会自动读取 .env.local 中的配置）
npm run dev
