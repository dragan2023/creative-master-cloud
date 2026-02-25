#Requires -Version 5.1
<#
.SYNOPSIS
    全能创意大师一键启动脚本 (PowerShell版)

.DESCRIPTION
    自动检测并启动前后端服务，支持中文输出、错误处理、端口检测、自动打开浏览器

.EXAMPLE
    .\start.ps1
    .\start.ps1 -NoBrowser  # 启动但不打开浏览器
#>

param(
    [switch]$NoBrowser = $false
)

# 设置控制台编码为UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 颜色定义
$ColorInfo = "Cyan"
$ColorSuccess = "Green"
$ColorWarning = "Yellow"
$ColorError = "Red"
$ColorTitle = "Magenta"

# 项目路径
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "backend"
$FrontendDir = Join-Path $ScriptDir "frontend"
$VenvPython = Join-Path $BackendDir "venv\Scripts\python.exe"
$LogFile = Join-Path $ScriptDir "startup.log"

# 服务配置
$BackendPort = 8000
$FrontendPort = 5173
$BackendUrl = "http://localhost:$BackendPort"
$FrontendUrl = "http://localhost:$FrontendPort"

# 进程跟踪
$script:BackendProcess = $null
$script:FrontendProcess = $null

# ==================== 辅助函数 ====================

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8
}

function Write-ColorHost {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Show-Banner {
    Write-Host ""
    Write-ColorHost "========================================================" $ColorTitle
    Write-ColorHost "         全能创意大师 - 智能启动助手 v1.0          " $ColorTitle
    Write-ColorHost "========================================================" $ColorTitle
    Write-Host ""
}

function Test-Port {
    param([int]$Port)
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $connect = $tcpClient.BeginConnect("localhost", $Port, $null, $null)
        $wait = $connect.AsyncWaitHandle.WaitOne(1000)
        if ($wait -and $tcpClient.Connected) {
            $tcpClient.EndConnect($connect)
            $tcpClient.Close()
            return $true
        }
        $tcpClient.Close()
        return $false
    } catch {
        return $false
    }
}

function Stop-PortProcess {
    param([int]$Port)
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-ColorHost "  正在停止进程: $($process.ProcessName) (PID: $($process.Id))" $ColorWarning
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Milliseconds 500
        return $true
    } catch {
        return $false
    }
}

function Wait-ForService {
    param([string]$Url, [int]$TimeoutSeconds = 30)
    $startTime = Get-Date
    while (((Get-Date) - $startTime).TotalSeconds -lt $TimeoutSeconds) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                return $true
            }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Cleanup {
    Write-Log "正在清理进程..." "INFO"
    
    if ($script:BackendProcess -and !$script:BackendProcess.HasExited) {
        Write-ColorHost "  正在停止后端服务..." $ColorWarning
        Stop-Process -Id $script:BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    if ($script:FrontendProcess -and !$script:FrontendProcess.HasExited) {
        Write-ColorHost "  正在停止前端服务..." $ColorWarning
        Stop-Process -Id $script:FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

# ==================== 主流程 ====================

# 注册退出处理
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

try {
    Show-Banner
    
    # 初始化日志
    "启动日志 - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -FilePath $LogFile -Encoding UTF8
    
    # ---------- 第一步：检测Python环境 ----------
    Write-ColorHost "[第一步] 检测 Python 环境" $ColorInfo
    Write-Host ""
    
    $pythonCmd = $null
    if (Test-Path $VenvPython) {
        $pythonCmd = $VenvPython
        Write-ColorHost "  [OK] 虚拟环境Python: $VenvPython" $ColorSuccess
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonCmd = "python"
        $version = & python --version 2>&1
        Write-ColorHost "  [OK] 系统Python: $version" $ColorSuccess
    } else {
        Write-ColorHost "  [错误] 未找到Python环境！" $ColorError
        Write-Host ""
        Write-Host "  请先运行以下命令安装Python:" -ForegroundColor Yellow
        Write-Host "    1. 访问 https://www.python.org/downloads/"
        Write-Host "    2. 下载并安装 Python 3.10+"
        Write-Host "    3. 重新运行此脚本"
        Read-Host "按回车键退出"
        exit 1
    }
    
    # ---------- 第二步：检测Node.js环境 ----------
    Write-Host ""
    Write-ColorHost "[第二步] 检测 Node.js 环境" $ColorInfo
    Write-Host ""
    
    if (Get-Command node -ErrorAction SilentlyContinue) {
        $nodeVersion = & node --version 2>&1
        Write-ColorHost "  [OK] Node.js 版本: $nodeVersion" $ColorSuccess
    } else {
        Write-ColorHost "  [错误] 未找到Node.js环境！" $ColorError
        Write-Host ""
        Write-Host "  请先运行以下命令安装Node.js:" -ForegroundColor Yellow
        Write-Host "    1. 访问 https://nodejs.org/"
        Write-Host "    2. 下载并安装 LTS 版本"
        Write-Host "    3. 重新运行此脚本"
        Read-Host "按回车键退出"
        exit 1
    }
    
    # ---------- 第三步：检测端口占用 ----------
    Write-Host ""
    Write-ColorHost "[第三步] 检测端口占用" $ColorInfo
    Write-Host ""
    
    $needStopBackend = Test-Port $BackendPort
    $needStopFrontend = Test-Port $FrontendPort
    
    if ($needStopBackend -or $needStopFrontend) {
        Write-ColorHost "  发现端口被占用，正在释放..." $ColorWarning
        
        if ($needStopBackend) {
            Write-Host "  端口 $BackendPort 被占用" -ForegroundColor Yellow
            Stop-PortProcess -Port $BackendPort
        }
        
        if ($needStopFrontend) {
            Write-Host "  端口 $FrontendPort 被占用" -ForegroundColor Yellow
            Stop-PortProcess -Port $FrontendPort
        }
        
        Start-Sleep -Seconds 2
    }
    
    Write-ColorHost "  [OK] 端口检测完成" $ColorSuccess
    
    # ---------- 第四步：启动后端服务 ----------
    Write-Host ""
    Write-ColorHost "[第四步] 启动后端服务" $ColorInfo
    Write-Host ""
    
    # 检查虚拟环境
    if (-not (Test-Path $VenvPython)) {
        Write-ColorHost "  [警告] 虚拟环境不存在，正在创建..." $ColorWarning
        
        Push-Location $BackendDir
        & python -m venv venv
        & $VenvPython -m pip install --upgrade pip -q
        & $VenvPython -m pip install -r requirements.txt -q
        Pop-Location
        
        if ($LASTEXITCODE -ne 0) {
            Write-ColorHost "  [错误] 依赖安装失败！" $ColorError
            Read-Host "按回车键退出"
            exit 1
        }
        Write-ColorHost "  [OK] 虚拟环境创建完成" $ColorSuccess
    }
    
    Write-Host "  正在启动后端服务 (端口: $BackendPort)..." -NoNewline
    
    $backendStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $backendStartInfo.FileName = $VenvPython
    $backendStartInfo.Arguments = "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", $BackendPort
    $backendStartInfo.WorkingDirectory = $BackendDir
    $backendStartInfo.UseShellExecute = $false
    $backendStartInfo.RedirectStandardOutput = $true
    $backendStartInfo.RedirectStandardError = $true
    $backendStartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $backendStartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    
    $script:BackendProcess = New-Object System.Diagnostics.Process
    $script:BackendProcess.StartInfo = $backendStartInfo
    $null = $script:BackendProcess.Start()
    
    Write-ColorHost " [OK]" $ColorSuccess
    Write-Log "后端服务已启动 (PID: $($script:BackendProcess.Id))" "INFO"
    
    # 等待后端就绪
    Write-Host "  等待后端服务就绪..." -NoNewline
    if (Wait-ForService -Url "$BackendUrl/docs" -TimeoutSeconds 30) {
        Write-ColorHost " [OK]" $ColorSuccess
    } else {
        Write-ColorHost " [超时]" $ColorError
        Write-ColorHost "  [警告] 后端服务启动超时，请检查日志" $ColorWarning
    }
    
    # ---------- 第五步：启动前端服务 ----------
    Write-Host ""
    Write-ColorHost "[第五步] 启动前端服务" $ColorInfo
    Write-Host ""
    
    # 检查node_modules
    $nodeModules = Join-Path $FrontendDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-ColorHost "  [警告] node_modules不存在，正在安装依赖..." $ColorWarning
        
        Push-Location $FrontendDir
        & npm install --silent
        Pop-Location
        
        if ($LASTEXITCODE -ne 0) {
            Write-ColorHost "  [错误] 前端依赖安装失败！" $ColorError
            Read-Host "按回车键退出"
            exit 1
        }
        Write-ColorHost "  [OK] 前端依赖安装完成" $ColorSuccess
    }
    
    Write-Host "  正在启动前端服务 (端口: $FrontendPort)..." -NoNewline
    
    $frontendStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $frontendStartInfo.FileName = "npm"
    $frontendStartInfo.Arguments = "run", "dev"
    $frontendStartInfo.WorkingDirectory = $FrontendDir
    $frontendStartInfo.UseShellExecute = $false
    $frontendStartInfo.RedirectStandardOutput = $true
    $frontendStartInfo.RedirectStandardError = $true
    $frontendStartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $frontendStartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    
    $script:FrontendProcess = New-Object System.Diagnostics.Process
    $script:FrontendProcess.StartInfo = $frontendStartInfo
    $null = $script:FrontendProcess.Start()
    
    Write-ColorHost " [OK]" $ColorSuccess
    Write-Log "前端服务已启动 (PID: $($script:FrontendProcess.Id))" "INFO"
    
    # 等待前端就绪
    Write-Host "  等待前端服务就绪..." -NoNewline
    Start-Sleep -Seconds 3
    
    if (Test-Port $FrontendPort) {
        Write-ColorHost " [OK]" $ColorSuccess
    } else {
        Write-ColorHost " [超时]" $ColorError
        Write-ColorHost "  [警告] 前端服务启动超时，请检查日志" $ColorWarning
    }
    
    # ---------- 完成启动 ----------
    Write-Host ""
    Write-ColorHost "========================================================" $ColorSuccess
    Write-ColorHost "              启动完成！系统已就绪" $ColorSuccess
    Write-ColorHost "========================================================" $ColorSuccess
    Write-Host ""
    Write-Host "  访问地址:"
    Write-ColorHost "    主界面: $FrontendUrl" $ColorInfo
    Write-ColorHost "    API文档: $BackendUrl/docs" $ColorInfo
    Write-Host ""
    Write-Host "  注意事项:"
    Write-Host "    - 请勿关闭此窗口，否则服务将停止"
    Write-Host "    - 按 Ctrl+C 可停止服务"
    Write-Host "    - 日志文件: $LogFile"
    Write-Host ""
    
    # 打开浏览器
    if (-not $NoBrowser) {
        Write-Host "  浏览器将在 5 秒后自动打开..."
        Start-Sleep -Seconds 5
        Start-Process $FrontendUrl
    }
    
    Write-Log "启动完成" "INFO"
    
    # 保持运行
    Write-Host ""
    Write-ColorHost "按 Ctrl+C 停止所有服务..." $ColorWarning
    Write-Host ""
    
    # 等待用户中断
    while ($true) {
        if ($script:BackendProcess.HasExited -or $script:FrontendProcess.HasExited) {
            Write-ColorHost "检测到服务异常退出！" $ColorError
            break
        }
        Start-Sleep -Seconds 1
    }
    
} catch {
    Write-ColorHost "发生错误: $_" $ColorError
    Write-Log "错误: $_" "ERROR"
} finally {
    Cleanup
}

Write-Host ""
Write-ColorHost "服务已停止。按任意键退出..." $ColorWarning
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
