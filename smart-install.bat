@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1
title 全能创意大师 - 智能环境安装助手
color 0B

echo.
echo ========================================================
echo         全能创意大师 - 智能环境安装助手 v1.0
echo ========================================================
echo.
echo  本工具将自动检测并安装以下环境：
echo    - Python 3.10 (运行基础)
echo    - Node.js 20 LTS (前端支持)
echo    - Python 依赖包 (后端模块)
echo    - Node 依赖包 (前端模块)
echo.
echo  所有下载均使用国内镜像源加速。
echo.
echo ========================================================
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "VENV_PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"

set "PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PYPI_MIRROR_2=https://mirrors.aliyun.com/pypi/simple/"
set "NPM_MIRROR=https://registry.npmmirror.com"
set "PYTHON_DL=https://npm.taobao.org/mirrors/python/3.10.11/python-3.10.11-amd64.exe"
set "NODE_DL=https://npmmirror.com/mirrors/node/v20.11.0/node-v20.11.0-x64.msi"

set "INSTALL_PYTHON=0"
set "INSTALL_NODE=0"
set "INSTALL_PY_DEPS=0"
set "INSTALL_NP_DEPS=0"

echo ========================================================
echo  [检测阶段] 开始扫描系统环境...
echo ========================================================
echo.

echo [1/4] Python 环境...
python --version 2>nul
if errorlevel 1 (
    echo       状态: 未安装
    set "INSTALL_PYTHON=1"
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo       已安装: Python %%v
)

echo [2/4] Node.js 环境...
node --version 2>nul
if errorlevel 1 (
    echo       状态: 未安装
    set "INSTALL_NODE=1"
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo       已安装: Node.js %%v
)

echo [3/4] Python 依赖包...
if exist "%VENV_PYTHON%" (
    echo       虚拟环境: 已存在
) else (
    echo       虚拟环境: 未创建
    set "INSTALL_PY_DEPS=1"
)

echo [4/4] Node 依赖包...
if exist "%FRONTEND_DIR%\node_modules" (
    echo       node_modules: 已存在
) else (
    echo       node_modules: 未安装
    set "INSTALL_NP_DEPS=1"
)

echo.
echo ========================================================
echo  [分析结果]
echo ========================================================
echo.

if !INSTALL_PYTHON!==1 (echo  [需安装] Python 3.10) else (echo  [已就绪] Python)
if !INSTALL_NODE!==1 (echo  [需安装] Node.js 20 LTS) else (echo  [已就绪] Node.js)
if !INSTALL_PY_DEPS!==1 (echo  [需安装] Python 依赖包) else (echo  [已就绪] Python 依赖包)
if !INSTALL_NP_DEPS!==1 (echo  [需安装] Node 依赖包) else (echo  [已就绪] Node 依赖包)
echo.

set "NEED_INSTALL=0"
if !INSTALL_PYTHON!==1 set "NEED_INSTALL=1"
if !INSTALL_NODE!==1 set "NEED_INSTALL=1"
if !INSTALL_PY_DEPS!==1 set "NEED_INSTALL=1"
if !INSTALL_NP_DEPS!==1 set "NEED_INSTALL=1"

if !NEED_INSTALL!==0 (
    color 0A
    echo  所有环境已就绪，无需安装！
    echo.
    echo  您可以直接运行 start.bat 启动程序。
    echo.
    pause
    exit /b 0
)

echo ========================================================
echo  [安装阶段]
echo ========================================================
echo.
echo  是否开始自动安装？
echo.
choice /c YN /n /m "  [Y] 开始安装  [N] 取消: "
if errorlevel 2 goto :cancel
echo.

if !INSTALL_PYTHON!==1 (
    echo ========================================================
    echo  [1/4] 安装 Python 3.10
    echo ========================================================
    echo.
    echo  下载源: 淘宝镜像
    echo  文件大小: 约 27MB
    echo.
    echo  正在下载...
    powershell -Command "(New-Object Net.WebClient).DownloadFile('!PYTHON_DL!', '%TEMP%\py.exe')"
    if exist "%TEMP%\py.exe" (
        echo  正在安装...
        "%TEMP%\py.exe" /passive InstallAllUsers=1 PrependPath=1
        timeout /t 30 >nul
        echo  [OK] Python 安装完成
    ) else (
        echo  [X] 下载失败
    )
    echo.
)

if !INSTALL_NODE!==1 (
    echo ========================================================
    echo  [2/4] 安装 Node.js 20 LTS
    echo ========================================================
    echo.
    echo  下载源: npmmirror 镜像
    echo  文件大小: 约 30MB
    echo.
    echo  正在下载...
    powershell -Command "(New-Object Net.WebClient).DownloadFile('!NODE_DL!', '%TEMP%\node.msi')"
    if exist "%TEMP%\node.msi" (
        echo  正在安装...
        msiexec /i "%TEMP%\node.msi" /passive /norestart
        timeout /t 30 >nul
        echo  [OK] Node.js 安装完成
    ) else (
        echo  [X] 下载失败
    )
    echo.
)

if !INSTALL_PY_DEPS!==1 (
    echo ========================================================
    echo  [3/4] 安装 Python 依赖包
    echo ========================================================
    echo.
    echo  正在创建虚拟环境...
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    echo  [OK] 虚拟环境创建完成
    echo.
    echo  正在安装依赖包 (3-5分钟)...
    "%VENV_PYTHON%" -m pip install --upgrade pip -q
    "%VENV_PYTHON%" -m pip install -r requirements.txt -q -i !PYPI_MIRROR!
    echo  [OK] Python 依赖包安装完成
    cd /d "%PROJECT_DIR%"
    echo.
)

if !INSTALL_NP_DEPS!==1 (
    echo ========================================================
    echo  [4/4] 安装 Node 依赖包
    echo ========================================================
    echo.
    call npm config set registry !NPM_MIRROR! >nul 2>&1
    echo  正在安装依赖包 (2-3分钟)...
    cd /d "%FRONTEND_DIR%"
    call npm install --silent
    echo  [OK] Node 依赖包安装完成
    cd /d "%PROJECT_DIR%"
    echo.
)

color 0A
echo ========================================================
echo           安装完成！
echo ========================================================
echo.
echo  所有环境已就绪！
echo.
echo  下一步: 双击运行 start.bat 启动程序
echo.
pause
exit /b 0

:cancel
echo.
echo  已取消安装。
pause
exit /b 1
