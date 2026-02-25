@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

:: ============================================================
:: 全能创意大师 - 自动更新脚本 v1.0
:: 功能：检测更新、下载更新包、关闭服务、解压覆盖、重启程序
:: ============================================================

title 全能创意大师 - 自动更新

set "PROJECT_DIR=%~dp0"
set "TEMP_DIR=%PROJECT_DIR%temp_update"
set "VERSION_FILE=%PROJECT_DIR%version.json"
set "BACKUP_DIR=%PROJECT_DIR%backup_old"

echo.
echo ========================================================
echo     全能创意大师 - 自动更新程序
echo ========================================================
echo.

:: 检查 PowerShell 是否可用
powershell -Command "Get-Host" >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 PowerShell，无法执行自动更新
    echo 请确保 Windows 系统完整安装
    pause
    exit /b 1
)

:: 创建临时目录（提前创建，避免后续写入失败）
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

:: 读取本地版本
echo [步骤 1/6] 读取本地版本信息...
if not exist "%VERSION_FILE%" (
    echo [错误] 未找到 version.json 文件
    pause
    exit /b 1
)

:: 使用 PowerShell 读取 JSON（处理中文路径）
for /f "delims=" %%v in ('powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; $json.current_version"') do set LOCAL_VERSION=%%v

if "%LOCAL_VERSION%"=="" (
    echo [错误] 无法解析本地版本信息
    pause
    exit /b 1
)
echo 本地版本: %LOCAL_VERSION%

:: 获取远程版本信息
echo.
echo [步骤 2/6] 检查远程版本信息...

set "VERSION_URL=https://raw.githubusercontent.com/dragan2023/creative-master/main/version.json"
set "MIRROR_URL1=https://ghproxy.com/https://raw.githubusercontent.com/dragan2023/creative-master/main/version.json"
set "MIRROR_URL2=https://mirror.ghproxy.com/https://raw.githubusercontent.com/dragan2023/creative-master/main/version.json"

:: 尝试多个镜像源（国内加速）
echo 正在连接服务器...

set "REMOTE_VERSION_FILE=%TEMP_DIR%\remote_version.json"
set "DOWNLOAD_SUCCESS=0"

:: 设置 TLS 1.2（GitHub要求）
powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12" >nul 2>&1

:: 尝试镜像1
echo [尝试 1/3] 镜像源 ghproxy.com...
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $response = Invoke-WebRequest -Uri '%MIRROR_URL1%' -TimeoutSec 20 -UseBasicParsing; [System.IO.File]::WriteAllText('%REMOTE_VERSION_FILE%', $response.Content, [System.Text.Encoding]::UTF8); exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    set "DOWNLOAD_SUCCESS=1"
    echo [OK] 镜像源1连接成功
) else (
    echo [跳过] 镜像源1连接失败，尝试下一个...
)

:: 尝试镜像2
if "%DOWNLOAD_SUCCESS%"=="0" (
    echo [尝试 2/3] 镜像源 mirror.ghproxy.com...
    powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $response = Invoke-WebRequest -Uri '%MIRROR_URL2%' -TimeoutSec 20 -UseBasicParsing; [System.IO.File]::WriteAllText('%REMOTE_VERSION_FILE%', $response.Content, [System.Text.Encoding]::UTF8); exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "DOWNLOAD_SUCCESS=1"
        echo [OK] 镜像源2连接成功
    ) else (
        echo [跳过] 镜像源2连接失败，尝试下一个...
    )
)

:: 尝试直连
if "%DOWNLOAD_SUCCESS%"=="0" (
    echo [尝试 3/3] 直连 GitHub...
    powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $response = Invoke-WebRequest -Uri '%VERSION_URL%' -TimeoutSec 30 -UseBasicParsing; [System.IO.File]::WriteAllText('%REMOTE_VERSION_FILE%', $response.Content, [System.Text.Encoding]::UTF8); exit 0 } catch { exit 1 }" >nul 2>&1
    if not errorlevel 1 (
        set "DOWNLOAD_SUCCESS=1"
        echo [OK] 直连GitHub成功
    ) else (
        echo [失败] 直连GitHub也失败
    )
)

if "%DOWNLOAD_SUCCESS%"=="0" (
    echo.
    echo ========================================
    echo   [错误] 所有连接方式均失败
    echo ========================================
    echo.
    echo 可能原因：
    echo   1. 网络连接问题
    echo   2. 防火墙阻止了连接
    echo   3. GitHub 服务暂时不可用
    echo.
    echo 请检查网络连接后重试
    echo ========================================
    pause
    exit /b 1
)

echo [OK] 版本信息获取成功

:: 解析远程版本信息
for /f "delims=" %%v in ('powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%REMOTE_VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; $json.current_version"') do set REMOTE_VERSION=%%v
for /f "delims=" %%v in ('powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%REMOTE_VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; $json.download_url_mirror"') do set DOWNLOAD_URL=%%v
for /f "delims=" %%v in ('powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%REMOTE_VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; $json.file_size_mb"') do set FILE_SIZE_MB=%%v
for /f "delims=" %%v in ('powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%REMOTE_VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; $json.update_notes"') do set UPDATE_NOTES=%%v

echo 远程版本: %REMOTE_VERSION%
echo 文件大小: %FILE_SIZE_MB% MB

:: 比较版本号
echo.
echo [步骤 3/6] 比较版本...

call :CompareVersions %LOCAL_VERSION% %REMOTE_VERSION%

if !COMPARE_RESULT! LEQ 0 (
    echo.
    echo ========================================
    echo   当前已是最新版本！
    echo ========================================
    echo.
    pause
    exit /b 0
)

echo.
echo ========================================
echo   发现新版本: %REMOTE_VERSION%
echo ========================================
echo.
echo 更新说明:
:: 使用 PowerShell 直接显示更新说明（支持多行文本）
powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%REMOTE_VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; Write-Host $json.update_notes"
echo.

:: 询问是否更新
set /p CONFIRM="是否立即更新？(Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo 已取消更新
    pause
    exit /b 0
)

:: 关闭运行中的服务
echo.
echo [步骤 4/6] 关闭运行中的服务...

:: 关闭后端服务（uvicorn）
taskkill /f /im python.exe /fi "WINDOWTITLE eq 全能创意大师*" >nul 2>&1
taskkill /f /im uvicorn* >nul 2>&1

:: 关闭前端服务（node）
taskkill /f /im node.exe /fi "WINDOWTITLE eq 全能创意大师*" >nul 2>&1

:: 清理端口
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 "') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173 "') do taskkill /f /pid %%a >nul 2>&1

echo [OK] 服务已关闭

:: 下载更新包
echo.
echo [步骤 5/6] 下载更新包...

:: 如果镜像 URL 为空，使用直连 URL
if "%DOWNLOAD_URL%"=="" (
    for /f "delims=" %%v in ('powershell -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $json = Get-Content -Path '%REMOTE_VERSION_FILE%' -Encoding UTF8 | ConvertFrom-Json; $json.download_url"') do set DOWNLOAD_URL=%%v
)

echo 下载地址: %DOWNLOAD_URL%
echo.

:: 使用系统临时目录避免中文路径问题
set "SYSTEM_TEMP=%TEMP%"
set "UPDATE_ZIP=%SYSTEM_TEMP%\creative_master_update.zip"

:: 下载文件（使用系统临时目录，避免中文路径问题）
powershell -NoProfile -Command ^
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;" ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "$url = '%DOWNLOAD_URL%';" ^
    "$output = '%UPDATE_ZIP%';" ^
    "Write-Host '正在下载更新包...';" ^
    "try {" ^
    "    $client = New-Object System.Net.WebClient;" ^
    "    $client.DownloadFile($url, $output);" ^
    "    if (Test-Path $output) {" ^
    "        $size = (Get-Item $output).Length / 1MB;" ^
    "        Write-Host ('[OK] 下载完成，文件大小: {0:N2} MB' -f $size);" ^
    "        exit 0" ^
    "    } else {" ^
    "        Write-Host '[错误] 下载失败：文件不存在';" ^
    "        exit 1" ^
    "    }" ^
    "} catch {" ^
    "    Write-Host ('[错误] 下载失败: ' + $_.Exception.Message);" ^
    "    exit 1" ^
    "}"

if errorlevel 1 (
    echo [错误] 下载更新包失败
    echo 请检查网络连接后重试
    pause
    exit /b 1
)

:: 解压并覆盖文件
echo.
echo [步骤 6/6] 解压并更新文件...

:: 创建备份目录
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: 备份重要文件（数据库、配置）
echo 正在备份重要文件...
if exist "%PROJECT_DIR%backend\data\creative_master.db" (
    copy "%PROJECT_DIR%backend\data\creative_master.db" "%BACKUP_DIR%\" >nul 2>&1
)
if exist "%PROJECT_DIR%backend\.env" (
    copy "%PROJECT_DIR%backend\.env" "%BACKUP_DIR%\" >nul 2>&1
)
if exist "%PROJECT_DIR%frontend\.env.local" (
    copy "%PROJECT_DIR%frontend\.env.local" "%BACKUP_DIR%\" >nul 2>&1
)

:: 解压更新包
echo 正在解压更新包...
set "EXTRACT_DIR=%SYSTEM_TEMP%\creative_master_extract"
powershell -NoProfile -Command ^
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;" ^
    "if (Test-Path '%EXTRACT_DIR%') { Remove-Item -Path '%EXTRACT_DIR%' -Recurse -Force };" ^
    "Expand-Archive -Path '%UPDATE_ZIP%' -DestinationPath '%EXTRACT_DIR%' -Force;" ^
    "if (Test-Path '%EXTRACT_DIR%') { exit 0 } else { exit 1 }"

if errorlevel 1 (
    echo [错误] 解压失败
    pause
    exit /b 1
)

:: 查找解压后的实际目录（可能是 creative-master-v1.1.0 这样的名称）
for /d %%d in ("%EXTRACT_DIR%\*") do set "EXTRACTED_DIR=%%d"
if not defined EXTRACTED_DIR set "EXTRACTED_DIR=%EXTRACT_DIR%"

:: 复制文件（排除数据目录和配置文件）
echo 正在更新文件...
powershell -NoProfile -Command ^
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;" ^
    "$source = '%EXTRACTED_DIR%';" ^
    "$dest = '%PROJECT_DIR%';" ^
    "$exclude = @('backend\data', 'backend\.env', 'frontend\.env.local', 'temp_update', 'backup_old', '自动更新.bat');" ^
    "Get-ChildItem -Path $source -Recurse | Where-Object {" ^
    "    $relativePath = $_.FullName.Substring($source.Length + 1);" ^
    "    $shouldExclude = $false;" ^
    "    foreach ($ex in $exclude) {" ^
    "        if ($relativePath -like \"$ex*\") { $shouldExclude = $true; break }" ^
    "    };" ^
    "    -not $shouldExclude" ^
    "} | ForEach-Object {" ^
    "    $relativePath = $_.FullName.Substring($source.Length + 1);" ^
    "    $targetPath = Join-Path $dest $relativePath;" ^
    "    if ($_.PSIsContainer) {" ^
    "        if (-not (Test-Path $targetPath)) { New-Item -ItemType Directory -Path $targetPath -Force | Out-Null }" ^
    "    } else {" ^
    "        $targetDir = Split-Path $targetPath -Parent;" ^
    "        if (-not (Test-Path $targetDir)) { New-Item -ItemType Directory -Path $targetDir -Force | Out-Null };" ^
    "        Copy-Item $_.FullName -Destination $targetPath -Force" ^
    "    }" ^
    "}; " ^
    "Write-Host '[OK] 文件更新完成'"

:: 恢复配置文件
if exist "%BACKUP_DIR%\.env" (
    copy "%BACKUP_DIR%\.env" "%PROJECT_DIR%backend\.env" >nul 2>&1
)
if exist "%BACKUP_DIR%\.env.local" (
    copy "%BACKUP_DIR%\.env.local" "%PROJECT_DIR%frontend\.env.local" >nul 2>&1
)

:: 清理临时文件
echo 正在清理临时文件...
if exist "%UPDATE_ZIP%" del "%UPDATE_ZIP%" 2>nul
if exist "%EXTRACT_DIR%" rd /s /q "%EXTRACT_DIR%" 2>nul
if exist "%TEMP_DIR%" rd /s /q "%TEMP_DIR%" 2>nul

:: 完成
echo.
echo ========================================================
echo   更新完成！
echo ========================================================
echo.
echo 版本已更新至: %REMOTE_VERSION%
echo.
echo 按任意键启动程序...
pause >nul

:: 启动程序
start "" "%PROJECT_DIR%start.bat"
exit /b 0

:: ============================================================
:: 版本比较函数
:: 参数1: 版本1
:: 参数2: 版本2
:: 返回: COMPARE_RESULT (1=版本1大, -1=版本2大, 0=相等)
:: ============================================================
:CompareVersions
set "V1=%~1"
set "V2=%~2"
set "COMPARE_RESULT=0"

:: 解析版本号
for /f "tokens=1,2,3 delims=." %%a in ("%V1%") do (
    set V1_MAJOR=%%a
    set V1_MINOR=%%b
    set V1_PATCH=%%c
)
for /f "tokens=1,2,3 delims=." %%a in ("%V2%") do (
    set V2_MAJOR=%%a
    set V2_MINOR=%%b
    set V2_PATCH=%%c
)

:: 默认值为0
if not defined V1_MAJOR set V1_MAJOR=0
if not defined V1_MINOR set V1_MINOR=0
if not defined V1_PATCH set V1_PATCH=0
if not defined V2_MAJOR set V2_MAJOR=0
if not defined V2_MINOR set V2_MINOR=0
if not defined V2_PATCH set V2_PATCH=0

:: 比较
if !V1_MAJOR! GTR !V2_MAJOR! (
    set "COMPARE_RESULT=1"
    goto :eof
)
if !V1_MAJOR! LSS !V2_MAJOR! (
    set "COMPARE_RESULT=-1"
    goto :eof
)
if !V1_MINOR! GTR !V2_MINOR! (
    set "COMPARE_RESULT=1"
    goto :eof
)
if !V1_MINOR! LSS !V2_MINOR! (
    set "COMPARE_RESULT=-1"
    goto :eof
)
if !V1_PATCH! GTR !V2_PATCH! (
    set "COMPARE_RESULT=1"
    goto :eof
)
if !V1_PATCH! LSS !V2_PATCH! (
    set "COMPARE_RESULT=-1"
    goto :eof
)

goto :eof
