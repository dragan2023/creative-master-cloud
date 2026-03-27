@echo off
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 本地开发环境启动脚本
REM ========================================

echo.
echo ========================================
echo   全能创意大师 - 本地开发环境
echo ========================================
echo.

REM 设置环境变量文件
set ENV_FILE=.env.local

REM 检查Docker是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker未运行，请先启动Docker Desktop
    pause
    exit /b 1
)

REM 检查环境变量文件
if not exist "%ENV_FILE%" (
    echo [警告] 未找到 %ENV_FILE%，使用默认配置
    copy .env.example %ENV_FILE% >nul
)

REM 解析命令参数
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=up

if "%COMMAND%"=="up" goto :start
if "%COMMAND%"=="down" goto :stop
if "%COMMAND%"=="build" goto :build
if "%COMMAND%"=="pull" goto :pull
if "%COMMAND%"=="logs" goto :logs
if "%COMMAND%"=="ps" goto :status
if "%COMMAND%"=="clean" goto :clean
if "%COMMAND%"=="tools" goto :tools
goto :help

:pull
echo [预拉取] 正在拉取所需镜像（使用加速器）...
echo.
echo [1/4] 拉取 Python 镜像...
docker pull python:3.10-slim 2>nul
echo.
echo [2/4] 拉取 PostgreSQL 镜像...
docker pull postgres:15-alpine 2>nul
echo.
echo [3/4] 拉取 Redis 镜像...
docker pull redis:7-alpine 2>nul
echo.
echo [4/4] 拉取 Nginx 镜像...
docker pull nginx:1.25-alpine 2>nul
echo.
echo [完成] 镜像拉取完成
goto :end

:start
echo [启动] 正在启动本地开发环境...
echo.

REM 先尝试拉取镜像
echo [预拉取] 检查并拉取所需镜像...
docker pull postgres:15-alpine 2>nul
docker pull redis:7-alpine 2>nul
docker pull nginx:1.25-alpine 2>nul
echo.

docker compose -p creative-master -f docker-compose.dev.yml --env-file %ENV_FILE% up -d
if errorlevel 1 (
    echo.
    echo [错误] 启动失败
    echo.
    echo 可能的原因:
    echo   1. 镜像拉取失败 - 请配置 Docker 镜像加速器
    echo   2. 端口被占用 - 检查 80, 5432, 6379 端口
    echo.
    echo 解决方案:
    echo   1. 在 Docker Desktop 中导入 docker-daemon.json 配置
    echo   2. 或运行: start-dev.bat pull 预拉取镜像
    echo.
    pause
    exit /b 1
)
echo.
echo [成功] 本地开发环境已启动
echo.
echo 访问地址:
echo   - 应用入口: http://localhost
echo   - API文档: http://localhost/docs
echo   - 数据库管理: http://localhost:8080 (需启用tools)
echo   - Redis管理: http://localhost:8081 (需启用tools)
echo.
echo 常用命令:
echo   - 查看日志: start-dev.bat logs
echo   - 停止服务: start-dev.bat down
echo   - 预拉取镜像: start-dev.bat pull
echo.
goto :end

:stop
echo [停止] 正在停止本地开发环境...
docker compose -p creative-master -f docker-compose.dev.yml down
echo [完成] 服务已停止
goto :end

:build
echo [构建] 正在构建镜像（使用清华源加速）...
docker compose -p creative-master -f docker-compose.dev.yml build --no-cache
echo [完成] 镜像构建完成
goto :end

:logs
echo [日志] 显示服务日志...
docker compose -p creative-master -f docker-compose.dev.yml logs -f --tail=100
goto :end

:status
echo [状态] 服务状态:
docker compose -p creative-master -f docker-compose.dev.yml ps
goto :end

:clean
echo [清理] 正在清理所有数据...
set /p CONFIRM="警告: 将删除所有数据库数据，确认吗? (y/n): "
if /i "%CONFIRM%"=="y" (
    docker compose -p creative-master -f docker-compose.dev.yml down -v
    echo [完成] 数据已清理
) else (
    echo [取消] 操作已取消
)
goto :end

:tools
echo [工具] 启动数据库管理工具...
docker compose -p creative-master -f docker-compose.dev.yml --profile tools up -d
echo [完成] 管理工具已启动
echo   - Adminer: http://localhost:8080
echo   - Redis Commander: http://localhost:8081
goto :end

:help
echo.
echo 用法: start-dev.bat [命令]
echo.
echo 命令列表:
echo   up      - 启动本地开发环境 (默认)
echo   down    - 停止所有服务
echo   build   - 重新构建镜像
echo   pull    - 预拉取所需镜像
echo   logs    - 查看服务日志
echo   ps      - 查看服务状态
echo   clean   - 清理所有数据
echo   tools   - 启动数据库管理工具
echo.
echo Docker镜像加速器配置:
echo   1. 打开 Docker Desktop -^> Settings -^> Docker Engine
echo   2. 复制 docker-daemon.json 内容到配置中
echo   3. 点击 Apply ^& Restart
echo.
goto :end

:end
