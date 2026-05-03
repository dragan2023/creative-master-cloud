@echo off
REM ========================================
REM DeepSeek 思考模式测试 - 一键运行脚本
REM ========================================

echo.
echo ========================================
echo DeepSeek 思考模式测试
echo ========================================
echo.

REM 检查是否在正确的目录
if not exist "venv\Scripts\python.exe" (
    echo [错误] 请在 backend 目录下运行此脚本
    echo.
    echo 正确做法:
    echo   cd backend
    echo   scripts\run_thinking_test.bat
    echo.
    pause
    exit /b 1
)

REM 检查 .env 文件
if not exist ".env" (
    echo [警告] 未找到 .env 文件
    echo 请确保已配置 DeepSeek API Key
    echo.
)

echo [信息] 使用虚拟环境运行测试...
echo.

REM 使用虚拟环境运行测试脚本
venv\Scripts\python.exe scripts\test_thinking_mode.py

echo.
echo ========================================
echo 测试完成
echo ========================================
echo.

pause
