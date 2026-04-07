@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   查看本地生产环境日志
echo ========================================
echo.

cd /d "%~dp0"

echo 选择要查看的服务：
echo   1. 全部服务
echo   2. 后端服务 (backend)
echo   3. 数据库 (db)
echo   4. Redis
echo   5. Nginx
echo.
choice /c 12345 /n /m "请选择: "

if errorlevel 5 (
    docker-compose -f docker-compose.prod.yml logs -f nginx
) else if errorlevel 4 (
    docker-compose -f docker-compose.prod.yml logs -f redis
) else if errorlevel 3 (
    docker-compose -f docker-compose.prod.yml logs -f db
) else if errorlevel 2 (
    docker-compose -f docker-compose.prod.yml logs -f backend
) else (
    docker-compose -f docker-compose.prod.yml logs -f
)
