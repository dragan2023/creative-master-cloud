# backend/Dockerfile
FROM python:3.10-slim

# 设置工作目录（可通过环境变量覆盖，但默认推荐 /app）
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 创建并激活虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建默认数据目录（可通过挂载卷覆盖）
RUN mkdir -p /app/logs /app/data/chroma /app/data/uploads /app/data/knowledge_graphs

# 暴露端口（可通过环境变量 PORT 覆盖）
EXPOSE 8000

# 启动命令（从环境变量读取配置）
# 使用环境变量 HOST 和 PORT，默认值为 0.0.0.0:8000
CMD uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}
