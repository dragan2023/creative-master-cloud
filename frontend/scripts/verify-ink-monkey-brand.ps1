$ErrorActionPreference = 'Stop'

$frontendRoot = Split-Path -Parent $PSScriptRoot
$layoutPath = Join-Path $frontendRoot 'src\layouts\MainLayout.vue'
$homePath = Join-Path $frontendRoot 'src\views\home\Index.vue'
$logoAsset = Join-Path $frontendRoot 'public\brand\ink-monkey-logo.png'
$bannerAsset = Join-Path $frontendRoot 'public\brand\ink-monkey-banner.png'

$layout = Get-Content -Raw $layoutPath
$homeSource = Get-Content -Raw $homePath

if (-not (Test-Path -LiteralPath $logoAsset)) {
  throw 'Missing ink-monkey sidebar logo asset.'
}

if (-not (Test-Path -LiteralPath $bannerAsset)) {
  throw 'Missing ink-monkey homepage banner asset.'
}

if ($layout -notmatch '/brand/ink-monkey-logo\.png') {
  throw 'Sidebar does not reference the ink-monkey logo.'
}

if ($homeSource -notmatch '/brand/ink-monkey-banner\.png') {
  throw 'Homepage does not reference the ink-monkey banner.'
}

if ($homeSource -notmatch 'welcome-kicker') {
  throw 'Homepage is missing the approved editorial kicker.'
}

if ($homeSource -match 'welcome-illustration') {
  throw 'Legacy welcome illustration markup or styling is still present.'
}

Write-Output 'Ink-monkey brand static checks passed.'
