@echo off
setlocal enabledelayedexpansion
chcp 936 >nul 2>&1
title 全能创意大师 - 智能启动助手
color 0A

echo.
echo ========================================================
echo         全能创意大师 - 智能启动助手 v5.0
echo ========================================================
echo.
echo  本程序将自动检测并安装运行所需的所有环境
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "VENV_PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"
set "DATA_DIR=%BACKEND_DIR%\data"
set "LOG_DIR=%BACKEND_DIR%\logs"
set "MODEL_DIR=%DATA_DIR%\marker_models"

set "PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "NPM_MIRROR=https://registry.npmmirror.com"
set "PYTHON_DL=https://npm.taobao.org/mirrors/python/3.10.11/python-3.10.11-amd64.exe"
set "NODE_DL=https://npmmirror.com/mirrors/node/v20.11.0/node-v20.11.0-x64.msi"

echo ========================================================
echo  [第一步] 检测 Python 环境
echo ========================================================
echo.
echo  Python 是本软件的核心运行环境，用于处理 AI 对话、
echo  文档解析等智能功能。
echo.
echo  正在检测 Python 是否已安装...
echo.

python --version 2>nul
if errorlevel 1 goto no_python

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo  [OK] Python 已安装，版本: !PY_VER!
goto check_node

:no_python
color 0E
echo  [X] 未检测到 Python 环境
echo.
echo  可能的原因:
echo    1. 电脑尚未安装 Python
echo    2. Python 已安装但未添加到系统路径
echo.
echo  请选择操作:
echo    [Y] 自动下载安装（推荐）
echo    [N] 查看手动安装指南
echo    [S] 跳过检测（已安装但未配置路径）
echo.
choice /c YNS /n /m "  请按键选择: "
if errorlevel 3 goto skip_python
if errorlevel 2 goto manual_python
if errorlevel 1 goto auto_python

:auto_python
echo.
echo  正在准备自动安装 Python 3.10...
echo  下载源: 淘宝镜像（国内加速）
echo  文件大小: 约 27MB
echo  预计时间: 30秒 - 2分钟
echo.
echo  正在下载，请耐心等待...
echo.

powershell -Command "& { $url='!PYTHON_DL!'; $out='%TEMP%\py.exe'; try { $wc=New-Object Net.WebClient; $wc.DownloadFile($url,$out); if(Test-Path $out){Write-Host '[OK] 下载完成'}else{Write-Host '[X] 下载失败'} } catch { Write-Host '[X] 下载出错:' $_.Exception.Message } }"

if exist "%TEMP%\py.exe" (
    echo.
    echo  正在安装 Python...
    echo  安装选项: 自动添加到系统路径
    echo.
    "%TEMP%\py.exe" /passive InstallAllUsers=1 PrependPath=1 Include_test=0
    echo  等待安装完成...
    timeout /t 30 >nul
    echo.
    echo  [OK] Python 安装完成！
    echo  [!] 如系统未识别，请重启电脑后重试
) else (
    echo.
    echo  [X] 自动下载失败，请尝试手动安装
    goto manual_python
)
goto check_node

:manual_python
echo.
echo  ========================================================
echo           Python 手动安装指南
echo  ========================================================
echo.
echo  1. 访问官网下载: https://www.python.org/downloads/
echo  2. 下载 Python 3.10 版本
echo  3. 运行安装程序时，务必勾选:
echo     [Add Python to PATH] - 非常重要！
echo  4. 安装完成后，重新运行本程序
echo.
pause
exit /b 1

:skip_python
echo.
echo  已跳过 Python 检测
echo  如果 Python 未正确安装，后续步骤可能会失败
echo.

:check_node
echo.
echo ========================================================
echo  [第二步] 检测 Node.js 环境
echo ========================================================
echo.
echo  Node.js 是前端界面的运行环境，负责显示网页操作界面。
echo.
echo  正在检测 Node.js 是否已安装...
echo.

node --version 2>nul
if errorlevel 1 goto no_node

for /f "tokens=*" %%v in ('node --version 2^>^&1') do set "NODE_VER=%%v"
echo  [OK] Node.js 已安装，版本: !NODE_VER!
goto create_config

:no_node
color 0E
echo  [X] 未检测到 Node.js 环境
echo.
echo  请选择操作:
echo    [Y] 自动下载安装（推荐）
echo    [N] 查看手动安装指南
echo    [S] 跳过检测
echo.
choice /c YNS /n /m "  请按键选择: "
if errorlevel 3 goto skip_node
if errorlevel 2 goto manual_node
if errorlevel 1 goto auto_node

:auto_node
echo.
echo  正在准备自动安装 Node.js 20 LTS...
echo  下载源: npmmirror 镜像（国内加速）
echo  文件大小: 约 30MB
echo  预计时间: 30秒 - 2分钟
echo.
echo  正在下载，请耐心等待...
echo.

powershell -Command "& { $url='!NODE_DL!'; $out='%TEMP%\node.msi'; try { $wc=New-Object Net.WebClient; $wc.DownloadFile($url,$out); if(Test-Path $out){Write-Host '[OK] 下载完成'}else{Write-Host '[X] 下载失败'} } catch { Write-Host '[X] 下载出错:' $_.Exception.Message } }"

if exist "%TEMP%\node.msi" (
    echo.
    echo  正在安装 Node.js...
    msiexec /i "%TEMP%\node.msi" /passive /norestart
    echo  等待安装完成...
    timeout /t 30 >nul
    echo.
    echo  [OK] Node.js 安装完成！
) else (
    echo.
    echo  [X] 自动下载失败，请尝试手动安装
    goto manual_node
)
goto create_config

:manual_node
echo.
echo  ========================================================
echo           Node.js 手动安装指南
echo  ========================================================
echo.
echo  1. 访问官网下载: https://nodejs.org/zh-cn/download/
echo  2. 下载 LTS 长期支持版
echo  3. 安装完成后，重新运行本程序
echo.
pause
exit /b 1

:skip_node
echo.
echo  已跳过 Node.js 检测
echo.

:create_config
echo.
echo ========================================================
echo  [第三步] 创建配置文件和数据目录
echo ========================================================
echo.
echo  正在创建必要的数据存储目录...
echo.

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\chroma" mkdir "%DATA_DIR%\chroma"
if not exist "%DATA_DIR%\uploads" mkdir "%DATA_DIR%\uploads"
if not exist "%DATA_DIR%\knowledge_graphs" mkdir "%DATA_DIR%\knowledge_graphs"
if not exist "%MODEL_DIR%" mkdir "%MODEL_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo  [OK] 数据目录创建完成
echo.

if not exist "%BACKEND_DIR%\.env" (
    echo  正在生成后端配置文件...
    (
        echo APP_NAME=全能创意大师
        echo DEBUG=True
        echo HOST=0.0.0.0
        echo PORT=8000
        echo DATABASE_URL=sqlite+aiosqlite:///./data/creative_master.db
        echo SECRET_KEY=auto-generated-please-change
        echo LOG_LEVEL=INFO
        echo LOG_DIR=./logs
        echo CHROMA_PERSIST_DIR=./data/chroma
        echo UPLOAD_DIR=./data/uploads
        echo MARKER_MODEL_DIR=./data/marker_models
    ) > "%BACKEND_DIR%\.env"
    echo  [OK] 后端配置已生成
)

if not exist "%FRONTEND_DIR%\.env.local" (
    echo  正在生成前端配置文件...
    (
        echo VITE_BACKEND_URL=http://localhost:8000
        echo VITE_FRONTEND_PORT=5173
    ) > "%FRONTEND_DIR%\.env.local"
    echo  [OK] 前端配置已生成
)

call npm config set registry !NPM_MIRROR! >nul 2>&1
echo  [OK] npm 镜像源已配置

echo.
echo ========================================================
echo  [第四步] 检测并安装依赖包
echo ========================================================
echo.
echo  依赖包是软件运行所需的"零件库"，首次运行需要下载。
echo.

if not exist "%VENV_PYTHON%" (
    echo  正在创建 Python 虚拟环境...
    echo  虚拟环境是一个独立的"沙盒"，不会影响其他程序。
    echo.
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    echo  [OK] 虚拟环境创建完成
    echo.
    
    echo  正在配置 pip 下载源...
    "%VENV_PYTHON%" -m pip config set global.index-url !PYPI_MIRROR! >nul 2>&1
    echo  [OK] pip 已配置清华镜像源
    echo.
    
    echo  正在安装后端依赖包...
    echo  需要下载约 200+ 个模块，预计 3-5 分钟
    echo.
    echo  [1/2] 升级 pip...
    "%VENV_PYTHON%" -m pip install --upgrade pip -q
    
    echo  [2/2] 安装功能模块...
    "%VENV_PYTHON%" -m pip install -r requirements.txt -q -i !PYPI_MIRROR!
    
    if errorlevel 1 (
        echo  [!] 安装遇到问题，尝试备用镜像源...
        "%VENV_PYTHON%" -m pip install -r requirements.txt -q -i https://mirrors.aliyun.com/pypi/simple/
    )
    
    echo  [OK] 后端依赖安装完成
    cd /d "%PROJECT_DIR%"
) else (
    echo  [OK] Python 虚拟环境已存在
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo.
    echo  正在安装前端依赖包...
    echo  需要下载约 1000+ 个模块，预计 2-3 分钟
    echo.
    cd /d "%FRONTEND_DIR%"
    call npm install --silent
    
    if errorlevel 1 (
        echo  [!] 安装遇到问题，尝试重新安装...
        call npm install --silent
    )
    
    echo  [OK] 前端依赖安装完成
    cd /d "%PROJECT_DIR%"
) else (
    echo  [OK] 前端依赖包已存在
)

echo.
echo ========================================================
echo  [第五步] 启动服务
echo ========================================================
echo.
echo  正在清理可能存在的旧进程...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 >nul
echo  [OK] 清理完成
echo.

echo  正在启动后端服务...
echo  端口: 8000 - AI 核心引擎
cd /d "%BACKEND_DIR%"
start /B "" "%VENV_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
timeout /t 3 >nul

echo  正在启动前端服务...
echo  端口: 5173 - 网页操作界面
cd /d "%FRONTEND_DIR%"
start /B "" npm run dev
timeout /t 3 >nul

cd /d "%PROJECT_DIR%"

color 0B
echo.
echo ========================================================
echo            启动完成！系统已就绪
echo ========================================================
echo.
echo  访问地址:
echo    主界面: http://localhost:5173
echo    API文档: http://localhost:8000/docs
echo.
echo  注意事项:
echo    - 请勿关闭此窗口，否则服务将停止
echo    - 按 Ctrl+C 可停止服务
echo    - 下次启动将更快（依赖包已安装）
echo.
echo  浏览器将在 5 秒后自动打开...
timeout /t 5 >nul
start http://localhost:5173

echo.
:WAIT
timeout /t 60 >nul
goto WAIT
