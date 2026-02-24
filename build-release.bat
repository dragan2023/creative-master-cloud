@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1
title 全能创意大师 - 发行版打包工具
color 0B

echo.
echo ========================================================
echo         全能创意大师 - 发行版打包工具 v1.1
echo ========================================================
echo.
echo  自动移除开发环境文件，生成纯净发行版
echo.

set "PROJECT_DIR=%~dp0"
set "DIST_DIR=%PROJECT_DIR%dist\全能创意大师-发行版"

:: 创建发行版目录
echo [1/4] 创建发行版目录...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"
echo   [OK] 完成
echo.

:: 复制根目录文件
echo [2/4] 复制根目录文件...
copy "%PROJECT_DIR%start.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%smart-install.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%stop.bat" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%docker-compose.yml" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%.env.example" "%DIST_DIR%\" >nul
copy "%PROJECT_DIR%.gitignore" "%DIST_DIR%\" >nul
echo   [OK] 完成
echo.

:: 复制后端（排除开发环境）
echo [3/4] 复制后端代码...
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
mkdir "%DIST_DIR%\backend\data\marker_models"
mkdir "%DIST_DIR%\backend\logs"

:: 复制 .env.example 作为模板
copy "%PROJECT_DIR%backend\.env" "%DIST_DIR%\backend\.env.example" >nul 2>&1

echo   [OK] 完成
echo.

:: 复制前端（排除 node_modules）
echo [4/4] 复制前端代码...
mkdir "%DIST_DIR%\frontend"

xcopy "%PROJECT_DIR%frontend\src" "%DIST_DIR%\frontend\src\" /E /I /Q
xcopy "%PROJECT_DIR%frontend\public" "%DIST_DIR%\frontend\public\" /E /I /Q

copy "%PROJECT_DIR%frontend\package.json" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\package-lock.json" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\vite.config.js" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\index.html" "%DIST_DIR%\frontend\" >nul
copy "%PROJECT_DIR%frontend\.env.example" "%DIST_DIR%\frontend\" >nul 2>&1

echo   [OK] 完成
echo.

:: 计算大小
echo ========================================================
echo.
color 0A
echo ========================================================
echo           打包完成！发行版已就绪
echo ========================================================
echo.
echo  发行版位置: %DIST_DIR%
echo.
echo  用户使用方法:
echo    方式一: 双击 start.bat 自动安装并启动
echo    方式二: 先运行 smart-install.bat 安装环境，再运行 start.bat
echo.
echo ========================================================
echo.

:: 打开发行版目录
explorer "%DIST_DIR%"

pause
