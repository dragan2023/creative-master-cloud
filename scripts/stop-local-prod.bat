@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   停止本地生产环境测试
echo ========================================
echo.

cd /d "%~dp0"

echo 正在停止服务...
docker-compose -f docker-compose.prod.yml down

echo.
echo 服务已停止
echo.
echo 是否清理数据卷？（将删除所有测试数据）
echo 按 Y 清理，按其他键保留数据
choice /c YN /n /m "请选择: "
if errorlevel 2 (
    echo 保留数据卷
) else (
    echo 清理数据卷...
    docker-compose -f docker-compose.prod.yml down -v
    echo 数据已清理
)

echo.
pause
