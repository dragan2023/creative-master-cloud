#!/bin/bash
set -e

echo "=== 全能创意大师开发环境启动 ==="

# 等待数据库就绪
if [ -n "$DATABASE_URL" ]; then
    echo "[1/3] 等待数据库连接..."
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    
    if [ -n "$DB_HOST" ] && [ -n "$DB_PORT" ]; then
        echo "      检测数据库: $DB_HOST:$DB_PORT"
        max_retries=30
        retry_count=0
        while ! nc -z $DB_HOST $DB_PORT 2>/dev/null; do
            retry_count=$((retry_count + 1))
            if [ $retry_count -ge $max_retries ]; then
                echo "      [WARNING] 数据库连接超时，继续启动..."
                break
            fi
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
fi

echo "[3/3] 开发环境就绪"
echo "=========================================="

# 开发模式：执行传入的命令，如果没有命令则保持运行
if [ $# -gt 0 ]; then
    exec "$@"
else
    # 保持容器运行（开发模式）
    echo "容器已就绪，等待命令..."
    exec tail -f /dev/null
fi
