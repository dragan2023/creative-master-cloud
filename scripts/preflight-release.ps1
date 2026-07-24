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

function Invoke-ConstraintCheck {
    Write-Gate "Dependency constraint consistency"
    $backendDir = Join-Path $ProjectRoot "backend"
    $constraints = Join-Path $backendDir "constraints.txt"
    $requirements = Join-Path $backendDir "requirements.txt"

    if (-not (Test-Path $constraints)) {
        Write-Host "constraints.txt not found; gate cannot verify reproducibility." -ForegroundColor Red
        return $false
    }

    # Validate constraints.txt syntax: each line must be blank/comment/valid pep508 constraint
    $lines = Get-Content -LiteralPath $constraints -Encoding utf8 | Where-Object { $_ -notmatch '^\s*$' -and $_ -notmatch '^\s*#' }
    $invalid = @()
    foreach ($line in $lines) {
        if ($line -notmatch '^[A-Za-z0-9_\-\.]+[<>=!~]+[0-9]') {
            $invalid += $line
        }
    }
    if ($invalid.Count -gt 0) {
        Write-Host "Invalid constraint lines in constraints.txt:" -ForegroundColor Red
        foreach ($l in $invalid) { Write-Host "  $l" -ForegroundColor Red }
        return $false
    }

    # Check that all packages in requirements.txt have corresponding constraints
    $reqLines = Get-Content -LiteralPath $requirements -Encoding utf8 | Where-Object { $_ -notmatch '^\s*$' -and $_ -notmatch '^\s*#' }
    $constraintNames = @{}
    foreach ($line in $lines) {
        if ($line -match '^([A-Za-z0-9_\-\.]+)') {
            $constraintNames[$Matches[1].ToLowerInvariant()] = $true
        }
    }

    $unconstrained = @()
    foreach ($line in $reqLines) {
        if ($line -match '^([A-Za-z0-9_\-\.]+)') {
            $pkg = $Matches[1].ToLowerInvariant()
            # Exempt test tools, build tools, and optional dependencies
            if ($pkg -match '^(pytest|torch|readability-lxml|beautifulsoup4|lxml|pysqlite3-binary)') { continue }
            if (-not $constraintNames.ContainsKey($pkg) -and $line -notmatch '\[.*\]') {
                $unconstrained += $line
            }
        }
    }
    if ($unconstrained.Count -gt 0) {
        Write-Host "Packages in requirements.txt without constraint in constraints.txt:" -ForegroundColor Yellow
        foreach ($l in $unconstrained) { Write-Host "  $l" -ForegroundColor Yellow }
        Write-Host "(Add constraints for production packages to ensure reproducible installs)" -ForegroundColor Yellow
        # Warning only, do not block release
    }

    Write-Host "Dependency constraints verified." -ForegroundColor Green
    return $true
}

function Invoke-FrontendBudget {
    Write-Gate "Frontend performance budget"
    $budgetScript = Join-Path $ScriptDir "check-frontend-budget.mjs"
    if (-not (Test-Path $budgetScript)) {
        Write-Host "Budget script not found; skipping." -ForegroundColor Yellow
        return $true
    }
    & node $budgetScript | Out-Host
    return ($LASTEXITCODE -eq 0)
}

function Invoke-AntiRegression {
    Write-Gate "Anti-regression checks"
    $failures = @()
    $backendApp = Join-Path $ProjectRoot "backend\app"

    # Check 1: No datetime.utcnow() in production code (allow doc comments in time.py only)
    $prevErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $utcnowMatches = Get-ChildItem -Path $backendApp -Recurse -Filter *.py -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne 'time.py' -or $_.Directory.Name -ne 'core' } |
        Select-String -Pattern 'datetime\.utcnow\(' -ErrorAction SilentlyContinue |
        Select-Object -First 20
    $ErrorActionPreference = $prevErrorAction
    if ($utcnowMatches) {
        $failures += "datetime.utcnow() found outside core/time.py doc comments"
        foreach ($m in $utcnowMatches) { Write-Host "  $($m.Path):$($m.LineNumber): $($m.Line.Trim())" -ForegroundColor Red }
    }

    # Check 2: No generation_task_ in services/api production code (allow doc comments only)
    $genTaskPaths = @(
        (Join-Path $ProjectRoot "backend\app\services"),
        (Join-Path $ProjectRoot "backend\app\api")
    )
    $genTaskMatches = Get-ChildItem -Path $genTaskPaths -Recurse -Filter *.py -ErrorAction SilentlyContinue |
        Select-String -Pattern 'generation_task_' -SimpleMatch |
        Where-Object { $_.Line -notmatch '替代已删除|字段|NovelProject\.generation_task' } |
        Select-Object -First 20
    if ($genTaskMatches) {
        $failures += "generation_task_ reference found in production code"
        foreach ($m in $genTaskMatches) { Write-Host "  $($m.Path):$($m.LineNumber): $($m.Line.Trim())" -ForegroundColor Red }
    }

    # Check 3: No test source files are gitignored (warn only for untracked)
    $testFiles = & git -C $ProjectRoot ls-files --others --exclude-standard 'backend/tests/**' 'frontend/tests/**' 'tests/**' 2>$null
    if ($testFiles) {
        Write-Host "  (info) Untracked test files (ensure they are committed before release):" -ForegroundColor Yellow
        foreach ($f in $testFiles) { Write-Host "    $f" -ForegroundColor Yellow }
        # Warning only: untracked test files are new additions, not hidden by gitignore
    }

    if ($failures.Count -eq 0) {
        Write-Host "Anti-regression checks: clean." -ForegroundColor Green
        return $true
    }
    Write-Host ("Anti-regression failures: {0}" -f $failures.Count) -ForegroundColor Red
    return $false
}

function Invoke-FrontendQuality {
    Write-Gate "Frontend quality build"
    Push-Location (Join-Path $ProjectRoot "frontend")
    try {
        & npm.cmd run check:toolchain | Out-Host
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
$results["Dependency constraint check"] = Invoke-ConstraintCheck
$results["Backend tests"] = Invoke-BackendTests
$results["Backend syntax compilation"] = Invoke-BackendCompile
$results["Anti-regression checks"] = Invoke-AntiRegression
if ($SkipFrontend) {
    Write-Host "`nFrontend quality gate skipped." -ForegroundColor Yellow
}
else {
    $results["Frontend quality build"] = Invoke-FrontendQuality
    $results["Frontend performance budget"] = Invoke-FrontendBudget
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
