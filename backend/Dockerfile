# backend/Dockerfile
# ========================================
# 全能创意大师 - 后端服务 Docker 镜像
#
# 【开发环境镜像】
# 此镜像用于 Docker 热更新开发模式
# 配合 docker-compose.dev.hot.yml 使用
# ========================================

# 使用阿里云镜像加速
FROM python:3.10-slim

# 设置工作目录（可通过环境变量覆盖，但默认推荐 /app）
WORKDIR /app

# 配置 Debian 清华镜像源（加速 apt 下载）
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq5 \
    curl \
    netcat-openbsd \
    locales \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置中文语言环境
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# 创建并激活虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 配置 pip 清华镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用清华源）
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 复制并设置启动脚本（开发和生产两个版本）
COPY docker-entrypoint.sh /usr/local/bin/
COPY docker-entrypoint.dev.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.dev.sh

# 创建默认数据目录（可通过挂载卷覆盖）
RUN mkdir -p /app/logs /app/data/chroma/models /app/data/uploads /app/data/knowledge_graphs

# 预下载 sentence-transformers 模型（避免运行时下载）
# 设置模型缓存目录环境变量
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/chroma/models
ENV CHROMA_MODEL_CACHE_DIR=/app/data/chroma/models
ENV HF_ENDPOINT=https://hf-mirror.com

# 预下载模型（在构建阶段完成，避免运行时下载超时）
RUN python -c "from sentence_transformers import SentenceTransformer; print('预下载模型...'); SentenceTransformer('all-MiniLM-L6-v2', cache_folder='/app/data/chroma/models'); print('模型下载完成')"

# 暴露端口（可通过环境变量 PORT 覆盖）
EXPOSE 8000

# 使用 entrypoint 脚本
ENTRYPOINT ["docker-entrypoint.sh"]

# 启动命令（从环境变量读取配置）
# 使用环境变量 HOST 和 PORT，默认值为 0.0.0.0:8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
