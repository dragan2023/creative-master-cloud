@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ========================================
:: 全能创意大师 - 本地完整构建脚本
:: 功能：前端构建 + 后端打包 + Docker镜像推送
:: ========================================

echo.
echo ========================================
echo   全能创意大师 - 本地完整构建
echo ========================================
echo.

:: 设置变量
set PROJECT_ROOT=%~dp0..
set FRONTEND_DIR=%PROJECT_ROOT%\frontend
set BACKEND_DIR=%PROJECT_ROOT%\backend
set IMAGE_NAME=creative-master
set REGISTRY=registry.cn-hangzhou.aliyuncs.com
set NAMESPACE=your-namespace

:: 从 version.json 动态读取版本号
for /f "tokens=2 delims=:," %%a in ('findstr /c:"current_version" "%PROJECT_ROOT%\version.json"') do (
    for /f "tokens=* delims= " %%b in ("%%a") do set VERSION=%%b
)
set VERSION=%VERSION:"=%
echo [信息] 当前版本: %VERSION%

:: 检查 Docker 是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    exit /b 1
)

:: ========================================
:: 第一步：前端构建
:: ========================================
echo.
echo [1/4] 前端构建中...
cd /d %FRONTEND_DIR%

:: 检查 node_modules
if not exist "node_modules" (
    echo [信息] 安装前端依赖...
    call npm install
    if errorlevel 1 (
        echo [错误] 前端依赖安装失败
        exit /b 1
    )
)

:: 构建
echo [信息] 执行 npm run build...
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败
    exit /b 1
)

echo [成功] 前端构建完成，产物已输出到 backend/app/static
echo.

:: ========================================
:: 第二步：后端依赖准备（可选，用于验证）
:: ========================================
echo [2/4] 验证后端依赖...
cd /d %BACKEND_DIR%

:: 检查 requirements.txt 是否存在
if not exist "requirements.txt" (
    echo [错误] requirements.txt 不存在
    exit /b 1
)

echo [成功] 后端依赖配置正常
echo.

:: ========================================
:: 第三步：Docker 镜像构建
:: ========================================
echo [3/4] 构建 Docker 镜像...
cd /d %PROJECT_ROOT%

:: 构建后端镜像（包含前端静态文件）
echo [信息] 构建镜像: %IMAGE_NAME%:%VERSION%
docker build -f backend/Dockerfile.prod -t %IMAGE_NAME%:%VERSION% -t %IMAGE_NAME%:latest ./backend
if errorlevel 1 (
    echo [错误] Docker 镜像构建失败
    exit /b 1
)

echo [成功] Docker 镜像构建完成
echo.

:: ========================================
:: 第四步：推送镜像到仓库（可选）
:: ========================================
echo [4/4] 推送镜像到仓库...
echo.
echo 请选择镜像仓库：
echo   1. 阿里云容器镜像服务（推荐国内用户）
echo   2. Docker Hub
echo   3. 跳过推送（仅本地构建）
echo.
set /p CHOICE="请输入选项 (1/2/3): "

if "%CHOICE%"=="1" (
    :: 阿里云容器镜像服务
    echo [信息] 登录阿里云容器镜像服务...
    docker login --username=your-username %REGISTRY%
    
    echo [信息] 标记镜像...
    docker tag %IMAGE_NAME%:%VERSION% %REGISTRY%/%NAMESPACE%/%IMAGE_NAME%:%VERSION%
    docker tag %IMAGE_NAME%:latest %REGISTRY%/%NAMESPACE%/%IMAGE_NAME%:latest
    
    echo [信息] 推送镜像...
    docker push %REGISTRY%/%NAMESPACE%/%IMAGE_NAME%:%VERSION%
    docker push %REGISTRY%/%NAMESPACE%/%IMAGE_NAME%:latest
    
    echo [成功] 镜像已推送到阿里云
    echo.
    echo 云端部署命令：
    echo   docker pull %REGISTRY%/%NAMESPACE%/%IMAGE_NAME%:latest
    echo   docker tag %REGISTRY%/%NAMESPACE%/%IMAGE_NAME%:latest %IMAGE_NAME%:latest
    
) else if "%CHOICE%"=="2" (
    :: Docker Hub
    echo [信息] 登录 Docker Hub...
    docker login
    
    echo [信息] 标记镜像...
    docker tag %IMAGE_NAME%:%VERSION% your-dockerhub-username/%IMAGE_NAME%:%VERSION%
    docker tag %IMAGE_NAME%:latest your-dockerhub-username/%IMAGE_NAME%:latest
    
    echo [信息] 推送镜像...
    docker push your-dockerhub-username/%IMAGE_NAME%:%VERSION%
    docker push your-dockerhub-username/%IMAGE_NAME%:latest
    
    echo [成功] 镜像已推送到 Docker Hub
    
) else (
    echo [信息] 跳过推送，镜像仅保存在本地
)

echo.
echo ========================================
echo   构建完成！
echo ========================================
echo.
echo 本地镜像列表：
docker images %IMAGE_NAME%
echo.
echo 下一步：
echo   1. 推送镜像到仓库后，在云端服务器执行部署脚本
echo   2. 或导出镜像文件传输到服务器：
echo      docker save -o %IMAGE_NAME%-%VERSION%.tar %IMAGE_NAME%:%VERSION%
echo.
pause
