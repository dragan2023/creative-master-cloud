@echo off
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 项目清理脚本
REM 清理本地开发产生的临时文件和过时文件
REM ========================================

echo.
echo ========================================
echo   全能创意大师 - 项目清理工具
echo ========================================
echo.

set CLEANED=0

REM 解析命令参数
set MODE=%1
if "%MODE%"=="" set MODE=check

if "%MODE%"=="check" goto :check
if "%MODE%"=="logs" goto :clean_logs
if "%MODE%"=="dist" goto :clean_dist
if "%MODE%"=="cache" goto :clean_cache
if "%MODE%"=="all" goto :clean_all
goto :help

:check
echo [模式] 检查可清理的文件
echo.
echo ========================================
echo   可清理项目统计
echo ========================================
echo.

REM 检查日志文件
echo [1] 日志文件 (backend/logs/):
dir /s /b backend\logs\*.log 2>nul | find /c /v ""
dir /s /b backend\logs\*.zip 2>nul | find /c /v ""
echo.

REM 检查发行版
echo [2] 发行版构建 (dist/):
if exist "dist" (
    dir /b dist\*.rar 2>nul
    dir /b /ad dist\ 2>nul
) else (
    echo     无发行版
)
echo.

REM 检查空目录
echo [3] 空目录:
if exist "backenddata" (
    echo     backenddata/ (空目录)
)
if exist "build_venv" (
    echo     build_venv/ (构建虚拟环境)
)
echo.

REM 检查编译文件
echo [4] 编译缓存文件:
dir /s /b backend\*.pyd 2>nul | find /c /v ""
dir /s /b backend\*.pyi 2>nul | find /c /v ""
echo.

REM 检查前端缓存
echo [5] 前端缓存:
if exist "frontend\node_modules" (
    echo     node_modules/ 存在
)
if exist "frontend\dist" (
    echo     frontend/dist/ 存在
)
echo.

echo ========================================
echo 使用 'clean-project.bat all' 执行清理
echo 或使用特定命令清理单项:
echo   clean-project.bat logs  - 清理日志
echo   clean-project.bat dist  - 清理发行版
echo   clean-project.bat cache - 清理缓存
echo ========================================
goto :end

:clean_logs
echo [清理] 日志文件...
echo.
set /p CONFIRM="确认清理所有日志文件? (y/n): "
if /i not "%CONFIRM%"=="y" goto :cancel

if exist "backend\logs" (
    del /q backend\logs\*.log 2>nul
    del /q backend\logs\*.zip 2>nul
    echo [完成] 日志文件已清理
) else (
    echo [跳过] 无日志文件
)
goto :end

:clean_dist
echo [清理] 发行版文件...
echo.
echo 将保留最新版本 v2.2.2
echo.
set /p CONFIRM="确认清理旧版发行版? (y/n): "
if /i not "%CONFIRM%"=="y" goto :cancel

if exist "dist" (
    REM 保留 creative-master-pyinstaller-v2.2.2 和 creative-master-release-v2.2.1
    for /d %%d in (dist\creative-master-release-v*) do (
        echo %%d | findstr /v "v2.2.2" >nul
        if not errorlevel 1 (
            rmdir /s /q "%%d" 2>nul
            echo [删除] %%d
        )
    )
    for %%f in (dist\*.rar) do (
        echo %%f | findstr /v "v2.2.2" >nul
        if not errorlevel 1 (
            del /q "%%f" 2>nul
            echo [删除] %%f
        )
    )
    echo [完成] 发行版已清理
) else (
    echo [跳过] 无发行版
)
goto :end

:clean_cache
echo [清理] 缓存文件...
echo.

REM 删除空目录
if exist "backenddata" (
    rmdir /s /q backenddata 2>nul
    echo [删除] backenddata/
)

if exist "build_venv" (
    rmdir /s /q build_venv 2>nul
    echo [删除] build_venv/
)

REM 删除编译文件
if exist "backend\*.pyd" (
    del /q backend\*.pyd 2>nul
    echo [删除] .pyd 文件
)
if exist "backend\*.pyi" (
    del /q backend\*.pyi 2>nul
    echo [删除] .pyi 文件
)

REM 清理 __pycache__
for /d /r backend %%d in (__pycache__) do (
    if exist "%%d" (
        rmdir /s /q "%%d" 2>nul
    )
)
echo [删除] __pycache__ 目录

REM 清理前端 dist（可选）
if exist "frontend\dist" (
    set /p CLEAN_FRONTEND="是否清理 frontend/dist? (y/n): "
    if /i "!CLEAN_FRONTEND!"=="y" (
        rmdir /s /q frontend\dist 2>nul
        echo [删除] frontend/dist/
    )
)

echo [完成] 缓存文件已清理
goto :end

:clean_all
echo [清理] 执行完整清理...
echo.
echo 警告: 将执行以下操作:
echo   1. 清理所有日志文件
echo   2. 清理旧版发行版（保留v2.2.2）
echo   3. 清理缓存和临时文件
echo   4. 删除空目录
echo.
set /p CONFIRM="确认执行完整清理? (y/n): "
if /i not "%CONFIRM%"=="y" goto :cancel

REM 执行所有清理
call :clean_logs_internal
call :clean_dist_internal
call :clean_cache_internal
echo.
echo [完成] 项目清理完成
goto :end

:clean_logs_internal
if exist "backend\logs" (
    del /q backend\logs\*.log 2>nul
    del /q backend\logs\*.zip 2>nul
)
exit /b

:clean_dist_internal
if exist "dist" (
    for /d %%d in (dist\creative-master-release-v*) do (
        echo %%d | findstr /v "v2.2.2" >nul
        if not errorlevel 1 rmdir /s /q "%%d" 2>nul
    )
    for %%f in (dist\*.rar) do (
        echo %%f | findstr /v "v2.2.2" >nul
        if not errorlevel 1 del /q "%%f" 2>nul
    )
)
exit /b

:clean_cache_internal
if exist "backenddata" rmdir /s /q backenddata 2>nul
if exist "build_venv" rmdir /s /q build_venv 2>nul
del /q backend\*.pyd 2>nul
del /q backend\*.pyi 2>nul
for /d /r backend %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
exit /b

:cancel
echo [取消] 操作已取消
goto :end

:help
echo.
echo 用法: clean-project.bat [命令]
echo.
echo 命令列表:
echo   check  - 检查可清理文件 (默认)
echo   logs   - 清理日志文件
echo   dist   - 清理旧版发行版
echo   cache  - 清理缓存文件
echo   all    - 执行完整清理
echo.

:end
