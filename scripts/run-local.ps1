#!/usr/bin/env powershell
# ========================================
# 全能创意大师 - 非容器化本地开发环境
# 支持前后端热更新，无需 Docker
# ========================================

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "install", "stop", "status", "help")]
    [string]$Command = "start"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " $Text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Test-PortInUse {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Stop-ProcessOnPort {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "  [停止] 正在停止进程 (PID: $($process.Id))" -ForegroundColor Yellow
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Test-Environment {
    Write-Header "检查运行环境"
    
    # 检查 Python
    if (-not (Test-Command "python")) {
        Write-Host "[错误] 未检测到 Python，请先安装 Python 3.10+" -ForegroundColor Red
        Write-Host "       下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
    $pythonVersion = (python --version 2>&1).ToString().Split()[1]
    Write-Host "[OK] Python $pythonVersion" -ForegroundColor Green
    
    # 检查 Node.js
    if (-not (Test-Command "node")) {
        Write-Host "[错误] 未检测到 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
        Write-Host "       下载地址: https://nodejs.org/" -ForegroundColor Yellow
        exit 1
    }
    $nodeVersion = (node --version).ToString().TrimStart('v')
    Write-Host "[OK] Node.js $nodeVersion" -ForegroundColor Green
    
    # 检查 npm
    $npmVersion = (npm --version).ToString()
    Write-Host "[OK] npm $npmVersion" -ForegroundColor Green
    
    Write-Host ""
    return $true
}

function Install-Dependencies {
    Write-Header "安装依赖"
    
    Test-Environment
    
    # 安装后端依赖
    Write-Host "[后端] 正在安装 Python 依赖（使用清华源）..." -ForegroundColor Cyan
    Push-Location $BackendDir
    
    # 检查虚拟环境
    if (-not (Test-Path "venv")) {
        Write-Host "[创建] 正在创建 Python 虚拟环境..." -ForegroundColor Yellow
        python -m venv venv
    }
    
    # 激活虚拟环境并安装依赖
    & ".\venv\Scripts\activate.ps1"
    Write-Host "[安装] 正在安装依赖（清华源）..." -ForegroundColor Yellow
    pip install -r requirements.txt -c constraints.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[警告] 部分依赖安装失败，尝试继续..." -ForegroundColor Yellow
    }
    deactivate
    Pop-Location
    
    Write-Host "[完成] 后端依赖安装完成" -ForegroundColor Green
    
    # 安装前端依赖
    Write-Host ""
    Write-Host "[前端] 正在安装 Node.js 依赖..." -ForegroundColor Cyan
    Push-Location $FrontendDir
    npm install --registry=https://registry.npmmirror.com
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 前端依赖安装失败" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    
    Write-Host "[完成] 前端依赖安装完成" -ForegroundColor Green
    
    Write-Header "依赖安装完成！"
    Write-Host "运行 '.\run-local.ps1 start' 启动开发环境" -ForegroundColor Yellow
}

function Start-Development {
    Write-Header "启动开发环境"
    
    Test-Environment
    
    # 检查后端虚拟环境
    if (-not (Test-Path "$BackendDir\venv")) {
        Write-Host "[警告] 未找到 Python 虚拟环境，正在自动安装依赖..." -ForegroundColor Yellow
        Install-Dependencies
    }
    
    # 检查前端 node_modules
    if (-not (Test-Path "$FrontendDir\node_modules")) {
        Write-Host "[警告] 未找到前端依赖，正在自动安装..." -ForegroundColor Yellow
        Push-Location $FrontendDir
        npm install --registry=https://registry.npmmirror.com
        Pop-Location
    }
    
    Write-Host ""
    Write-Host "[启动模式] 热更新模式" -ForegroundColor Magenta
    Write-Host "  - 后端: uvicorn --reload （代码修改自动重载）" -ForegroundColor Cyan
    Write-Host "  - 前端: Vite HMR （代码修改实时刷新）" -ForegroundColor Cyan
    Write-Host ""
    
    # 启动后端服务
    Write-Host "[后端] 正在启动后端服务..." -ForegroundColor Cyan
    $backendJob = Start-Job -ScriptBlock {
        param($backendDir)
        Set-Location $backendDir
        & ".\venv\Scripts\activate.ps1"
        python -m uvicorn app.main:app --host 0.0.0.0 --port 7000 --reload
    } -ArgumentList $BackendDir
    
    # 等待后端启动
    Write-Host "[等待] 正在等待后端服务就绪..." -ForegroundColor Yellow
    $waitCount = 0
    while ($waitCount -lt 30) {
        try {
            $null = Invoke-WebRequest -Uri "http://localhost:7000/health" -TimeoutSec 1 -ErrorAction SilentlyContinue
            Write-Host "[就绪] 后端服务已就绪 (等待 $waitCount 秒)" -ForegroundColor Green
            break
        } catch {
            $waitCount++
            Start-Sleep -Seconds 1
        }
    }
    if ($waitCount -ge 30) {
        Write-Host "[警告] 后端启动超时，请检查日志" -ForegroundColor Yellow
    }
    
    # 启动前端服务
    Write-Host ""
    Write-Host "[前端] 正在启动前端开发服务器..." -ForegroundColor Cyan
    $env:BROWSER = "none"
    $frontendJob = Start-Job -ScriptBlock {
        param($frontendDir)
        Set-Location $frontendDir
        $env:BROWSER = "none"
        npm run dev
    } -ArgumentList $FrontendDir
    
    # 等待前端启动并检测端口
    Write-Host "[等待] 正在等待前端服务就绪..." -ForegroundColor Yellow
    $waitCount = 0
    $frontendPort = $null
    while ($waitCount -lt 30) {
        foreach ($port in @(5173, 5174, 5175, 5176, 5177, 5178, 5179, 5180)) {
            if ((Test-PortInUse $port) -and -not $frontendPort) {
                $frontendPort = $port
                Write-Host "[就绪] 前端服务已就绪 (端口 $port, 等待 $waitCount 秒)" -ForegroundColor Green
                break
            }
        }
        if ($frontendPort) { break }
        $waitCount++
        Start-Sleep -Seconds 1
    }
    
    if (-not $frontendPort) {
        Write-Host "[警告] 前端启动超时" -ForegroundColor Yellow
        $frontendPort = 5173
    }
    
    Show-Info $frontendPort
    
    # 自动打开浏览器
    Write-Host "[提示] 自动打开浏览器..." -ForegroundColor Yellow
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:$frontendPort"
    
    # 等待作业
    Write-Header "实时日志（Ctrl+C 退出）"
    Write-Host "提示: 按 Ctrl+C 只会退出日志显示，服务继续运行" -ForegroundColor Green
    Write-Host ""
    
    # 显示后端日志
    Receive-Job -Job $backendJob -Wait -AutoRemoveJob
}

function Show-Info {
    param([int]$FrontendPort = 5173)
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " 开发环境已启动" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  访问地址:" -ForegroundColor White
    Write-Host "  - 前端开发服务器: " -NoNewline; Write-Host "http://localhost:$FrontendPort" -ForegroundColor Yellow
    Write-Host "  - 后端 API:       " -NoNewline; Write-Host "http://localhost:7000" -ForegroundColor Yellow
    Write-Host "  - API 文档:       " -NoNewline; Write-Host "http://localhost:7000/docs" -ForegroundColor Yellow
    Write-Host "  - API 文档(ReDoc): " -NoNewline; Write-Host "http://localhost:7000/redoc" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " 热更新说明" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  - 修改前端代码（.vue, .js, .css 等）后会自动刷新浏览器"
    Write-Host "  - 修改后端代码（.py 文件）后会自动重启服务"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " 常用命令" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  安装依赖:  .\run-local.ps1 install" -ForegroundColor Yellow
    Write-Host "  停止服务:  .\run-local.ps1 stop" -ForegroundColor Yellow
    Write-Host "  查看状态:  .\run-local.ps1 status" -ForegroundColor Yellow
    Write-Host ""
}

function Stop-Development {
    Write-Header "停止开发服务"
    
    # 停止后端进程
    if (Test-PortInUse 7000) {
        Write-Host "[停止] 正在停止后端服务..." -ForegroundColor Yellow
        Stop-ProcessOnPort 7000
    }
    
    # 停止前端进程
    foreach ($port in @(5173, 5174, 5175, 5176, 5177, 5178, 5179, 5180)) {
        if (Test-PortInUse $port) {
            Write-Host "[停止] 正在停止前端服务 (端口 $port)..." -ForegroundColor Yellow
            Stop-ProcessOnPort $port
        }
    }
    
    Write-Host "[完成] 开发服务已停止" -ForegroundColor Green
}

function Show-Status {
    Write-Header "服务状态"
    
    # 检查后端状态
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:7000/health" -TimeoutSec 2
        Write-Host "[运行中] 后端服务 - http://localhost:7000" -ForegroundColor Green
    } catch {
        Write-Host "[已停止] 后端服务" -ForegroundColor Red
    }
    
    # 检查前端状态
    $frontendRunning = $false
    foreach ($port in @(5173, 5174, 5175, 5176, 5177, 5178, 5179, 5180)) {
        if (Test-PortInUse $port) {
            Write-Host "[运行中] 前端服务 - http://localhost:$port" -ForegroundColor Green
            $frontendRunning = $true
        }
    }
    if (-not $frontendRunning) {
        Write-Host "[已停止] 前端服务" -ForegroundColor Red
    }
    
    Write-Host ""
}

function Show-Help {
    Write-Header "全能创意大师 - 本地开发环境启动脚本"
    
    Write-Host "用法: .\run-local.ps1 [命令]"
    Write-Host ""
    Write-Host "命令列表:"
    Write-Host "  start   - 启动开发环境 (默认)"
    Write-Host "  install - 安装所有依赖"
    Write-Host "  stop    - 停止所有服务"
    Write-Host "  status  - 查看服务状态"
    Write-Host "  help    - 显示帮助信息"
    Write-Host ""
    Write-Host "环境要求:"
    Write-Host "  - Python 3.10+ (推荐 3.11 或 3.12)"
    Write-Host "  - Node.js 18+ (推荐 20 LTS)"
    Write-Host ""
    Write-Host "热更新说明:"
    Write-Host "  - 前端: Vite 内置 HMR，修改代码自动刷新浏览器"
    Write-Host "  - 后端: uvicorn --reload，修改代码自动重启服务"
    Write-Host ""
    Write-Host "数据存储:"
    Write-Host "  - 数据库: SQLite (backend/data/creative_master.db)"
    Write-Host "  - 向量库: ChromaDB (backend/data/chroma/)"
    Write-Host "  - 上传文件: backend/data/uploads/"
    Write-Host ""
    Write-Host "注意事项:"
    Write-Host "  - 首次运行会自动安装依赖"
    Write-Host "  - 依赖安装使用清华镜像源加速"
    Write-Host "  - 服务窗口关闭后服务会停止"
    Write-Host ""
}

# 主命令分发
switch ($Command) {
    "start" { Start-Development }
    "install" { Install-Dependencies }
    "stop" { Stop-Development }
    "status" { Show-Status }
    "help" { Show-Help }
}
