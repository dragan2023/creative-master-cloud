@echo off
setlocal enabledelayedexpansion

REM Python UTF-8 encoding fix for Windows Chinese systems
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

:: ============================================================
:: 全能创意大师 - 发行版启动脚本 v9.0
:: 功能：环境检测、端口清理、依赖安装、后端服务启动
:: 特点：前端由后端统一托管，启动后自动打开浏览器
:: ============================================================

title 全能创意大师 - 启动脚本

:: 设置项目路径
set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "DATA_DIR=%BACKEND_DIR%\data"

:: 端口配置
set "BACKEND_PORT=8000"

echo.
echo ========================================================
echo     全能创意大师 - 智能内容生成平台
echo ========================================================
echo.

:: [第零步] 检测并配置 PowerShell 环境
echo ========================================================
echo  [步骤 0/7] 检测 PowerShell 环境
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
echo  [步骤 1/7] 检测 Python 环境
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
echo  [步骤 2/7] 检测 Node.js 环境
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

:: [第2.5步] 检测 Visual C++ Redistributable
REM Visual C++ Redistributable 是 onnxruntime 等依赖的必需组件
echo ========================================================
echo  [步骤 2.5/7] 检测 Visual C++ Redistributable
echo ========================================================

set "VCPP_OK=0"

REM 方法1: 检查关键 DLL 文件是否存在
if exist "%SystemRoot%\System32\vcruntime140.dll" (
    set "VCPP_OK=1"
    echo  [OK] 检测到 Visual C++ Redistributable (vcruntime140.dll)
)

REM 方法2: 检查 msvcp140.dll 作为备用验证
if exist "%SystemRoot%\System32\msvcp140.dll" (
    if "!VCPP_OK!"=="0" (
        set "VCPP_OK=1"
        echo  [OK] 检测到 Visual C++ Redistributable (msvcp140.dll)
    )
)

REM 方法3: 通过注册表检查安装情况（更准确）
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=3" %%v in ('reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed 2^>nul ^| findstr "Installed"') do (
        if "%%v"=="0x1" (
            if "!VCPP_OK!"=="0" (
                set "VCPP_OK=1"
                echo  [OK] 检测到 Visual C++ Redistributable (注册表验证)
            )
        )
    )
)

if "!VCPP_OK!"=="0" (
    echo.
    echo  [WARNING] 未检测到 Visual C++ Redistributable 2015-2022
    echo.
    echo  Visual C++ Redistributable 是以下组件的必需依赖：
    echo    - onnxruntime (语义切片功能)
    echo    - PyTorch (深度学习框架)
    echo    - 其他 C++ 扩展模块
    echo.
    echo  缺少此组件可能导致程序运行时出现 DLL 加载失败错误。
    echo.
    echo  建议下载并安装 Visual C++ Redistributable:
    echo  下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo  [INFO] 继续运行，部分功能可能受限
)

echo.

:: [第三步] 检测并清理端口占用（提前执行）
echo ========================================================
echo  [步骤 3/7] 检测并清理端口占用
echo ========================================================
echo.

:: 清理后端端口（8000-8005）
echo  [*] 清理后端服务端口范围 (8000-8005)...
for /l %%p in (8000,1,8005) do (
    call :CleanPort %%p "后端服务" 0
)

:: 清理残留的 Node.js 和 Python 进程（本项目相关）
echo  [*] 清理残留的 Node.js 进程...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq node.exe" /fo list 2^>nul ^| findstr "PID:"') do (
    echo  [!] 发现 Node.js 进程 PID=%%i，正在终止...
    taskkill /f /pid %%i >nul 2>&1
)
echo  [*] 清理残留的 Python 进程（uvicorn相关）...
for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr "PID:"') do (
    echo  [!] 发现 Python 进程 PID=%%i，正在终止...
    taskkill /f /pid %%i >nul 2>&1
)

:: 等待端口完全释放
echo  [*] 等待端口完全释放...
timeout /t 3 /nobreak >nul

echo  [OK] 端口清理完成
echo.

:: [第四步] 创建必要的目录和配置文件
echo ========================================================
echo  [步骤 4/7] 创建必要的目录和配置文件
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
    ) > "%BACKEND_DIR%\.env"
    echo  [OK] 后端配置文件已生成
) else (
    echo  [OK] 后端配置文件已存在
)

echo.

:: [第五步] 检查并安装依赖
echo ========================================================
echo  [步骤 5/7] 检查并安装依赖
echo ========================================================

if not exist "%BACKEND_DIR%\venv" (
    echo  [*] 正在创建 Python 虚拟环境...
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    cd /d "%PROJECT_DIR%"
    echo  [OK] 虚拟环境创建完成
)

:: 确保工作目录在项目根目录
cd /d "%PROJECT_DIR%"

:: 不依赖 activate.bat，直接使用虚拟环境中的 pip 和 python
set "VENV_PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"
set "VENV_PIP=%BACKEND_DIR%\venv\Scripts\pip.exe"

echo  [*] 正在检查后端依赖...
"%VENV_PIP%" show fastapi >nul 2>&1
if errorlevel 1 (
    echo  [*] 正在安装后端依赖（使用国内镜像加速）...
    echo  [INFO] requirements.txt 路径: "%BACKEND_DIR%\requirements.txt"
    echo  [INFO] pip 路径: "%VENV_PIP%"
    
    REM 验证 requirements.txt 文件是否存在
    if not exist "%BACKEND_DIR%\requirements.txt" (
        echo  [ERROR] requirements.txt 文件不存在！
        echo  [INFO] 请检查路径: %BACKEND_DIR%\requirements.txt
        goto deps_failed
    )
    
    "%VENV_PIP%" install -r "%BACKEND_DIR%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo  [WARNING] 国内镜像安装失败，尝试默认源...
        "%VENV_PIP%" install -r "%BACKEND_DIR%\requirements.txt"
    )
    echo  [OK] 后端依赖安装完成
    
    REM 确保关键依赖已安装（防止 requirements.txt 安装失败）
    echo  [*] 验证关键依赖...
    "%VENV_PIP%" show onnxruntime >nul 2>&1
    if errorlevel 1 (
        echo  [WARNING] onnxruntime 未安装，正在单独安装...
        "%VENV_PIP%" install onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo  [OK] onnxruntime 已安装
    )
    
    "%VENV_PIP%" show huggingface_hub >nul 2>&1
    if errorlevel 1 (
        echo  [WARNING] huggingface_hub 未安装，正在单独安装...
        "%VENV_PIP%" install huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo  [OK] huggingface_hub 已安装
    )
    echo  [OK] 关键依赖验证完成
) else (
    echo  [OK] 后端依赖已安装
    
    REM 即使依赖已安装，也要验证关键依赖
    echo  [*] 验证关键依赖...
    "%VENV_PIP%" show onnxruntime >nul 2>&1
    if errorlevel 1 (
        echo  [WARNING] onnxruntime 未安装，正在单独安装...
        "%VENV_PIP%" install onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo  [OK] onnxruntime 已安装
    )
    
    "%VENV_PIP%" show huggingface_hub >nul 2>&1
    if errorlevel 1 (
        echo  [WARNING] huggingface_hub 未安装，正在单独安装...
        "%VENV_PIP%" install huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple
    ) else (
        echo  [OK] huggingface_hub 已安装
    )
    echo  [OK] 关键依赖验证完成
)

goto deps_ok

:deps_failed
echo  [ERROR] 依赖安装失败，请手动安装依赖后重试
echo  [INFO] 手动安装命令: cd backend ^&^& venv\Scripts\pip install -r requirements.txt
pause
exit /b 1

:deps_ok

:: 验证 onnxruntime 是否真正可用（检测 DLL 依赖问题）
echo  [*] 验证 onnxruntime 运行时...
"%VENV_PYTHON%" -c "import onnxruntime; print('onnxruntime', onnxruntime.__version__)" >nul 2>&1
if errorlevel 1 (
    echo  [!] onnxruntime 加载失败，可能缺少 Visual C++ Redistributable
    echo  [INFO] 请下载并安装: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo  [INFO] 安装后重新运行此脚本
    REM 不退出，允许继续运行（语义切片会自动降级）
) else (
    echo  [OK] onnxruntime 运行时正常
)

echo.

:: [第六步] 启动服务
echo ========================================================
echo  [步骤 6/7] 启动服务
echo ========================================================

echo  [*] 正在启动后端服务（端口 !BACKEND_PORT!）...
start "全能创意大师 - 后端服务" /d "%BACKEND_DIR%" cmd /k ""%BACKEND_DIR%\venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port !BACKEND_PORT! --reload"

echo  [*] 等待后端服务启动...

:: 检测 curl 是否可用
curl --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] curl 不可用，使用 PowerShell 进行健康检查
    set "USE_CURL=0"
) else (
    set "USE_CURL=1"
)

set BACKEND_READY=0
for /l %%i in (1,1,60) do (
    timeout /t 1 /nobreak >nul
    
    REM 使用 curl 或 PowerShell 检查健康状态
    if "!USE_CURL!"=="1" (
        curl -s http://localhost:!BACKEND_PORT!/health >nul 2>&1
    ) else (
        powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://localhost:!BACKEND_PORT!/health' -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
    )
    
    if not errorlevel 1 (
        set BACKEND_READY=1
        echo.
        echo  [OK] 后端服务启动成功 ^(检测耗时: %%i秒^)
        goto backend_done
    )
    set /a "progress=%%i*100/60"
    <nul set /p="  等待后端启动中... [!progress!%%] "
)

echo.
:backend_done
if !BACKEND_READY! EQU 0 (
    echo  [WARNING] 后端启动超时，请检查后端窗口是否有错误
    echo  [INFO] 可能的原因:
    echo         1. 依赖安装失败 - 请查看后端窗口错误
    echo         2. 端口被占用 - 请检查端口 !BACKEND_PORT!
    echo         3. 数据库初始化失败 - 请查看日志文件
)

:: 前端已由后端统一托管，无需单独启动
:: 后端启动后会自动打开浏览器访问前端
echo  [*] 前端已由后端服务托管（端口 !BACKEND_PORT!）
echo  [*] 浏览器将自动打开前端页面
echo.

:: [第七步] 完成
echo ========================================================
echo  [步骤 7/7] 启动完成
echo ========================================================
echo.
echo  ========================================
echo    全能创意大师 启动成功！
echo  ========================================
echo.
echo  访问地址: http://localhost:!BACKEND_PORT!
echo.
echo  浏览器将自动打开前端页面
echo  如果没有自动打开，请手动访问上述地址
echo.
echo  按 Ctrl+C 可以停止服务
echo ========================================
echo.

:: 后端启动后会自动打开浏览器，无需在此手动打开

pause
exit /b 0

:: ============================================================
:: 端口清理函数
:: 参数1: 端口号
:: 参数2: 服务名称（用于日志显示）
:: 参数3: 是否显示详细信息（1=显示，0=静默）
:: ============================================================
:CleanPort
set "CLEAN_PORT=%~1"
set "SERVICE_NAME=%~2"
set "VERBOSE=%~3"
if "%VERBOSE%"=="" set "VERBOSE=1"
set "PORT_CLEANED=0"

:: 使用 netstat 查找占用指定端口的进程（改进匹配模式）
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /r ":%CLEAN_PORT%[ \t]"') do (
    set "PID=%%a"
    
    REM 跳过空值和 "0"
    if "!PID!" NEQ "" if "!PID!" NEQ "0" (
        if "%VERBOSE%"=="1" (
            echo  [!] 发现端口 %CLEAN_PORT% 被进程 PID=!PID! 占用
            echo  [*] 正在强制终止进程 !PID!...
        )
        
        REM 强制终止进程
        taskkill /f /pid !PID! >nul 2>&1
        if not errorlevel 1 (
            if "%VERBOSE%"=="1" echo  [OK] 进程 !PID! 已终止
            set "PORT_CLEANED=1"
        ) else (
            if "%VERBOSE%"=="1" echo  [WARNING] 无法终止进程 !PID!，可能需要管理员权限
        )
    )
)

:: 额外检查 IPv6 端口
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /r "\[.*\]:%CLEAN_PORT%"') do (
    set "PID=%%a"
    
    if "!PID!" NEQ "" if "!PID!" NEQ "0" (
        if "%VERBOSE%"=="1" (
            echo  [!] 发现 IPv6 端口 %CLEAN_PORT% 被进程 PID=!PID! 占用
            echo  [*] 正在强制终止进程 !PID!...
        )
        
        taskkill /f /pid !PID! >nul 2>&1
        if not errorlevel 1 (
            if "%VERBOSE%"=="1" echo  [OK] 进程 !PID! 已终止
            set "PORT_CLEANED=1"
        )
    )
)

:: 等待端口释放
if !PORT_CLEANED! EQU 1 (
    timeout /t 1 /nobreak >nul
    if "%VERBOSE%"=="1" echo  [OK] 端口 %CLEAN_PORT% 已清理
) else (
    if "%VERBOSE%"=="1" echo  [OK] 端口 %CLEAN_PORT% 可用
)

goto :eof
