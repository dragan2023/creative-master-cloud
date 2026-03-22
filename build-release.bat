@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Creative Master - Build Release Tool
color 0B

echo.
echo ========================================================
echo         Creative Master - Release Builder v2.0
echo ========================================================
echo.

echo  Building clean release package...
echo.

set "PROJECT_DIR=%~dp0"

:: 从 version.json 读取版本号
set "VERSION_FILE=%PROJECT_DIR%version.json"
if exist "%VERSION_FILE%" (
    for /f "tokens=2 delims=:," %%a in ('findstr /c:"\"current_version\"" "%VERSION_FILE%"') do (
        set "VERSION=%%a"
        set "VERSION=!VERSION:\"=!"
        set "VERSION=!VERSION: =!"
    )
)
if not defined VERSION set "VERSION=1.0.0"
echo  Version: %VERSION%

set "DIST_DIR=%PROJECT_DIR%dist\creative-master-release-v%VERSION%"

:: 创建发行版目录
echo [1/5] Creating release directory...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"
echo   [OK] Done
echo.

:: 复制根目录文件
echo [2/5] Copying root files...
copy "%PROJECT_DIR%start.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%start.ps1" "%DIST_DIR%\" >nul 2>&1
copy "%PROJECT_DIR%run-backend.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%run-frontend.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%smart-install.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%stop.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%docker-compose.yml" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%version.json" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%check-gpu.py" "%DIST_DIR%\" >nul 2>&1
copy "%PROJECT_DIR%使用手册.txt" "%DIST_DIR%\" >nul
echo   [OK] Done
echo.

:: 复制后端（排除开发环境）
echo [3/5] Copying backend code...
mkdir "%DIST_DIR%\backend"

:: 复制必要目录
xcopy "%PROJECT_DIR%backend\app" "%DIST_DIR%\backend\app\" /E /I /Q /EXCLUDE:%PROJECT_DIR%pack-exclude.txt
xcopy "%PROJECT_DIR%backend\alembic" "%DIST_DIR%\backend\alembic\" /E /I /Q /EXCLUDE:%PROJECT_DIR%pack-exclude.txt
xcopy "%PROJECT_DIR%backend\scripts" "%DIST_DIR%\backend\scripts\" /E /I /Q /EXCLUDE:%PROJECT_DIR%pack-exclude.txt

:: 复制必要文件
copy "%PROJECT_DIR%backend\requirements.txt" "%DIST_DIR%\backend\" >nul
copy "%PROJECT_DIR%backend\alembic.ini" "%DIST_DIR%\backend\" >nul
copy "%PROJECT_DIR%backend\Dockerfile" "%DIST_DIR%\backend\" >nul

:: 创建空的必要目录
mkdir "%DIST_DIR%\backend\data\chroma"
mkdir "%DIST_DIR%\backend\data\uploads"
mkdir "%DIST_DIR%\backend\data\knowledge_graphs"
mkdir "%DIST_DIR%\backend\logs"

:: 生成 UTF-8 编码的 .env 文件（避免中文编码问题）
echo   Generating backend .env file...
(
echo APP_NAME=Creative Master
echo DEBUG=True
echo HOST=0.0.0.0
echo PORT=8000
echo DATABASE_URL=sqlite+aiosqlite:///./data/creative_master.db
echo SECRET_KEY=auto-generated-please-change
echo LOG_LEVEL=INFO
echo LOG_DIR=./logs
echo CHROMA_PERSIST_DIR=./data/chroma
echo UPLOAD_DIR=./data/uploads
echo.
echo # ==================== 批量生成速率控制 ====================
echo BATCH_REQUEST_INTERVAL=1.5
echo BATCH_RETRY_ON_RATE_LIMIT=true
echo BATCH_MAX_RETRIES=3
echo BATCH_RETRY_BASE_DELAY=2.0
) > "%DIST_DIR%\backend\.env"

echo   [OK] Backend copied
echo.

:: 复制前端（排除 node_modules）
echo [4/5] Copying frontend code...
mkdir "%DIST_DIR%\frontend"

xcopy "%PROJECT_DIR%frontend\src" "%DIST_DIR%\frontend\src\" /E /I /Q
xcopy "%PROJECT_DIR%frontend\public" "%DIST_DIR%\frontend\public\" /E /I /Q

copy "%PROJECT_DIR%frontend\package.json" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\package-lock.json" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\vite.config.js" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\index.html" "%DIST_DIR%\frontend\" >nul

:: 生成前端 .env.local 文件
echo   Generating frontend .env.local file...
(
echo # 前端环境配置
echo VITE_BACKEND_URL=http://127.0.0.1:8000
echo VITE_FRONTEND_PORT=5173
) > "%DIST_DIR%\frontend\.env.local"

echo   [OK] Frontend copied
echo.

:: 创建安装日志目录
echo. 2>"%DIST_DIR%\install.log"

:: 计算大小
echo ========================================================
echo.
color 0A
echo ========================================================
echo           Build Complete! Release Ready
echo ========================================================
echo.
echo  Release location: %DIST_DIR%
echo.
echo  Included files:
echo    - start.bat (Main launcher with auto-setup)
echo    - run-backend.bat (Backend service)
echo    - run-frontend.bat (Frontend service)
echo    - smart-install.bat (Dependency installer)
echo    - stop.bat (Service stopper)
echo    - check-gpu.py (GPU diagnostic tool)
echo.
echo  Next steps:
echo    1. Test by running start.bat
echo    2. Compress the release folder to ZIP
echo    3. Upload to GitHub Releases
echo.
echo ========================================================
echo.

:: 打开发行版目录
explorer "%DIST_DIR%"

pause
exit /b 0
