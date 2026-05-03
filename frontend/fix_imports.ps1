$filePath = "f:\python_project\全能创意大师（开发版）\frontend\src\views\novel-writer\WritingWorkbench.vue"
$lines = Get-Content -Path $filePath
$result = [System.Collections.ArrayList]@()
$skipCount = 0
foreach ($line in $lines) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "Connection," -or $trimmed -eq "Loading," -or $trimmed -eq "Download," -or $trimmed -eq "DataAnalysis,") {
        $skipCount++
        continue
    }
    [void]$result.Add($line)
}
Set-Content -Path $filePath -Value $result
Write-Host "Removed $skipCount lines, kept $($result.Count) lines"
$filePath = "f:\python_project\全能创意大师（开发版）\frontend\src\views\novel-writer\WritingWorkbench.vue"
$lines = Get-Content $filePath
$skipPatterns = @("  Connection,", "  Loading,", "  Download,", "  DataAnalysis,")
$result = @()
foreach ($line in $lines) {
    $trimmed = $line.TrimStart()
    $shouldSkip = $false
    foreach ($pattern in $skipPatterns) {
        if ($trimmed -eq $pattern.Trim()) {
            $shouldSkip = $true
            break
        }
    }
    if (-not $shouldSkip) {
        $result += $line
    }
}
Set-Content $filePath $result
Write-Host "Done: $($result.Count) lines"
$filePath = "f:\python_project\全能创意大师（开发版）\frontend\src\views\novel-writer\WritingWorkbench.vue"
$content = Get-Content $filePath -Raw
$content = $content -replace '  Connection,\r\n  Loading,\r\n  List,\r\n  Download,\r\n  Setting,\r\n  Upload,\r\n  DataAnalysis,', '  List,
  Setting,
  Upload,'
Set-Content $filePath $content -NoNewline
Write-Host "Done"
