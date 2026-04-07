@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   本地生产环境健康检查
echo ========================================
echo.

cd /d "%~dp0"

echo [1/6] 检查 Docker 容器状态...
docker-compose -f docker-compose.prod.yml ps

echo.
echo [2/6] 检查后端健康接口...
curl -s http://localhost/health | findstr "ok healthy" >nul
if errorlevel 1 (
    echo       [警告] 后端健康检查失败
) else (
    echo       [OK] 后端服务正常
)

echo.
echo [3/6] 检查 API 文档访问...
curl -s -o nul -w "%%{http_code}" http://localhost/docs | findstr "200" >nul
if errorlevel 1 (
    echo       [警告] API文档无法访问
) else (
    echo       [OK] API文档可访问
)

echo.
echo [4/6] 检查前端页面...
curl -s -o nul -w "%%{http_code}" http://localhost/ | findstr "200" >nul
if errorlevel 1 (
    echo       [警告] 前端页面无法访问
) else (
    echo       [OK] 前端页面可访问
)

echo.
echo [5/6] 检查数据库连接...
docker exec creative-master-db pg_isready -U creative_user -d creative_master >nul 2>&1
if errorlevel 1 (
    echo       [警告] 数据库连接异常
) else (
    echo       [OK] 数据库连接正常
)

echo.
echo [6/6] 检查 Redis 连接...
docker exec creative-master-redis redis-cli ping | findstr "PONG" >nul
if errorlevel 1 (
    echo       [警告] Redis连接异常
) else (
    echo       [OK] Redis连接正常
)

echo.
echo ========================================
echo   检测完成
echo ========================================
echo.
echo 详细测试建议：
echo   1. 访问 http://localhost 进行功能测试
echo   2. 测试账号: admin / admin123
echo   3. 测试人物状态追踪器保存功能
echo   4. 测试知识库上传和检索功能
echo   5. 测试小说生成流程
echo.
pause
