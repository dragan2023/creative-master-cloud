@echo off
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 快速测试API连接
REM ========================================

echo.
echo ========================================
echo   测试本地开发环境API
echo ========================================
echo.

echo [1] 测试后端健康检查...
curl -s http://localhost:8000/health
echo.
echo.

echo [2] 测试Nginx代理...
curl -s http://localhost/health
echo.
echo.

echo [3] 测试数据库连接...
curl -s http://localhost/api/v1/health
echo.
echo.

echo [4] 测试Redis连接...
curl -s http://localhost/api/v1/system/info
echo.
echo.

echo ========================================
echo   测试完成
echo ========================================
pause
