@echo off
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 环境验证脚本
REM 验证本地与云端环境一致性
REM ========================================

echo.
echo ========================================
echo   本地开发环境验证
echo ========================================
echo.

set PASS=0
set FAIL=0

REM 1. Docker检查
echo [1/7] 检查Docker环境...
docker info >nul 2>&1
if errorlevel 1 (
    echo     [FAIL] Docker未运行
    set /a FAIL+=1
) else (
    echo     [PASS] Docker运行正常
    set /a PASS+=1
)

REM 2. 环境变量文件检查
echo.
echo [2/7] 检查环境配置文件...
if exist ".env.local" (
    echo     [PASS] .env.local 存在
    set /a PASS+=1
) else (
    echo     [FAIL] .env.local 不存在
    set /a FAIL+=1
)

REM 3. Docker配置文件检查
echo.
echo [3/7] 检查Docker配置文件...
if exist "docker-compose.dev.yml" (
    echo     [PASS] docker-compose.dev.yml 存在
    set /a PASS+=1
) else (
    echo     [FAIL] docker-compose.dev.yml 不存在
    set /a FAIL+=1
)

if exist "nginx\dev.conf" (
    echo     [PASS] nginx\dev.conf 存在
    set /a PASS+=1
) else (
    echo     [FAIL] nginx\dev.conf 不存在
    set /a FAIL+=1
)

REM 4. 服务状态检查
echo.
echo [4/7] 检查容器服务状态...
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>nul | findstr "creative" >nul
if errorlevel 1 (
    echo     [INFO] 无运行中的容器，运行 start-dev.bat up 启动服务
) else (
    echo     [PASS] 发现运行中的容器:
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>nul | findstr "creative"
    set /a PASS+=1
)

REM 5. 端口检查
echo.
echo [5/7] 检查端口占用...
netstat -ano | findstr ":80 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo     [INFO] 端口80可用
) else (
    echo     [WARN] 端口80已被占用
)

netstat -ano | findstr ":5432 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo     [INFO] 端口5432可用
) else (
    echo     [WARN] 端口5432已被占用
)

netstat -ano | findstr ":6379 " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo     [INFO] 端口6379可用
) else (
    echo     [WARN] 端口6379已被占用
)

REM 6. 前端构建检查
echo.
echo [6/7] 检查前端构建产物...
if exist "backend\app\static\index.html" (
    echo     [PASS] 前端已构建
    set /a PASS+=1
) else (
    echo     [INFO] 前端未构建，需要先构建前端
    echo     [提示] 运行: cd frontend ^&^& npm run build
)

REM 7. 云端配置对比
echo.
echo [7/7] 检查与云端配置一致性...

REM 比较环境变量
findstr /C:"DATABASE_URL" .env.local >nul 2>&1
if errorlevel 1 (
    echo     [FAIL] 缺少DATABASE_URL配置
    set /a FAIL+=1
) else (
    echo     [PASS] DATABASE_URL已配置
    set /a PASS+=1
)

findstr /C:"REDIS_URL" .env.local >nul 2>&1
if errorlevel 1 (
    echo     [FAIL] 缺少REDIS_URL配置
    set /a FAIL+=1
) else (
    echo     [PASS] REDIS_URL已配置
    set /a PASS+=1
)

echo.
echo ========================================
echo   验证结果
echo ========================================
echo 通过: %PASS% 项
echo 失败: %FAIL% 项
echo.

if %FAIL% gtr 0 (
    echo [警告] 存在配置问题，请检查上述失败项
) else (
    echo [成功] 环境验证通过
)

echo.
echo ========================================
echo   云端环境对比提示
echo ========================================
echo 本地环境与云端差异:
echo   1. DEBUG=True (云端为False)
echo   2. 数据库使用相同PostgreSQL 15
echo   3. Redis使用相同Redis 7
echo   4. Nginx配置结构与云端一致
echo.
echo 部署前检查清单:
echo   [ ] 确认所有功能本地测试通过
echo   [ ] 检查API响应格式一致
echo   [ ] 确认数据库迁移脚本正确
echo   [ ] 修改.env为云端配置
echo   [ ] 设置SECRET_KEY
echo   [ ] 关闭DEBUG模式
echo.

pause
