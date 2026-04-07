@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   全能创意大师 - 本地生产环境测试
echo ========================================
echo.
echo 此脚本将在本地启动与云端完全相同的容器化生产环境
echo 用于在推送代码前进行完整的功能验证
echo.

:: 检查 Docker 是否运行
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

:: 设置项目根目录
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: 创建必要的数据目录
echo [1/5] 创建数据目录...
if not exist "backend\data" mkdir "backend\data"
if not exist "backend\data\character_states" mkdir "backend\data\character_states"
if not exist "backend\data\chroma" mkdir "backend\data\chroma"
if not exist "backend\data\uploads" mkdir "backend\data\uploads"
if not exist "backend\data\knowledge_graphs" mkdir "backend\data\knowledge_graphs"
if not exist "backend\data\novel_projects" mkdir "backend\data\novel_projects"
if not exist "backend\data\exports" mkdir "backend\data\exports"
if not exist "backend\data\backups" mkdir "backend\data\backups"
if not exist "backend\logs" mkdir "backend\logs"

:: 复制环境配置文件
echo [2/5] 配置环境变量...
if not exist ".env" (
    copy ".env.local.prod" ".env" >nul
    echo       已复制 .env.local.prod 到 .env
) else (
    echo       .env 已存在，跳过复制
)

:: 停止可能存在的旧容器
echo [3/5] 清理旧容器...
docker-compose -f docker-compose.prod.yml down --remove-orphans 2>nul

:: 构建镜像
echo [4/5] 构建生产镜像（首次运行较慢）...
echo       这将使用与云端完全相同的 Dockerfile.prod
docker-compose -f docker-compose.prod.yml build --no-cache

if errorlevel 1 (
    echo.
    echo [错误] 镜像构建失败，请检查错误信息
    pause
    exit /b 1
)

:: 启动服务
echo [5/5] 启动生产环境服务...
docker-compose -f docker-compose.prod.yml up -d

if errorlevel 1 (
    echo.
    echo [错误] 服务启动失败，请检查错误信息
    pause
    exit /b 1
)

:: 等待服务就绪
echo.
echo 等待服务启动...
timeout /t 10 /nobreak >nul

:: 检查服务状态
echo.
echo ========================================
echo   服务状态
echo ========================================
docker-compose -f docker-compose.prod.yml ps

echo.
echo ========================================
echo   访问地址
echo ========================================
echo   前端界面: http://localhost
echo   API文档:  http://localhost/docs
echo   健康检查: http://localhost/health
echo.
echo   测试账号: admin / admin123
echo ========================================
echo.
echo 提示：
echo   - 使用 'docker-compose -f docker-compose.prod.yml logs -f' 查看日志
echo   - 使用 'docker-compose -f docker-compose.prod.yml down' 停止服务
echo   - 测试完成后请运行 stop-local-prod.bat 停止服务
echo.

:: 打开浏览器
echo 按任意键打开浏览器访问测试环境...
pause >nul
start http://localhost

endlocal
