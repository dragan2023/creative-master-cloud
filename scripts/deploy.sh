#!/bin/bash
# ========================================
# 全能创意大师 - 云端部署脚本
# ========================================

set -e

echo "========================================"
echo "全能创意大师 - 云端部署"
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查.env文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: .env 文件不存在${NC}"
    echo "正在从模板创建 .env 文件..."
    cp .env.cloud .env
    echo -e "${RED}请编辑 .env 文件，设置 SECRET_KEY！${NC}"
    echo "生成密钥命令: python -c \"import secrets; print(secrets.token_hex(32))\""
    exit 1
fi

# 创建必要目录
echo "创建必要目录..."
mkdir -p backend/logs
mkdir -p backend/data/chroma/models
mkdir -p backend/data/uploads
mkdir -p backend/data/knowledge_graphs

# 设置权限
echo "设置目录权限..."
chmod -R 777 backend/logs
chmod -R 777 backend/data

# 检查模型文件
MODEL_DIR="backend/data/chroma/models/models--sentence-transformers--all-MiniLM-L6-v2"
if [ ! -d "$MODEL_DIR" ]; then
    echo -e "${YELLOW}警告: 嵌入模型未找到${NC}"
    echo "请运行以下命令下载模型："
    echo "  bash scripts/download-model.sh"
fi

# 构建并启动服务
echo "构建Docker镜像..."
docker compose -f docker-compose.prod.yml build

echo "启动服务..."
docker compose -f docker-compose.prod.yml up -d

# 等待服务启动
echo "等待服务启动..."
sleep 30

# 检查服务状态
echo "检查服务状态..."
docker compose -f docker-compose.prod.yml ps

# 运行数据库迁移
echo "运行数据库迁移..."
docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

echo ""
echo -e "${GREEN}========================================"
echo "部署完成！"
echo "========================================${NC}"
echo ""
echo "访问地址: http://$(curl -s ifconfig.me)"
echo "API文档: http://$(curl -s ifconfig.me)/docs"
echo ""
echo "常用命令:"
echo "  查看日志: docker compose -f docker-compose.prod.yml logs -f backend"
echo "  重启服务: docker compose -f docker-compose.prod.yml restart"
echo "  停止服务: docker compose -f docker-compose.prod.yml down"
