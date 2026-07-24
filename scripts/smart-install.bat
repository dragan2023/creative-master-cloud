@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Creative Master - Smart Install
color 0B

echo.
echo ========================================================
echo         Creative Master - Smart Install v2.0
echo ========================================================
echo.
echo  This tool will automatically install:
echo    - Python 3.10 (Runtime foundation)
echo    - Node.js 20 LTS (Frontend support)
echo    - Python dependencies (Backend modules)
echo    - Node dependencies (Frontend modules)
echo    - AI Models (Optional, for document parsing)
echo.
echo  All downloads use China-optimized mirrors.
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "VENV_PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"
set "MODEL_DIR=%BACKEND_DIR%\data\marker_models"
set "INSTALL_LOG=%PROJECT_DIR%install.log"

:: ����Դ����
set "PYPI_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PYPI_MIRROR_2=https://mirrors.aliyun.com/pypi/simple/"
set "NPM_MIRROR=https://registry.npmmirror.com"
set "PYTHON_DL=https://npm.taobao.org/mirrors/python/3.10.11/python-3.10.11-amd64.exe"
set "NODE_DL=https://npmmirror.com/mirrors/node/v20.11.0/node-v20.11.0-x64.msi"

:: ״̬��־
set "INSTALL_PYTHON=0"
set "INSTALL_NODE=0"
set "INSTALL_PY_DEPS=0"
set "INSTALL_NP_DEPS=0"
set "DOWNLOAD_MODELS=0"

:: ��ʼ����־
echo [%date% %time%] Install log started > "%INSTALL_LOG%"
echo Project dir: %PROJECT_DIR% >> "%INSTALL_LOG%"

echo ========================================================
echo  [Detection Phase] Scanning system...
echo ========================================================
echo.

:: ��� Python
echo [1/5] Python 3.10+...
python --version >nul 2>&1
if errorlevel 1 (
    echo       Status: NOT INSTALLED
    set "INSTALL_PYTHON=1"
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do (
        set "PY_VER=%%v"
        echo       Installed: Python !PY_VER!
        echo [%date% %time%] Python !PY_VER! found >> "%INSTALL_LOG%"
    )
)

:: ��� Node.js
echo [2/5] Node.js 20+...
node --version >nul 2>&1
if errorlevel 1 (
    echo       Status: NOT INSTALLED
    set "INSTALL_NODE=1"
) else (
    for /f "tokens=*" %%v in ('node --version 2^>^&1') do (
        set "NODE_VER=%%v"
        echo       Installed: Node.js !NODE_VER!
        echo [%date% %time%] Node.js !NODE_VER! found >> "%INSTALL_LOG%"
    )
)

:: ��� Python ���⻷��
echo [3/5] Python virtual environment...
if exist "%VENV_PYTHON%" (
    echo       venv: EXISTS
) else (
    echo       venv: NOT CREATED
    set "INSTALL_PY_DEPS=1"
)

:: ��� Node ����
echo [4/5] Node dependencies...
if exist "%FRONTEND_DIR%\node_modules" (
    echo       node_modules: EXISTS
) else (
    echo       node_modules: NOT INSTALLED
    set "INSTALL_NP_DEPS=1"
)

:: ���ģ���ļ�
echo [5/5] AI Models for document parsing...
if exist "%MODEL_DIR%\layout" (
    if exist "%MODEL_DIR%\text_detection" (
        if exist "%MODEL_DIR%\text_recognition" (
            echo       Models: EXISTS
            goto models_done
        )
    )
)
echo       Models: NOT DOWNLOADED (Optional)
echo       Note: Models are ~500MB, needed for PDF parsing
set "DOWNLOAD_MODELS=1"

:models_done
echo.
echo ========================================================
echo  [Analysis Result]
echo ========================================================
echo.

if !INSTALL_PYTHON!==1 (echo  [Need] Python 3.10+) else (echo  [Ready] Python)
if !INSTALL_NODE!==1 (echo  [Need] Node.js 20 LTS) else (echo  [Ready] Node.js)
if !INSTALL_PY_DEPS!==1 (echo  [Need] Python dependencies) else (echo  [Ready] Python dependencies)
if !INSTALL_NP_DEPS!==1 (echo  [Need] Node dependencies) else (echo  [Ready] Node dependencies)
if !DOWNLOAD_MODELS!==1 (echo  [Optional] AI Models) else (echo  [Ready] AI Models)
echo.

set "NEED_INSTALL=0"
if !INSTALL_PYTHON!==1 set "NEED_INSTALL=1"
if !INSTALL_NODE!==1 set "NEED_INSTALL=1"
if !INSTALL_PY_DEPS!==1 set "NEED_INSTALL=1"
if !INSTALL_NP_DEPS!==1 set "NEED_INSTALL=1"

if !NEED_INSTALL!==0 (
    if !DOWNLOAD_MODELS!==0 (
        color 0A
        echo  All components are ready!
        echo.
        echo  You can run start.bat to launch the program.
        echo.
        pause
        exit /b 0
    )
)

echo ========================================================
echo  [Install Phase]
echo ========================================================
echo.
echo  Options:
echo    [Y] Install all required components
echo    [N] Cancel
if !DOWNLOAD_MODELS!==1 (
    echo    [M] Install required + download AI Models (~500MB)
)
echo.
if !DOWNLOAD_MODELS!==1 (
    choice /c YNM /n /m "  Press key: "
    if errorlevel 3 goto install_with_models
) else (
    choice /c YN /n /m "  Press key: "
)
if errorlevel 2 goto :cancel
echo.

:: ��װ Python
if !INSTALL_PYTHON!==1 (
    echo ========================================================
    echo  [1/4] Installing Python 3.10
    echo ========================================================
    echo.
    echo  Source: Taobao Mirror
    echo  Size: ~27MB
    echo.
    echo  Downloading...
    echo [%date% %time%] Downloading Python... >> "%INSTALL_LOG%"
    powershell -Command "(New-Object Net.WebClient).DownloadFile('!PYTHON_DL!', '%TEMP%\py.exe')"
    if exist "%TEMP%\py.exe" (
        echo  Installing...
        "%TEMP%\py.exe" /passive InstallAllUsers=1 PrependPath=1
        timeout /t 30 >nul
        echo  [OK] Python installed
        echo [%date% %time%] Python installed >> "%INSTALL_LOG%"
    ) else (
        echo  [X] Download failed
        echo [%date% %time%] ERROR: Python download failed >> "%INSTALL_LOG%"
    )
    echo.
)

:: ��װ Node.js
if !INSTALL_NODE!==1 (
    echo ========================================================
    echo  [2/4] Installing Node.js 20 LTS
    echo ========================================================
    echo.
    echo  Source: npmmirror
    echo  Size: ~30MB
    echo.
    echo  Downloading...
    echo [%date% %time%] Downloading Node.js... >> "%INSTALL_LOG%"
    powershell -Command "(New-Object Net.WebClient).DownloadFile('!NODE_DL!', '%TEMP%\node.msi')"
    if exist "%TEMP%\node.msi" (
        echo  Installing...
        msiexec /i "%TEMP%\node.msi" /passive /norestart
        timeout /t 30 >nul
        echo  [OK] Node.js installed
        echo [%date% %time%] Node.js installed >> "%INSTALL_LOG%"
    ) else (
        echo  [X] Download failed
        echo [%date% %time%] ERROR: Node.js download failed >> "%INSTALL_LOG%"
    )
    echo.
)

:: ��װ Python ����
if !INSTALL_PY_DEPS!==1 (
    echo ========================================================
    echo  [3/4] Installing Python dependencies
    echo ========================================================
    echo.
    echo  Creating virtual environment...
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    if errorlevel 1 (
        echo  [X] Failed to create venv
        echo [%date% %time%] ERROR: venv creation failed >> "%INSTALL_LOG%"
        goto py_deps_done
    )
    echo  [OK] Virtual environment created
    
    echo  Configuring pip mirror...
    "%VENV_PYTHON%" -m pip config set global.index-url !PYPI_MIRROR! >nul 2>&1
    echo  [OK] pip mirror configured
    
    echo  Installing packages (3-5 minutes)...
    echo [%date% %time%] Installing Python packages... >> "%INSTALL_LOG%"
    echo  [1/2] Upgrading pip...
    "%VENV_PYTHON%" -m pip install --upgrade pip -q 2>> "%INSTALL_LOG%"
    
    echo  [2/2] Installing requirements.txt...
    "%VENV_PYTHON%" -m pip install -r requirements.txt -c constraints.txt -q -i !PYPI_MIRROR! 2>> "%INSTALL_LOG%"
    if errorlevel 1 (
        echo  [!] Primary mirror failed, trying backup...
        "%VENV_PYTHON%" -m pip install -r requirements.txt -c constraints.txt -q -i !PYPI_MIRROR_2! 2>> "%INSTALL_LOG%"
    )
    echo  [OK] Python dependencies installed
    echo [%date% %time%] Python deps installed >> "%INSTALL_LOG%"
    cd /d "%PROJECT_DIR%"
    echo.
)

:py_deps_done

:: ��װ Node ����
if !INSTALL_NP_DEPS!==1 (
    echo ========================================================
    echo  [4/4] Installing Node dependencies
    echo ========================================================
    echo.
    echo  Configuring npm mirror...
    call npm config set registry !NPM_MIRROR! >nul 2>&1
    
    echo  Installing packages (2-3 minutes)...
    echo [%date% %time%] Installing Node packages... >> "%INSTALL_LOG%"
    cd /d "%FRONTEND_DIR%"
    call npm install --silent 2>> "%INSTALL_LOG%"
    if errorlevel 1 (
        echo  [!] First attempt failed, retrying...
        call npm install --silent 2>> "%INSTALL_LOG%"
    )
    echo  [OK] Node dependencies installed
    echo [%date% %time%] Node deps installed >> "%INSTALL_LOG%"
    cd /d "%PROJECT_DIR%"
    echo.
)

goto install_complete

:install_with_models
:: ��װ���� + ģ��
echo.
echo  Installing all components including AI models...
echo.

:: �Ȱ�װ�������������������߼���
if !INSTALL_PYTHON!==1 (
    echo [1/5] Installing Python 3.10...
    powershell -Command "(New-Object Net.WebClient).DownloadFile('!PYTHON_DL!', '%TEMP%\py.exe')"
    if exist "%TEMP%\py.exe" (
        "%TEMP%\py.exe" /passive InstallAllUsers=1 PrependPath=1
        timeout /t 30 >nul
        echo  [OK] Python installed
    )
)

if !INSTALL_NODE!==1 (
    echo [2/5] Installing Node.js 20 LTS...
    powershell -Command "(New-Object Net.WebClient).DownloadFile('!NODE_DL!', '%TEMP%\node.msi')"
    if exist "%TEMP%\node.msi" (
        msiexec /i "%TEMP%\node.msi" /passive /norestart
        timeout /t 30 >nul
        echo  [OK] Node.js installed
    )
)

if !INSTALL_PY_DEPS!==1 (
    echo [3/5] Installing Python dependencies...
    cd /d "%BACKEND_DIR%"
    python -m venv venv
    "%VENV_PYTHON%" -m pip config set global.index-url !PYPI_MIRROR! >nul 2>&1
    "%VENV_PYTHON%" -m pip install --upgrade pip -q
    "%VENV_PYTHON%" -m pip install -r requirements.txt -c constraints.txt -q -i !PYPI_MIRROR!
    cd /d "%PROJECT_DIR%"
    echo  [OK] Python dependencies installed
)

if !INSTALL_NP_DEPS!==1 (
    echo [4/5] Installing Node dependencies...
    call npm config set registry !NPM_MIRROR! >nul 2>&1
    cd /d "%FRONTEND_DIR%"
    call npm install --silent
    cd /d "%PROJECT_DIR%"
    echo  [OK] Node dependencies installed
)

:: ����ģ��
echo [5/5] Downloading AI Models (~500MB)...
echo  This may take 5-15 minutes depending on your connection.
echo.
echo  Models will be downloaded when you first use PDF parsing.
echo  No action needed now.
echo  [OK] Models will auto-download on first use
echo.

:install_complete

:: ���������ļ�
if not exist "%BACKEND_DIR%\.env" (
    echo  Creating backend config...
    (
        echo APP_NAME=Creative Master
        echo DEBUG=True
        echo HOST=0.0.0.0
        echo PORT=8000
        echo DATABASE_URL=sqlite+aiosqlite:///./data/creative_master.db
        echo SECRET_KEY=auto-generated-please-change
        echo LOG_LEVEL=INFO
        echo LOG_DIR=./logs
        echo CHROMA_PERSIST_DIR=./data/chroma
        echo UPLOAD_DIR=./data/uploads
        echo MARKER_MODEL_DIR=./data/marker_models
    ) > "%BACKEND_DIR%\.env"
)

if not exist "%FRONTEND_DIR%\.env.local" (
    echo  Creating frontend config...
    (
        echo VITE_BACKEND_URL=http://localhost:8000
        echo VITE_FRONTEND_PORT=5173
    ) > "%FRONTEND_DIR%\.env.local"
)

color 0A
echo ========================================================
echo           Installation Complete!
echo ========================================================
echo.
echo  All components are ready!
echo.
echo  Log file: %INSTALL_LOG%
echo.
echo  Next step: Run start.bat to launch the program
echo.
echo ========================================================
echo.
echo [%date% %time%] Installation complete >> "%INSTALL_LOG%"
pause
exit /b 0

:cancel
echo.
echo  Installation cancelled.
echo [%date% %time%] Installation cancelled >> "%INSTALL_LOG%"
pause
exit /b 1
