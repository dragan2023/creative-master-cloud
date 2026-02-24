#!/bin/bash
# 本地开发启动脚本

# 进入 backend 目录
cd "$(dirname "$0")/backend"

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python -m venv venv
fi

# 激活虚拟环境
if [ -f "venv/Scripts/activate" ]; then
    # Windows Git Bash
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    # Linux/Mac
    source venv/bin/activate
fi

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt

# 复制环境变量文件
if [ ! -f "../.env" ]; then
    echo "创建 .env 文件..."
    cp ../.env.example ../.env
    echo "请编辑 .env 文件配置你的 API Key"
fi

# 启动服务
echo "启动服务..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
