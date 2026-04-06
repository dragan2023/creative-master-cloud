@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ========================================
:: 全能创意大师 - 镜像导出脚本
:: 功能：将 Docker 镜像导出为 tar 文件
:: 用途：传输到无法访问镜像仓库的服务器
:: ========================================

echo.
echo ========================================
echo   全能创意大师 - 镜像导出
echo ========================================
echo.

set PROJECT_ROOT=%~dp0..
set IMAGE_NAME=creative-master
set OUTPUT_DIR=%PROJECT_ROOT%\dist\images

:: 从 version.json 动态读取版本号
for /f "tokens=2 delims=:," %%a in ('findstr /c:"current_version" "%PROJECT_ROOT%\version.json"') do (
    for /f "tokens=* delims= " %%b in ("%%a") do set VERSION=%%b
)
set VERSION=%VERSION:"=%
echo [信息] 当前版本: %VERSION%

:: 创建输出目录
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: 检查镜像是否存在
docker images %IMAGE_NAME%:%VERSION% --format "{{.ID}}" >nul 2>&1
if errorlevel 1 (
    echo [错误] 镜像 %IMAGE_NAME%:%VERSION% 不存在
    echo [提示] 请先运行 build-and-push.bat 构建镜像
    pause
    exit /b 1
)

echo [信息] 导出镜像: %IMAGE_NAME%:%VERSION%
echo [信息] 输出目录: %OUTPUT_DIR%
echo.

:: 导出镜像
set OUTPUT_FILE=%OUTPUT_DIR%\%IMAGE_NAME%-v%VERSION%.tar
echo [执行] docker save -o %OUTPUT_FILE% %IMAGE_NAME%:%VERSION%
docker save -o "%OUTPUT_FILE%" %IMAGE_NAME%:%VERSION%

if errorlevel 1 (
    echo [错误] 镜像导出失败
    pause
    exit /b 1
)

:: 同时导出 latest 标签
echo [执行] 标记 latest 并导出...
docker tag %IMAGE_NAME%:%VERSION% %IMAGE_NAME%:latest

:: 显示文件大小
for %%A in ("%OUTPUT_FILE%") do set SIZE=%%~zA
set /a SIZE_MB=%SIZE% / 1048576

echo.
echo ========================================
echo   导出完成！
echo ========================================
echo.
echo 文件: %OUTPUT_FILE%
echo 大小: %SIZE_MB% MB
echo.
echo 传输到服务器后，执行以下命令加载镜像：
echo   docker load -i %IMAGE_NAME%-v%VERSION%.tar
echo   docker tag %IMAGE_NAME%:%VERSION% %IMAGE_NAME%:latest
echo.
echo 然后执行部署：
echo   docker compose -f docker-compose.cloud.yml up -d
echo.
pause
