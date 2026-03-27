#!/bin/bash
set -e

echo "=== 全能创意大师启动脚本 ==="

# 设置模型缓存目录环境变量（确保与 Dockerfile 一致）
export SENTENCE_TRANSFORMERS_HOME=/app/data/chroma/models
export CHROMA_MODEL_CACHE_DIR=/app/data/chroma/models
export HF_ENDPOINT=${HF_ENDPOINT:-https://hf-mirror.com}
echo "[0/3] 模型缓存目录: $CHROMA_MODEL_CACHE_DIR"

# 等待数据库就绪
if [ -n "$DATABASE_URL" ]; then
    echo "[1/3] 等待数据库连接..."
    # 提取数据库主机和端口（兼容多种 URL 格式）
    # 格式: postgresql+asyncpg://user:pass@host:port/database
    DB_HOST=$(echo $DATABASE_URL | grep -oP '(?<=@)[^:]+' | head -1)
    DB_PORT=$(echo $DATABASE_URL | grep -oP '(?<=:)[0-9]+(?=/)' | head -1)
    
    # 如果 grep -P 不支持（Alpine），使用 sed 备用方案
    if [ -z "$DB_HOST" ]; then
        DB_HOST=$(echo $DATABASE_URL | sed 's/.*@\([^:]*\):.*/\1/')
    fi
    if [ -z "$DB_PORT" ]; then
        DB_PORT=$(echo $DATABASE_URL | sed 's/.*:\([0-9]*\)\/.*/\1/')
    fi
    
    # 默认端口
    DB_PORT=${DB_PORT:-5432}
    
    if [ -n "$DB_HOST" ]; then
        echo "      检测数据库: $DB_HOST:$DB_PORT"
        max_retries=30
        retry_count=0
        while ! nc -z $DB_HOST $DB_PORT 2>/dev/null; do
            retry_count=$((retry_count + 1))
            if [ $retry_count -ge $max_retries ]; then
                echo "      [WARNING] 数据库连接超时，继续启动..."
                break
            fi
            echo "      等待数据库... ($retry_count/$max_retries)"
            sleep 1
        done
        if [ $retry_count -lt $max_retries ]; then
            echo "      [OK] 数据库已就绪"
        fi
    fi
fi

# 执行数据库迁移
echo "[2/3] 执行数据库迁移..."
cd /app
if [ -f "alembic.ini" ]; then
    /opt/venv/bin/alembic upgrade head 2>&1 || {
        echo "      [WARNING] 数据库迁移失败，可能已迁移或表已存在"
    }
    echo "      [OK] 数据库迁移完成"
else
    echo "      [SKIP] 未找到alembic配置"
fi

# 启动应用
echo "[3/3] 启动应用服务..."
echo "=========================================="

exec "$@"
