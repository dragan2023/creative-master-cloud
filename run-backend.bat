@echo off
REM 后端服务启动脚本
cd /d "%~dp0backend"
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
