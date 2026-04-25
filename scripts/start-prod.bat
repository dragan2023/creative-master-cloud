@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 生产环境启动脚本
REM 容器化部署（Docker Compose）
REM ========================================

echo.
echo ========================================
echo   全能创意大师 - 生产环境
echo   [容器化部署]
echo ========================================
echo.

REM 获取项目根目录
set PROJECT_ROOT=%~dp0
set COMPOSE_FILE=docker-compose.prod.yml
set COMPOSE_PROJECT_NAME=creative-master-prod

REM 解析命令参数
set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=up

if "%COMMAND%"=="up" goto :start
if "%COMMAND%"=="down" goto :stop
if "%COMMAND%"=="restart" goto :restart
if "%COMMAND%"=="build" goto :build
if "%COMMAND%"=="rebuild" goto :rebuild
if "%COMMAND%"=="logs" goto :logs
if "%COMMAND%"=="ps" goto :status
if "%COMMAND%"=="status" goto :status
if "%COMMAND%"=="init" goto :init
if "%COMMAND%"=="help" goto :help
goto :help

REM ==================== 环境检查 ====================
:check_docker
echo [检查] 正在检查Docker环境...
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    echo.
    pause
    exit /b 1
)
echo [OK] Docker 正在运行
exit /b 0

:check_env_file
echo [检查] 正在检查环境配置...
if not exist "%PROJECT_ROOT%.env" (
    echo [警告] 未找到 .env 文件
    
    REM 检查是否存在模板文件
    if exist "%PROJECT_ROOT%.env.cloud" (
        echo [提示] 发现 .env.cloud 模板文件
        set /p COPY_ENV="是否从 .env.cloud 创建 .env 文件？(y/n): "
        if /i "!COPY_ENV!"=="y" (
            copy "%PROJECT_ROOT%.env.cloud" "%PROJECT_ROOT%.env" >nul
            echo [完成] 已创建 .env 文件
            echo.
            echo [重要] 请编辑 .env 文件，设置以下关键配置：
            echo   - SECRET_KEY: JWT密钥（必须修改！）
            echo   - DB_PASSWORD: 数据库密码
            echo   - 各API_KEY: LLM服务密钥
            echo.
            set /p EDIT_NOW="是否现在编辑 .env 文件？(y/n): "
            if /i "!EDIT_NOW!"=="y" (
                notepad "%PROJECT_ROOT%.env"
                pause
            )
        ) else (
            echo [错误] 需要配置 .env 文件才能启动
            exit /b 1
        )
    ) else (
        echo [错误] 未找到环境配置文件，请创建 .env 文件
        exit /b 1
    )
)

REM 检查 SECRET_KEY 是否为默认值
findstr /C:"SECRET_KEY=YOUR_SECRET_KEY_HERE" "%PROJECT_ROOT%.env" >nul 2>&1
if not errorlevel 1 (
    echo [警告] SECRET_KEY 仍为默认值，生产环境必须修改！
    echo.
    set /p CONTINUE_ANYWAY="是否继续启动？(y/n): "
    if /i not "!CONTINUE_ANYWAY!"=="y" (
        echo [取消] 请先修改 .env 中的 SECRET_KEY
        exit /b 1
    )
)
echo [OK] 环境配置文件检查通过
exit /b 0

REM ==================== 初始化环境 ====================
:init
echo ========================================
echo   初始化生产环境
echo ========================================
echo.

call :check_docker
if errorlevel 1 exit /b 1

call :check_env_file
if errorlevel 1 exit /b 1

REM 创建必要的目录
echo [创建] 正在创建必要的目录...
if not exist "%PROJECT_ROOT%backend\logs" mkdir "%PROJECT_ROOT%backend\logs"
if not exist "%PROJECT_ROOT%backend\data" mkdir "%PROJECT_ROOT%backend\data"
if not exist "%PROJECT_ROOT%backups" mkdir "%PROJECT_ROOT%backups"
echo [OK] 目录创建完成

REM 构建镜像
echo.
echo [构建] 正在构建Docker镜像...
docker-compose -f %COMPOSE_FILE% build
if errorlevel 1 (
    echo [错误] 镜像构建失败
    pause
    exit /b 1
)
echo [完成] 生产环境初始化完成
echo.
echo 运行 'start-prod.bat up' 启动服务
goto :end

REM ==================== 启动服务 ====================
:start
echo ========================================
echo   启动生产环境
echo ========================================
echo.

call :check_docker
if errorlevel 1 exit /b 1

call :check_env_file
if errorlevel 1 exit /b 1

REM 检查服务是否已运行
docker-compose -f %COMPOSE_FILE% ps -q 2>nul | findstr /r ".*" >nul
if not errorlevel 1 (
    echo [提示] 服务已在运行中
    echo.
    goto :show_info
)

REM 启动服务
echo [启动] 正在启动生产环境服务...
echo.
docker-compose -f %COMPOSE_FILE% up -d
if errorlevel 1 (
    echo.
    echo [错误] 启动失败
    echo.
    echo 可能的原因:
    echo   1. 镜像未构建 - 请运行: start-prod.bat build
    echo   2. 端口被占用 - 检查 80, 443 端口
    echo   3. 环境变量未配置 - 检查 .env 文件
    echo.
    pause
    exit /b 1
)

echo.
echo [成功] 生产环境已启动
echo.

REM 等待服务就绪
echo [等待] 正在等待服务就绪...
set WAIT_COUNT=0
set MAX_WAIT=90

:wait_loop
set /a WAIT_COUNT+=1
curl -s http://localhost/health >nul 2>&1
if not errorlevel 1 (
    echo [就绪] 服务已就绪 ^(等待 %WAIT_COUNT% 秒^)
    goto :open_browser
)
if %WAIT_COUNT% GEQ %MAX_WAIT% (
    echo [警告] 等待超时，服务可能未完全启动
    echo        请检查日志: start-prod.bat logs
    goto :show_info
)
timeout /t 1 /nobreak >nul
goto :wait_loop

:open_browser
echo.
echo [自动打开] 正在打开浏览器访问 http://localhost ...
start http://localhost
echo.

:show_info
echo ========================================
echo   访问地址
echo ========================================
echo.
echo   生产环境入口: http://localhost
echo   API 文档:      http://localhost/docs
echo   API 文档(ReDoc): http://localhost/redoc
echo.
echo ========================================
echo   常用命令
echo ========================================
echo.
echo   查看后端日志:  start-prod.bat logs backend
echo   查看所有日志:  start-prod.bat logs
echo   停止所有服务:  start-prod.bat down
echo   重启所有服务:  start-prod.bat restart
echo   查看服务状态:  start-prod.bat status
echo   重新构建镜像:  start-prod.bat rebuild
echo.
echo 提示: 按 Ctrl+C 只会退出日志显示，不会停止服务
echo.

REM 显示日志
echo [日志] 显示实时日志（Ctrl+C 退出）...
echo.
if "%2"=="" (
    docker-compose -f %COMPOSE_FILE% logs -f --tail=50
) else (
    docker-compose -f %COMPOSE_FILE% logs -f --tail=50 %2
)
goto :end

REM ==================== 停止服务 ====================
:stop
echo [停止] 正在停止生产环境...
docker-compose -f %COMPOSE_FILE% down
echo [完成] 服务已停止（数据保留）
goto :end

REM ==================== 重启服务 ====================
:restart
echo [重启] 正在重启生产环境...
docker-compose -f %COMPOSE_FILE% restart
echo [完成] 服务已重启
goto :show_info

REM ==================== 构建镜像 ====================
:build
echo ========================================
echo   构建生产环境镜像
echo ========================================
echo.

call :check_docker
if errorlevel 1 exit /b 1

echo [构建] 正在构建镜像（使用缓存）...
docker-compose -f %COMPOSE_FILE% build
if errorlevel 1 (
    echo [警告] 构建失败，尝试无缓存构建...
    docker-compose -f %COMPOSE_FILE% build --no-cache
)
echo [完成] 镜像构建完成
goto :end

REM ==================== 重新构建镜像 ====================
:rebuild
echo ========================================
echo   重新构建生产环境镜像（无缓存）
echo ========================================
echo.

call :check_docker
if errorlevel 1 exit /b 1

echo [构建] 正在无缓存构建镜像...
docker-compose -f %COMPOSE_FILE% build --no-cache
if errorlevel 1 (
    echo [错误] 构建失败
    pause
    exit /b 1
)
echo [完成] 镜像重新构建完成
goto :end

REM ==================== 查看日志 ====================
:logs
echo [日志] 显示服务日志...
docker-compose -f %COMPOSE_FILE% logs -f --tail=100 %2
goto :end

REM ==================== 查看状态 ====================
:status
echo ========================================
echo   服务状态
echo ========================================
echo.
docker-compose -f %COMPOSE_FILE% ps
echo.
echo ========================================
echo   容器健康状态
echo ========================================
echo.
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" --filter "name=creative-master"
echo.
goto :end

REM ==================== 帮助信息 ====================
:help
echo.
echo ========================================
echo   全能创意大师 - 生产环境启动脚本
echo ========================================
echo.
echo 用法: start-prod.bat [命令]
echo.
echo 命令列表:
echo   init     - 初始化环境（创建配置、构建镜像）
echo   up       - 启动生产环境 (默认)
echo   down     - 停止所有服务
echo   restart  - 重启所有服务
echo   build    - 构建镜像（使用缓存）
echo   rebuild  - 无缓存重新构建镜像
echo   logs     - 查看服务日志
echo   ps       - 查看服务状态
echo   status   - 查看服务状态
echo   help     - 显示帮助信息
echo.
echo 环境配置:
echo   1. 复制 .env.cloud 为 .env
echo   2. 编辑 .env 文件，设置 SECRET_KEY 等关键配置
echo   3. 运行 start-prod.bat init 初始化环境
echo   4. 运行 start-prod.bat up 启动服务
echo.
echo 生产环境说明:
echo   - 使用 PostgreSQL 数据库（数据持久化）
echo   - 使用 Redis 缓存（提升性能）
echo   - 使用 Nginx 反向代理（统一入口）
echo   - 多 Worker 模式运行（提升并发能力）
echo.
echo 数据持久化:
echo   - 数据库数据: Docker Volume (postgres_data)
echo   - Redis数据: Docker Volume (redis_data)
echo   - 日志文件: ./backend/logs/
echo   - 上传文件: ./backend/data/uploads/
echo.
goto :end

:end
endlocal
