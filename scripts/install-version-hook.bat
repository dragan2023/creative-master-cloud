@echo off
REM 安装 Git pre-push hook (Windows)
REM
REM 使用方法: scripts\install-version-hook.bat

setlocal enabledelayedexpansion

echo 正在安装 Git pre-push hook...

REM 获取脚本目录和项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "GIT_HOOKS_DIR=%PROJECT_ROOT%\.git\hooks"

REM 检查 .git 目录是否存在
if not exist "%PROJECT_ROOT%\.git" (
    echo 错误: 未找到 .git 目录，请确保在 Git 仓库中运行此脚本
    exit /b 1
)

REM 创建 hooks 目录（如果不存在）
if not exist "%GIT_HOOKS_DIR%" (
    mkdir "%GIT_HOOKS_DIR%"
)

REM 复制 hook 文件
copy /Y "%SCRIPT_DIR%git-hooks\pre-push" "%GIT_HOOKS_DIR%\pre-push" >nul

echo.
echo √ Git pre-push hook 安装成功！
echo.
echo 功能说明:
echo   - 推送到 main/master 分支时自动更新版本号
echo   - 根据提交信息自动判断版本递增类型
echo   - 自动更新 version.json 和 CHANGELOG.md
echo.
echo 人工干预标记（在提交信息中添加）:
echo   [skip version]  - 跳过版本更新
echo   [major]         - 强制主版本递增
echo   [minor]         - 强制次版本递增
echo   [patch]         - 强制修订号递增
echo.

endlocal
