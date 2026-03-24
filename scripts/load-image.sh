#!/bin/bash
# ========================================
# 全能创意大师 - 服务器镜像加载脚本
# 功能：从 tar 文件加载 Docker 镜像
# 用途：适用于无法访问镜像仓库的服务器
# ========================================

set -e

echo ""
echo "========================================"
echo "  全能创意大师 - 镜像加载"
echo "========================================"
echo ""

# 配置
IMAGE_NAME="creative-master"
VERSION="2.2.2"
PROJECT_DIR="/opt/creative-master"

# 查找 tar 文件
TAR_FILE=$(ls -t ${PROJECT_DIR}/creative-master-*.tar 2>/dev/null | head -1)

if [ -z "$TAR_FILE" ]; then
    echo "[错误] 未找到镜像文件"
    echo "[提示] 请先将镜像文件上传到 ${PROJECT_DIR}/ 目录"
    echo "       文件名格式: creative-master-vX.X.X.tar"
    exit 1
fi

echo "[信息] 找到镜像文件: $TAR_FILE"
echo "[信息] 文件大小: $(du -h "$TAR_FILE" | cut -f1)"
echo ""

# 加载镜像
echo "[执行] 加载镜像..."
docker load -i "$TAR_FILE"

# 标记 latest 标签
echo "[执行] 标记 latest 标签..."
docker tag ${IMAGE_NAME}:${VERSION} ${IMAGE_NAME}:latest

# 显示镜像信息
echo ""
echo "[成功] 镜像加载完成"
docker images ${IMAGE_NAME}

echo ""
echo "========================================"
echo "  下一步：执行部署"
echo "========================================"
echo ""
echo "  cd ${PROJECT_DIR}"
echo "  docker compose -f docker-compose.cloud.yml up -d"
echo ""
