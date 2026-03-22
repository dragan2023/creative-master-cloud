@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM Python UTF-8 encoding fix for Windows Chinese systems
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

:: ============================================================
:: 全能创意大师 - 停止服务脚本 v2.0
:: 功能：清理残留进程、释放端口占用、安全停止服务
:: ============================================================

title 全能创意大师 - 停止服务
color 0C

:: 端口配置
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║           全能创意大师 - 停止服务 v2.0                     ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo  正在安全停止所有服务...
echo.

:: ============================================================
:: 第一步：终止所有相关进程
:: ============================================================
echo ┌────────────────────────────────────────────────────────────┐
echo │  [步骤 1/3] 终止相关进程                                   │
echo └────────────────────────────────────────────────────────────┘
echo.

:: 统计进程数量
set "PYTHON_COUNT=0"
set "NODE_COUNT=0"

for /f %%i in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr /c:"PID:"') do (
    set /a PYTHON_COUNT+=1
)

for /f %%i in ('tasklist /fi "imagename eq node.exe" /fo list 2^>nul ^| findstr /c:"PID:"') do (
    set /a NODE_COUNT+=1
)

:: 关闭 Python 进程（后端）
if !PYTHON_COUNT! GTR 0 (
    echo  [*] 发现 !PYTHON_COUNT! 个 Python 进程，正在终止...
    for /f "tokens=2" %%i in ('tasklist /fi "imagename eq python.exe" /fo list 2^>nul ^| findstr "PID:"') do (
        echo      - 终止 Python 进程 PID=%%i
        taskkill /f /pid %%i >nul 2>&1
    )
    echo  [OK] 后端服务已停止 ^(Python^)
) else (
    echo  [INFO] 后端服务未运行 ^(无 Python 进程^)
)

:: 关闭 Node 进程（前端）
if !NODE_COUNT! GTR 0 (
    echo  [*] 发现 !NODE_COUNT! 个 Node.js 进程，正在终止...
    for /f "tokens=2" %%i in ('tasklist /fi "imagename eq node.exe" /fo list 2^>nul ^| findstr "PID:"') do (
        echo      - 终止 Node.js 进程 PID=%%i
        taskkill /f /pid %%i >nul 2>&1
    )
    echo  [OK] 前端服务已停止 ^(Node.js^)
) else (
    echo  [INFO] 前端服务未运行 ^(无 Node.js 进程^)
)

:: 关闭可能的 cmd 窗口进程（启动脚本打开的窗口）
echo  [*] 清理残留的命令行窗口...
for /f "tokens=2" %%i in ('tasklist /fi "windowtitle eq 全能创意大师*" /fo list 2^>nul ^| findstr "PID:"') do (
    echo      - 终止窗口进程 PID=%%i
    taskkill /f /pid %%i >nul 2>&1
)

echo.

:: ============================================================
:: 第二步：清理端口占用
:: ============================================================
echo ┌────────────────────────────────────────────────────────────┐
echo │  [步骤 2/3] 清理端口占用                                   │
echo └────────────────────────────────────────────────────────────┘
echo.

:: 清理所有可能的前端端口（5173-5180）
echo  [*] 清理前端服务端口范围 ^(5173-5180^)...
for /l %%p in (5173,1,5180) do (
    call :CleanPort %%p "前端服务" 0
)

:: 清理后端端口（8000-8005）
echo  [*] 清理后端服务端口范围 ^(8000-8005^)...
for /l %%p in (8000,1,8005) do (
    call :CleanPort %%p "后端服务" 0
)

echo  [OK] 端口清理完成
echo.

:: ============================================================
:: 第三步：验证清理结果
:: ============================================================
echo ┌────────────────────────────────────────────────────────────┐
echo │  [步骤 3/3] 验证清理结果                                   │
echo └────────────────────────────────────────────────────────────┘
echo.

:: 等待端口完全释放
echo  [*] 等待端口完全释放...
timeout /t 2 /nobreak >nul

:: 检查关键端口是否已释放
set "PORT_CHECK_OK=1"

:: 检查后端端口
netstat -ano 2>nul | findstr /r ":8000[ \t]" >nul 2>&1
if not errorlevel 1 (
    echo  [WARNING] 端口 8000 仍被占用
    set "PORT_CHECK_OK=0"
) else (
    echo  [OK] 端口 8000 已释放
)

:: 检查前端端口
netstat -ano 2>nul | findstr /r ":5173[ \t]" >nul 2>&1
if not errorlevel 1 (
    echo  [WARNING] 端口 5173 仍被占用
    set "PORT_CHECK_OK=0"
) else (
    echo  [OK] 端口 5173 已释放
)

echo.

:: ============================================================
:: 完成
:: ============================================================
if !PORT_CHECK_OK! EQU 1 (
    color 0A
    echo ╔════════════════════════════════════════════════════════════╗
    echo ║                                                            ║
    echo ║              ✓ 所有服务已安全停止                         ║
    echo ║                                                            ║
    echo ╚════════════════════════════════════════════════════════════╝
) else (
    color 0E
    echo ╔════════════════════════════════════════════════════════════╗
    echo ║                                                            ║
    echo ║              ⚠ 服务已停止，但部分端口未释放               ║
    echo ║                                                            ║
    echo ╚════════════════════════════════════════════════════════════╝
    echo.
    echo  [提示] 如果端口仍被占用，请尝试：
    echo         1. 以管理员身份运行此脚本
    echo         2. 重启计算机
    echo         3. 手动查找占用进程: netstat -ano ^| findstr "端口号"
)

echo.
echo  如需重新启动，请双击 start.bat
echo.
echo ══════════════════════════════════════════════════════════════
echo.

timeout /t 3 >nul
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

:: 使用 netstat 查找占用指定端口的进程
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
)

goto :eof
