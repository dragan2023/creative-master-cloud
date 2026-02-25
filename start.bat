@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: 全能创意大师 - 发行版启动脚本 v8.0
:: 功能：环境检测、端口清理、依赖安装、服务启动
:: ============================================================

title 全能创意大师 - 启动脚本

:: 设置项目路径
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "DATA_DIR=%BACKEND_DIR%data"

:: 端口配置
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

echo.
echo ========================================================
echo     全能创意大师 - 智能内容生成平台
echo ========================================================
echo.

:: [第零步] 检测并配置 PowerShell 环境
echo ========================================================
echo  [步骤 0/8] 检测 PowerShell 环境
echo ========================================================

set "PS_OK=0"
set "PS_PATH="

:: 首先检查 PowerShell 是否已经在 PATH 中可用
powershell -Command "Get-Host" >nul 2>&1
if not errorlevel 1 (
    set "PS_OK=1"
    echo  [OK] PowerShell 已在系统 PATH 中可用
    goto ps_done
)

echo  [!] PowerShell 未在 PATH 中找到，正在搜索...

:: 搜索常见的 PowerShell 安装位置
if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
    set "PS_PATH=%SystemRoot%\System32\WindowsPowerShell\v1.0"
    goto found_ps
)

if exist "%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" (
    set "PS_PATH=%SystemRoot%\SysWOW64\WindowsPowerShell\v1.0"
    goto found_ps
)

if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
    set "PS_PATH=%ProgramFiles%\PowerShell\7"
    goto found_ps
)

if exist "%ProgramFiles(x86)%\PowerShell\7\pwsh.exe" (
    set "PS_PATH=%ProgramFiles(x86)%\PowerShell\7"
    goto found_ps
)

echo  [ERROR] 未找到 PowerShell，请确保 Windows 系统完整
goto skip_ps_config

:found_ps
echo  [OK] 找到 PowerShell: !PS_PATH!

set "PS_EXE=powershell.exe"
if exist "!PS_PATH!\pwsh.exe" set "PS_EXE=pwsh.exe"

echo  [*] 正在将 PowerShell 添加到用户 PATH 环境变量...
"!PS_PATH!\!PS_EXE!" -Command "[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';!PS_PATH!', 'User')" 2>nul

set "PATH=!PATH!;!PS_PATH!"
echo  [OK] PowerShell 已添加到 PATH（重启终端后永久生效）

:ps_done
:skip_ps_config
echo.

:: [第一步] 检测 Python 环境
echo ========================================================
echo  [步骤 1/8] 检测 Python 环境
echo ========================================================

python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] 未检测到 Python
    echo.
    echo  请安装 Python 3.10 或更高版本
    echo  下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo  [OK] Python 版本: !PYTHON_VERSION!

for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if !PY_MAJOR! LSS 3 (
    echo  [ERROR] Python 版本过低，需要 3.10 或更高版本
    pause
    exit /b 1
)

if !PY_MAJOR! EQU 3 (
    if !PY_MINOR! LSS 10 (
        echo  [ERROR] Python 版本过低，需要 3.10 或更高版本
        pause
        exit /b 1
    )
)

echo.

:: [第二步] 检测 Node.js 环境
echo ========================================================
echo  [步骤 2/8] 检测 Node.js 环境
echo ========================================================

node --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] 未检测到 Node.js
    echo.
    echo  请安装 Node.js 20 或更高版本
    echo  下载地址: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

for /f "tokens=1 delims=v" %%v in ('node --version 2^>^&1') do set NODE_VERSION=%%v
echo  [OK] Node.js 版本: !NODE_VERSION!

for /f "tokens=1 delims=." %%a in ("!NODE_VERSION!") do set NODE_MAJOR=%%a

if !NODE_MAJOR! LSS 20 (
    echo  [WARNING] Node.js 版本过低，建议使用 20 或更高版本
)

echo.

:: [第三步] 检测并清理端口占用（提前执行）
echo ========================================================
echo  [步骤 3/8] 检测并清理端口占用
echo ========================================================
echo.

:: 调用端口清理函数
call :CleanPort !BACKEND_PORT! "后端服务"
call :CleanPort !FRONTEND_PORT! "前端服务"

echo  [OK] 端口清理完成
echo.

:: [第四步] 创建必要的目录和配置文件
echo ========================================================
echo  [步骤 4/8] 创建必要的目录和配置文件
echo ========================================================

if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%DATA_DIR%\chroma" mkdir "%DATA_DIR%\chroma"
if not exist "%DATA_DIR%\uploads" mkdir "%DATA_DIR%\uploads"
if not exist "%DATA_DIR%\knowledge_graphs" mkdir "%DATA_DIR%\knowledge_graphs"
if not exist "%BACKEND_DIR%\logs" mkdir "%BACKEND_DIR%\logs"

echo  [OK] 数据目录创建完成

if not exist "%BACKEND_DIR%\.env" (
    echo  [*] 正在生成后端配置文件...
    (
        echo APP_NAME=Creative Master
        echo DEBUG=True
        echo HOST=0.0.0.0
        echo PORT=!BACKEND_PORT!
        echo DATABASE_URL=sqlite+aiosqlite:///./data/creative_master.db
        echo SECRET_KEY=auto-generated-please-change
        echo LOG_LEVEL=INFO
        echo LOG_DIR=./logs
        echo CHROMA_PERSIST_DIR=./data/chroma
        echo UPLOAD_DIR=./data/uploads
        echo MARKER_MODEL_DIR=./data/marker_models
    ) > "%BACKEND_DIR%\.env"
    echo  [OK] 后端配置文件已生成
) else (
    echo  [OK] 后端配置文件已存在
)

if not exist "%FRONTEND_DIR%\.env.local" (
    echo  [*] 正在生成前端配置文件...
    (
        echo VITE_BACKEND_URL=http://localhost:!BACKEND_PORT!
        echo VITE_FRONTEND_PORT=!FRONTEND_PORT!
    ) > "%FRONTEND_DIR%\.env.local"
    echo  [OK] 前端配置文件已生成
) else (
    echo  [OK] 前端配置文件已存在
)

echo.

:: [第五步] 检查并安装依赖
echo ========================================================
echo  [步骤 5/8] 检查并安装依赖
echo ========================================================

if not exist "%BACKEND_DIR%\venv" (
    echo  [*] 正在创建 Python 虚拟环境...
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    echo  [OK] 虚拟环境创建完成
)

call "%BACKEND_DIR%\venv\Scripts\activate.bat"

echo  [*] 正在检查后端依赖...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo  [*] 正在安装后端依赖（使用国内镜像加速）...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo  [WARNING] 国内镜像安装失败，尝试默认源...
        pip install -r requirements.txt
    )
    echo  [OK] 后端依赖安装完成
    
    :: 检测 GPU 并安装对应版本的 PyTorch
    echo.
    echo  [*] 正在检测 GPU 环境...
    nvidia-smi >nul 2>&1
    if not errorlevel 1 (
        echo  [OK] 检测到 NVIDIA GPU，正在安装 GPU 版本 PyTorch...
        pip uninstall torch torchvision torchaudio -y >nul 2>&1
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126 -i https://pypi.tuna.tsinghua.edu.cn/simple
        if errorlevel 1 (
            echo  [WARNING] GPU 版本安装失败，尝试默认源...
            pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
        )
        echo  [OK] GPU 版本 PyTorch 安装完成
    ) else (
        echo  [INFO] 未检测到 NVIDIA GPU，使用 CPU 版本 PyTorch
    )
) else (
    echo  [OK] 后端依赖已安装
    
    :: 检查 PyTorch CUDA 支持（使用虚拟环境中的 Python）
    "%BACKEND_DIR%\venv\Scripts\python.exe" -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
    if errorlevel 1 (
        echo  [!] 当前 PyTorch 不支持 CUDA，检查是否有 GPU...
        nvidia-smi >nul 2>&1
        if not errorlevel 1 (
            echo  [OK] 检测到 NVIDIA GPU，正在更新为 GPU 版本 PyTorch...
            "%BACKEND_DIR%\venv\Scripts\pip.exe" uninstall torch torchvision torchaudio -y >nul 2>&1
            "%BACKEND_DIR%\venv\Scripts\pip.exe" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
            echo  [OK] GPU 版本 PyTorch 安装完成
        )
    ) else (
        echo  [OK] PyTorch GPU 加速已就绪
    )
)

cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo  [*] 正在安装前端依赖（使用国内镜像加速）...
    call npm config set registry https://registry.npmmirror.com
    echo  [*] 开始安装，请耐心等待...
    call npm install
    if errorlevel 1 (
        echo  [WARNING] 安装失败，请手动运行: cd frontend ^&^& npm install
    ) else (
        echo  [OK] 前端依赖安装完成
    )
) else (
    echo  [OK] 前端依赖已安装
)

echo.

:: [第六步] 启动服务
echo ========================================================
echo  [步骤 6/8] 启动服务
echo ========================================================

echo  [*] 正在启动后端服务（端口 !BACKEND_PORT!）...
start "全能创意大师 - 后端服务" cmd /k "cd /d "%BACKEND_DIR%" && call venv\Scripts\activate.bat && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port !BACKEND_PORT! --reload"

echo  [*] 等待后端服务启动...
set BACKEND_READY=0
for /l %%i in (1,1,45) do (
    timeout /t 1 /nobreak >nul
    curl -s http://localhost:!BACKEND_PORT!/api/v1/health >nul 2>&1
    if not errorlevel 1 (
        set BACKEND_READY=1
        echo  [OK] 后端服务启动成功
        goto backend_done
    )
    echo  等待后端启动中... (%%i/45^)
)

:backend_done
if !BACKEND_READY! EQU 0 (
    echo  [WARNING] 后端启动超时，请检查日志
)

echo  [*] 正在启动前端服务（端口 !FRONTEND_PORT!）...
start "全能创意大师 - 前端服务" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo  [*] 等待前端服务启动...
timeout /t 5 /nobreak >nul
echo  [OK] 前端服务启动中...

echo.

:: [第七步] 完成
echo ========================================================
echo  [步骤 7/8] 启动完成
echo ========================================================
echo.
echo  ========================================
echo    全能创意大师 启动成功！
echo  ========================================
echo.
echo  后端地址: http://localhost:!BACKEND_PORT!
echo  前端地址: http://localhost:!FRONTEND_PORT!
echo.
echo  浏览器将自动打开前端页面
echo  如果没有自动打开，请手动访问上述地址
echo.
echo  按 Ctrl+C 可以停止服务
echo ========================================
echo.

:: Vite 会自动打开浏览器（vite.config.js 中配置了 open: true）
:: 无需在此手动打开浏览器，否则会打开两个窗口

pause
exit /b 0

:: ============================================================
:: 端口清理函数
:: 参数1: 端口号
:: 参数2: 服务名称（用于日志显示）
:: ============================================================
:CleanPort
set "CLEAN_PORT=%~1"
set "SERVICE_NAME=%~2"
set "PORT_CLEANED=0"

echo  [*] 检测 %SERVICE_NAME% 端口 !CLEAN_PORT!...

:: 使用 netstat 查找占用指定端口的进程
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%CLEAN_PORT% "') do (
    set "PID=%%a"
    
    :: 跳过空值和 "0"
    if "!PID!" NEQ "" if "!PID!" NEQ "0" (
        echo  [!] 发现端口 !CLEAN_PORT! 被进程 PID=!PID! 占用
        echo  [*] 正在强制终止进程 !PID!...
        
        :: 强制终止进程
        taskkill /f /pid !PID! >nul 2>&1
        if not errorlevel 1 (
            echo  [OK] 进程 !PID! 已终止
            set "PORT_CLEANED=1"
        ) else (
            echo  [WARNING] 无法终止进程 !PID!，可能需要管理员权限
        )
    )
)

:: 等待端口释放
if !PORT_CLEANED! EQU 1 (
    timeout /t 1 /nobreak >nul
    echo  [OK] 端口 !CLEAN_PORT! 已清理
) else (
    echo  [OK] 端口 !CLEAN_PORT! 可用
)

goto :eof
