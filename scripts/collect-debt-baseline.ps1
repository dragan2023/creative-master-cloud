<#
.SYNOPSIS
    Phase01 Debt Inventory - Reproducible Baseline Snapshot Collector

.DESCRIPTION
    Read-only output of current environment and code baseline info to reports/technical-debt/.
    No writes, deletes, or code changes. Strictly follows global red lines.
    Report contains NO keys, user content, or production data.

.OUTPUTS
    reports/technical-debt/baseline-YYYYMMDD-HHmmss.txt
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ReportDir = Join-Path $ProjectRoot "reports\technical-debt"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ReportFile = Join-Path $ReportDir "baseline-$Timestamp.txt"

if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

$BackendPython = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"

function Write-Section {
    param([string]$Title)
    "`n$('=' * 60)" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    "  $Title" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    "$('=' * 60)" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
}

function Invoke-Cmd {
    param([string]$Label, [ScriptBlock]$Command, [string]$ErrMsg = "N/A")
    try {
        $output = & $Command 2>&1 | Out-String
        ">>> $Label" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
        $output.TrimEnd() | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    } catch {
        ">>> $Label [ERROR]: $ErrMsg" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
    }
}

"Tech Debt Baseline Snapshot - $Timestamp" | Out-File -FilePath $ReportFile -Encoding UTF8
"Project Root: $ProjectRoot" | Out-File -FilePath $ReportFile -Append -Encoding UTF8

Write-Section "Git Status"
Invoke-Cmd "git rev-parse HEAD" { git -C $ProjectRoot rev-parse HEAD }
Invoke-Cmd "git status --short" { git -C $ProjectRoot status --short }
Invoke-Cmd "git log -1" { git -C $ProjectRoot log -1 --format="%H %ai %s" }

Write-Section "Runtime Versions"
Invoke-Cmd "python --version" { & $BackendPython --version }
Invoke-Cmd "node --version" { node --version }
Invoke-Cmd "npm --version" { npm.cmd --version }

Write-Section "Alembic Status"
Invoke-Cmd "alembic heads" {
    Push-Location (Join-Path $ProjectRoot "backend")
    try { & $BackendPython -m alembic heads 2>&1 }
    finally { Pop-Location }
}

Write-Section "Backend Tests"
Invoke-Cmd "pytest -q" {
    & $BackendPython -m pytest (Join-Path $ProjectRoot "backend\tests") (Join-Path $ProjectRoot "tests") -q -p no:cacheprovider 2>&1
}

Write-Section "Backend Compile"
Invoke-Cmd "compileall" {
    & $BackendPython -m compileall -q (Join-Path $ProjectRoot "backend\app") 2>&1
}

Write-Section "Frontend Deps"
Invoke-Cmd "npm ci --dry-run" {
    Push-Location (Join-Path $ProjectRoot "frontend")
    try { npm.cmd ci --dry-run 2>&1 }
    finally { Pop-Location }
}

Write-Section "Build Warnings"
Invoke-Cmd "build warnings" {
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        $output = npm.cmd run build 2>&1 | Out-String
        $warnPattern = [regex]::new('warn|WARN|warning|deprecated|DEPRECATED', 'IgnoreCase')
        $lines = $output -split "`n" | Where-Object { $warnPattern.IsMatch($_) }
        if ($lines) { $lines -join "`n" } else { "No build warnings detected." }
    }
    finally { Pop-Location }
}

Write-Section "Code Stats"
Invoke-Cmd "backend .py count" {
    (Get-ChildItem -Path (Join-Path $ProjectRoot "backend\app") -Filter "*.py" -Recurse -ErrorAction SilentlyContinue).Count
}
Invoke-Cmd "frontend .js/.vue count" {
    $js = (Get-ChildItem -Path (Join-Path $ProjectRoot "frontend\src") -Filter "*.js" -Recurse -ErrorAction SilentlyContinue).Count
    $vue = (Get-ChildItem -Path (Join-Path $ProjectRoot "frontend\src") -Filter "*.vue" -Recurse -ErrorAction SilentlyContinue).Count
    "JS: $js, Vue: $vue"
}

Write-Section "App Version"
Invoke-Cmd "version.json" {
    Get-Content (Join-Path $ProjectRoot "version.json") -Raw
}

"`nBaseline completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -FilePath $ReportFile -Append -Encoding UTF8
Write-Host "Baseline report: $ReportFile" -ForegroundColor Green
Write-Host "No keys, user content, or production data included." -ForegroundColor Cyan
