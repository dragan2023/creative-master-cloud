# 全能创意大师 - 一键启动脚本
# 在同一个终端窗口中启动前后端服务

$Host.UI.RawUI.WindowTitle = "全能创意大师 - 服务运行中"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     全能创意大师 - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir "backend"
$FrontendDir = Join-Path $ProjectDir "frontend"
$VenvPython = Join-Path $BackendDir "venv\Scripts\python.exe"

# 检查虚拟环境
if (-not (Test-Path $VenvPython)) {
    Write-Host "[错误] 后端虚拟环境不存在: $VenvPython" -ForegroundColor Red
    Write-Host "请先创建虚拟环境" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 清理旧进程
Write-Host "[1/3] 清理旧进程..." -ForegroundColor Yellow
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Stop-Process -Name node -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 启动后端服务
Write-Host "[2/3] 启动后端服务 (端口 8000)..." -ForegroundColor Yellow
Set-Location $BackendDir
Start-Process -FilePath $VenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" -NoNewWindow

# 启动前端服务
Write-Host "[3/3] 启动前端服务 (端口 5173)..." -ForegroundColor Yellow
Set-Location $FrontendDir
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -NoNewWindow

Set-Location $ProjectDir

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "     服务启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  前端地址: http://localhost:5173" -ForegroundColor Cyan
Write-Host "  后端地址: http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API文档:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3秒后自动打开浏览器..." -ForegroundColor Yellow
Write-Host ""

# 延迟3秒后打开浏览器
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"

Write-Host "========================================" -ForegroundColor Magenta
Write-Host " 服务运行中，关闭此窗口停止所有服务" -ForegroundColor Magenta
Write-Host " 或双击 stop.bat 停止服务" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# 保持窗口打开
Write-Host "按 Ctrl+C 或关闭窗口停止服务..." -ForegroundColor Gray
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host ""
    Write-Host "正在停止服务..." -ForegroundColor Yellow
    Stop-Process -Name python -Force -ErrorAction SilentlyContinue
    Stop-Process -Name node -Force -ErrorAction SilentlyContinue
    Write-Host "所有服务已停止" -ForegroundColor Green
}
