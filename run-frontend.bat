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

:: 检查是否存在 .env.production（异地运行时需要）
if exist ".env.production" (
    echo [INFO] Using production environment configuration...
    echo [INFO] If running in different location, please ensure VITE_API_BASE_URL is set correctly in .env.production
    echo.
)

:: 启动前端服务（Vite 会自动读取 .env.local 或 .env.production 中的配置）
npm run dev
