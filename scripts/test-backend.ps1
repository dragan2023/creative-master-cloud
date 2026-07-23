<#
.SYNOPSIS
    后端测试统一入口，固定使用后端虚拟环境解释器运行 pytest。

.DESCRIPTION
    该脚本解析项目根目录并固定调用 backend\venv\Scripts\python.exe，
    严禁静默回退到系统 Python。若虚拟环境解释器缺失，则明确提示先运行
    run-local.ps1 并以非零退出码结束。

.PARAMETER PrintCommand
    仅打印将要执行的命令字符串并退出（用于测试与排查），不实际运行测试。

.PARAMETER PytestArgs
    追加到固定 pytest 参数之后的额外参数。

.EXAMPLE
    scripts\test-backend.ps1
    scripts\test-backend.ps1 -PrintCommand
    scripts\test-backend.ps1 -- -k character_state
#>
[CmdletBinding()]
param(
    [switch]$PrintCommand,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 解析项目根目录（脚本位于 <ProjectRoot>\scripts）
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# 固定使用后端虚拟环境解释器，严禁回退到系统 Python
$BackendPython = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"

# 固定测试目标与参数（与验收命令一致）
$FixedArgs = @("-m", "pytest", "backend/tests", "tests", "-q", "-p", "no:cacheprovider")
if ($PytestArgs) {
    $FixedArgs += $PytestArgs
}

# 组装可读命令字符串（用于打印/测试断言）
$CommandString = ('"{0}" {1}' -f $BackendPython, ($FixedArgs -join ' '))

if ($PrintCommand) {
    Write-Output $CommandString
    exit 0
}

if (-not (Test-Path $BackendPython)) {
    Write-Error "未找到后端虚拟环境解释器: $BackendPython`n请先运行 run-local.ps1 初始化后端环境后再执行本脚本。"
    exit 1
}

Set-Location $ProjectRoot
& $BackendPython @FixedArgs
exit $LASTEXITCODE
