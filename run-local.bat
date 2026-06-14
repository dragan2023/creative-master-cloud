@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 非容器化本地开发环境
REM 支持前后端热更新，无需 Docker
REM ========================================

echo.
echo ========================================
echo   全能创意大师 - 本地开发环境
echo   [非容器化, 支持热更新]
echo ========================================
echo.

REM 获取项目根目录
set PROJECT_ROOT=%~dp0
set BACKEND_DIR=%PROJECT_ROOT%backend
set FRONTEND_DIR=%PROJECT_ROOT%frontend

REM 解析命令参数
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=start

if "%COMMAND%"=="start" goto :start
if "%COMMAND%"=="install" goto :install
if "%COMMAND%"=="stop" goto :stop
if "%COMMAND%"=="status" goto :status
if "%COMMAND%"=="help" goto :help
goto :help

REM ==================== 环境检查 ====================
:check_environment
echo [检查] 正在检查运行环境...
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo        下载地址: https://www.python.org/downloads/
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo [OK] Python %PYTHON_VERSION%

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js 18+
    echo        下载地址: https://nodejs.org/
    exit /b 1
)
for /f "delims=" %%v in ('node --version') do set NODE_VERSION=%%v
echo [OK] Node.js %NODE_VERSION%

REM 检查 npm
for /f "delims=" %%v in ('npm --version') do set NPM_VERSION=%%v
echo [OK] npm %NPM_VERSION%

echo.
exit /b 0

REM ==================== 清理端口和进程 ====================
:cleanup_ports
echo [清理] 正在检查并清理残留进程...
echo.

REM 清理后端端口 8002
set BACKEND_CLEANED=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002.*LISTENING" 2^>nul') do (
    echo [清理] 终止后端进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
    set BACKEND_CLEANED=1
)
if "%BACKEND_CLEANED%"=="1" (
    echo [清理] 后端端口 8002 已释放
    timeout /t 1 /nobreak >nul
)

REM 清理前端端口 3000, 3001-3008
set FRONTEND_CLEANED=0
for %%p in (3000 3001 3002 3003 3004 3005 3006 3007 3008) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p.*LISTENING" 2^>nul') do (
        echo [清理] 终止前端进程 PID: %%a ^(端口 %%p^)
        taskkill /F /PID %%a >nul 2>&1
        set FRONTEND_CLEANED=1
    )
)
if "%FRONTEND_CLEANED%"=="1" (
    echo [清理] 前端端口已释放
    timeout /t 1 /nobreak >nul
)

REM 关闭残留的服务窗口
taskkill /FI "WINDOWTITLE eq Creative-Master-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Creative-Master-Frontend*" /F >nul 2>&1

if "%BACKEND_CLEANED%%FRONTEND_CLEANED%"=="00" (
    echo [清理] 无残留进程
)
echo.
exit /b 0

REM ==================== 安装依赖 ====================
:install
echo ========================================
echo   安装依赖
echo ========================================
echo.

REM 检查环境
call :check_environment
if errorlevel 1 exit /b 1

REM 安装后端依赖
echo.
echo [后端] 正在安装 Python 依赖（使用清华源）...
cd /d "%BACKEND_DIR%"

REM 检查虚拟环境
if not exist "venv" (
    echo [创建] 正在创建 Python 虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境并安装依赖
call venv\Scripts\activate.bat
echo [安装] 正在安装依赖（清华源）...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，尝试继续...
)
call deactivate

echo [完成] 后端依赖安装完成

REM 安装前端依赖
echo.
echo [前端] 正在安装 Node.js 依赖...
cd /d "%FRONTEND_DIR%"
call npm install --registry=https://registry.npmmirror.com
if errorlevel 1 (
    echo [错误] 前端依赖安装失败
    exit /b 1
)
echo [完成] 前端依赖安装完成

cd /d "%PROJECT_ROOT%"
echo.
echo ========================================
echo   依赖安装完成！
echo ========================================
echo.
echo 运行 'run-local.bat start' 启动开发环境
echo.
goto :end

REM ==================== 启动服务 ====================
:start
echo ========================================
echo   启动开发环境
echo ========================================
echo.

REM 检查环境
call :check_environment
if errorlevel 1 goto :end

REM 清理残留进程
call :cleanup_ports

REM 检查后端虚拟环境
if not exist "%BACKEND_DIR%\venv" (
    echo [警告] 未找到 Python 虚拟环境，正在自动安装依赖...
    call :install
)

REM 检查前端 node_modules
if not exist "%FRONTEND_DIR%\node_modules" (
    echo [警告] 未找到前端依赖，正在自动安装...
    cd /d "%FRONTEND_DIR%"
    call npm install --registry=https://registry.npmmirror.com
    cd /d "%PROJECT_ROOT%"
)

echo.
echo [启动模式] 热更新模式
echo   - 后端: uvicorn --reload （代码修改自动重载）
echo   - 前端: Vite HMR （代码修改实时刷新）
echo.

REM 启动后端服务
echo [后端] 正在启动后端服务...
cd /d "%BACKEND_DIR%"
start "Creative-Master-Backend" cmd /k "venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload"
cd /d "%PROJECT_ROOT%"

REM 等待后端启动
echo [等待] 正在等待后端服务就绪...
set WAIT_COUNT=0
:wait_backend
set /a WAIT_COUNT+=1
curl -s http://localhost:8002/health >nul 2>&1
if not errorlevel 1 (
    echo [就绪] 后端服务已就绪 ^(等待 %WAIT_COUNT% 秒^)
    goto :start_frontend
)
if %WAIT_COUNT% GEQ 45 (
    echo [错误] 后端启动超时，请检查日志
    echo.
    echo 可能的原因:
    echo   1. Python 依赖未正确安装
    echo   2. 端口 8002 被其他程序占用
    echo   3. 数据库文件损坏
    echo.
    pause
    goto :end
)
timeout /t 1 /nobreak >nul
goto :wait_backend

:start_frontend
REM 启动前端服务
echo.
echo [前端] 正在启动前端开发服务器...
cd /d "%FRONTEND_DIR%"

REM 使用npx启动vite并指定端口,添加错误捕获
start "Creative-Master-Frontend" cmd /k "set BROWSER=none && npx vite --port 3001 --host 0.0.0.0 || (echo [错误] 前端启动失败,按任意键关闭此窗口... && pause)"
cd /d "%PROJECT_ROOT%"

REM 等待前端启动并检测实际端口
echo [等待] 正在等待前端服务就绪...
set WAIT_COUNT=0
set FRONTEND_PORT=

:wait_frontend
set /a WAIT_COUNT+=1

REM 检测前端实际监听的端口(优先3001)
if "!FRONTEND_PORT!"=="" (
    netstat -ano | findstr ":3001.*LISTENING" >nul 2>&1
    if not errorlevel 1 (
        set FRONTEND_PORT=3001
        echo [就绪] 前端服务已就绪 ^(端口 3001, 等待 %WAIT_COUNT% 秒^)
        goto :verify_frontend
    )
)

REM 如果3001端口未就绪,尝试其他端口
for %%p in (3002 3003 3004 3005 3006 3007 3008) do (
    if "!FRONTEND_PORT!"=="" (
        netstat -ano | findstr ":%%p.*LISTENING" >nul 2>&1
        if not errorlevel 1 (
            set FRONTEND_PORT=%%p
            echo [就绪] 前端服务已就绪 ^(端口 %%p, 等待 %WAIT_COUNT% 秒^)
        )
    )
)
if "!FRONTEND_PORT!" NEQ "" goto :verify_frontend

if %WAIT_COUNT% GEQ 45 (
    echo [警告] 前端启动超时
    echo.
    echo 可能的原因:
    echo   1. Node.js 依赖未正确安装
    echo   2. 端口 3001-3008 均被占用
    echo   3. 查看前端窗口错误信息
    echo.
    set FRONTEND_PORT=3001
    goto :show_info
)
timeout /t 1 /nobreak >nul
goto :wait_frontend

:verify_frontend
REM 验证前端服务是否真正可用
echo [验证] 正在验证前端服务...
set VERIFY_COUNT=0
:verify_loop
set /a VERIFY_COUNT+=1
curl -s http://localhost:!FRONTEND_PORT! >nul 2>&1
if not errorlevel 1 (
    echo [验证] 前端服务响应正常
    goto :show_info
)
if %VERIFY_COUNT% GEQ 10 (
    echo [警告] 前端服务无响应，但端口已监听
    echo        请稍后手动刷新浏览器
    goto :show_info
)
timeout /t 1 /nobreak >nul
goto :verify_loop

:show_info
echo.
echo ========================================
echo   开发环境已启动
echo ========================================
echo.
echo   访问地址:
echo   - 前端开发服务器: http://localhost:!FRONTEND_PORT!
echo   - 后端 API:       http://localhost:8002
echo   - API 文档:       http://localhost:8002/docs
echo   - API 文档(ReDoc): http://localhost:8002/redoc
echo.
echo ========================================
echo   热更新说明
echo ========================================
echo.
echo   - 修改前端代码（.vue, .js, .css 等）后会自动刷新浏览器
echo   - 修改后端代码（.py 文件）后会自动重启服务
echo   - 两个服务窗口请勿关闭，否则服务会停止
echo.
echo ========================================
echo   常用命令
echo ========================================
echo.
echo   安装依赖:  run-local.bat install
echo   停止服务:  run-local.bat stop
echo   查看状态:  run-local.bat status
echo   帮助信息:  run-local.bat help
echo.

REM 自动打开浏览器
echo [提示] 3秒后自动打开浏览器...
timeout /t 3 /nobreak >nul
echo [打开] 正在打开 http://localhost:!FRONTEND_PORT!
start http://localhost:!FRONTEND_PORT!
echo.

echo ========================================
echo   后端实时日志 (Ctrl+C 退出)
echo ========================================
echo.
echo 提示: 按 Ctrl+C 只会退出日志显示，服务继续运行
echo.

REM 使用 PowerShell 实时跟踪日志文件
cd /d "%BACKEND_DIR%"
set LATEST_LOG=
for /f "delims=" %%f in ('dir /b /o-d logs\app_*.log 2^>nul') do (
    set LATEST_LOG=%%f
    goto :found_log
)

:found_log
if defined LATEST_LOG (
    echo [日志] 跟踪日志文件: logs\!LATEST_LOG!
    echo.
    powershell -Command "Get-Content -Path 'logs\!LATEST_LOG!' -Wait -Tail 50"
) else (
    echo [提示] 未找到日志文件，服务正在启动中...
    echo        请查看后端服务窗口: Creative-Master-Backend
    echo.
    pause
)
cd /d "%PROJECT_ROOT%"
goto :end

REM ==================== 停止服务 ====================
:stop
echo [停止] 正在停止开发服务...
echo.

REM 关闭后端进程（查找占用8002端口的进程）
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8002.*LISTENING"') do (
    echo [停止] 正在停止后端进程 (PID: %%a^)
    taskkill /F /PID %%a >nul 2>&1
)

REM 关闭前端进程（查找占用3000, 3001-3008端口的进程）
for %%p in (3000 3001 3002 3003 3004 3005 3006 3007 3008) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p.*LISTENING"') do (
        echo [停止] 正在停止前端进程 (PID: %%a^)
        taskkill /F /PID %%a >nul 2>&1
    )
)

REM 关闭命令窗口
taskkill /FI "WINDOWTITLE eq Creative-Master-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Creative-Master-Frontend*" /F >nul 2>&1

REM 等待端口释放
timeout /t 2 /nobreak >nul

echo.
echo [完成] 开发服务已停止
echo.
goto :end

REM ==================== 查看状态 ====================
:status
echo ========================================
echo   服务状态
echo ========================================
echo.

REM 检查后端状态
curl -s http://localhost:8002/health >nul 2>&1
if not errorlevel 1 (
    echo [运行中] 后端服务 - http://localhost:8002
) else (
    echo [已停止] 后端服务
)

REM 检查前端状态
set FRONTEND_RUNNING=0
REM 优先检查3001端口
netstat -ano | findstr ":3001.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [运行中] 前端服务 - http://localhost:3001
    set FRONTEND_RUNNING=1
    goto :status_end
)

REM 如果3001未运行,检查其他端口
for %%p in (3002 3003 3004 3005 3006 3007 3008) do (
    netstat -ano | findstr ":%%p.*LISTENING" >nul 2>&1
    if not errorlevel 1 (
        echo [运行中] 前端服务 - http://localhost:%%p
        set FRONTEND_RUNNING=1
        goto :status_end
    )
)

:status_end
if "%FRONTEND_RUNNING%"=="0" (
    echo [已停止] 前端服务
)

echo.
goto :end

REM ==================== 帮助信息 ====================
:help
echo.
echo ========================================
echo   全能创意大师 - 本地开发环境启动脚本
echo ========================================
echo.
echo 用法: run-local.bat [命令]
echo.
echo 命令列表:
echo   start   - 启动开发环境 (默认)
echo   install - 安装所有依赖
echo   stop    - 停止所有服务
echo   status  - 查看服务状态
echo   help    - 显示帮助信息
echo.
echo 环境要求:
echo   - Python 3.10+ (推荐 3.11 或 3.12)
echo   - Node.js 18+ (推荐 20 LTS)
echo.
echo 热更新说明:
echo   - 前端: Vite 内置 HMR，修改代码自动刷新浏览器
echo   - 后端: uvicorn --reload，修改代码自动重启服务
echo.
echo 数据存储:
echo   - 数据库: SQLite (backend/data/creative_master.db)
echo   - 向量库: ChromaDB (backend/data/chroma/)
echo   - 上传文件: backend/data/uploads/
echo.
echo 注意事项:
echo   - 首次运行会自动安装依赖
echo   - 依赖安装使用清华镜像源加速
echo   - 服务窗口关闭后服务会停止
echo   - 启动前会自动清理残留进程
echo.
goto :end

:end
endlocal
