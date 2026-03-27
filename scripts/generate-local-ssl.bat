@echo off
chcp 65001 >nul
REM ========================================
REM 全能创意大师 - 本地自签名SSL证书生成
REM 用于模拟HTTPS环境
REM ========================================

set SSL_DIR=nginx\ssl
set CERT_FILE=%SSL_DIR%\localhost.crt
set KEY_FILE=%SSL_DIR%\localhost.key

echo.
echo ========================================
echo   生成本地开发SSL证书
echo ========================================
echo.

REM 创建SSL目录
if not exist "%SSL_DIR%" mkdir "%SSL_DIR%"

REM 检查证书是否已存在
if exist "%CERT_FILE%" (
    if exist "%KEY_FILE%" (
        echo [警告] SSL证书已存在
        set /p CONFIRM="是否重新生成? (y/n): "
        if /i not "%CONFIRM%"=="y" (
            echo [信息] 使用现有证书
            goto :end
        )
    )
)

REM 检查OpenSSL
where openssl >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到OpenSSL
    echo.
    echo 请安装OpenSSL:
    echo   1. 下载: https://slproweb.com/products/Win32OpenSSL.html
    echo   2. 或使用Git Bash运行: bash scripts/generate-local-ssl.sh
    echo.
    pause
    exit /b 1
)

echo [信息] 生成自签名SSL证书...

openssl req -x509 -nodes -days 365 -newkey rsa:2048 ^
    -keyout "%KEY_FILE%" ^
    -out "%CERT_FILE%" ^
    -subj "/C=CN/ST=Shanghai/L=Shanghai/O=Development/OU=Local/CN=localhost" ^
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1" 2>nul

if errorlevel 1 (
    echo [错误] 证书生成失败
    echo [提示] 请使用Git Bash运行: bash scripts/generate-local-ssl.sh
    pause
    exit /b 1
)

echo.
echo [成功] SSL证书生成完成!
echo.
echo 证书文件: %CERT_FILE%
echo 私钥文件: %KEY_FILE%
echo.
echo ========================================
echo   Windows信任证书步骤:
echo ========================================
echo 1. 双击 %CERT_FILE%
echo 2. 点击 "安装证书"
echo 3. 选择 "本地计算机" ^> "将所有的证书都放入下列存储"
echo 4. 选择 "受信任的根证书颁发机构"
echo 5. 完成安装后重启浏览器
echo.

:end
pause
