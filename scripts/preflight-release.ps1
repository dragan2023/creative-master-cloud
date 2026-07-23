<#
.SYNOPSIS
    Runs the required pre-release validation gates.

.DESCRIPTION
    Uses the backend virtual environment, verifies the Python test suite and
    application syntax, optionally runs the frontend quality gate, and scans
    tracked files for sensitive filenames or plaintext API-key signatures.
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$BackendPython = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"
$BinaryExtensions = @(
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".zip", ".gz", ".7z", ".mp4", ".mp3", ".woff", ".woff2",
    ".ttf", ".eot", ".db", ".sqlite", ".pyc", ".xlsx", ".docx"
)
$MaxScanFileBytes = 1MB

function Write-Gate {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Test-BackendPython {
    if (-not (Test-Path -LiteralPath $BackendPython)) {
        throw "Backend virtual environment interpreter was not found: $BackendPython"
    }
}

function Invoke-BackendTests {
    Write-Gate "Backend tests"
    & $BackendPython -m pytest backend/tests tests -q -p no:cacheprovider | Out-Host
    $exitCode = $LASTEXITCODE
    return ($exitCode -eq 0)
}

function Invoke-BackendCompile {
    Write-Gate "Backend syntax compilation"
    & $BackendPython -m compileall -q backend/app | Out-Host
    $exitCode = $LASTEXITCODE
    return ($exitCode -eq 0)
}

function Invoke-FrontendQuality {
    Write-Gate "Frontend quality build"
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        & npm.cmd run check:quality | Out-Host
        $exitCode = $LASTEXITCODE
        return ($exitCode -eq 0)
    }
    finally {
        Pop-Location
    }
}

function Get-TrackedFiles {
    $files = & git -C $ProjectRoot ls-files 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed; cannot perform the tracked-file secret scan."
    }
    return $files
}

function Test-SensitiveFileName {
    param([string]$RelativePath)
    $leaf = Split-Path -Leaf $RelativePath
    if ($leaf -eq ".env.cloud") {
        return "env-cloud-file"
    }
    if ($leaf -match "^id_rsa" -or $leaf -match "\.(pem|key|pfx|p12)$") {
        return "private-key-file"
    }
    return $null
}

function Test-PlaintextApiKey {
    param([string]$AbsolutePath)
    $extension = [System.IO.Path]::GetExtension($AbsolutePath).ToLowerInvariant()
    if ($BinaryExtensions -contains $extension) { return $false }

    $info = Get-Item -LiteralPath $AbsolutePath -ErrorAction SilentlyContinue
    if ($null -eq $info -or $info.Length -gt $MaxScanFileBytes) { return $false }

    $content = Get-Content -LiteralPath $AbsolutePath -Raw -ErrorAction SilentlyContinue
    if ([string]::IsNullOrEmpty($content)) { return $false }

    foreach ($pattern in @(
        "sk-[A-Za-z0-9]{20,}",
        "AKIA[0-9A-Z]{16}",
        "AIza[0-9A-Za-z_\-]{35}"
    )) {
        if ($content -match $pattern) { return $true }
    }
    return $false
}

function Invoke-SecretScan {
    Write-Gate "Tracked-file secret scan"
    $findings = @()
    foreach ($relativePath in (Get-TrackedFiles)) {
        $nameRule = Test-SensitiveFileName -RelativePath $relativePath
        if ($nameRule) {
            $findings += [pscustomobject]@{ File = $relativePath; Rule = $nameRule }
            continue
        }

        $absolutePath = Join-Path $ProjectRoot $relativePath
        if ((Test-Path -LiteralPath $absolutePath) -and (Test-PlaintextApiKey -AbsolutePath $absolutePath)) {
            $findings += [pscustomobject]@{ File = $relativePath; Rule = "plaintext-api-key" }
        }
    }

    if ($findings.Count -eq 0) {
        Write-Host "No sensitive files or suspected plaintext API keys found." -ForegroundColor Green
        return $true
    }

    Write-Host "Potential sensitive files found (filename and rule only):" -ForegroundColor Red
    foreach ($finding in $findings) {
        Write-Host ("  [{0}] {1}" -f $finding.Rule, $finding.File) -ForegroundColor Red
    }
    return $false
}

Test-BackendPython
Set-Location $ProjectRoot

$results = [ordered]@{}
$results["Backend tests"] = Invoke-BackendTests
$results["Backend syntax compilation"] = Invoke-BackendCompile
if ($SkipFrontend) {
    Write-Host "`nFrontend quality gate skipped." -ForegroundColor Yellow
}
else {
    $results["Frontend quality build"] = Invoke-FrontendQuality
}
$results["Tracked-file secret scan"] = Invoke-SecretScan

Write-Host ""
Write-Host "==================== Pre-release gate summary ====================" -ForegroundColor Cyan
$hasFailure = $false
foreach ($gate in $results.Keys) {
    if ($results[$gate]) {
        Write-Host ("  [PASS] {0}" -f $gate) -ForegroundColor Green
    }
    else {
        Write-Host ("  [FAIL] {0}" -f $gate) -ForegroundColor Red
        $hasFailure = $true
    }
}

if ($hasFailure) {
    Write-Host "`nPre-release gate failed; release is blocked." -ForegroundColor Red
    exit 1
}

Write-Host "`nAll pre-release gates passed." -ForegroundColor Green
exit 0
