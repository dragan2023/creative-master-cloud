#!/bin/bash
# ========================================
# 全能创意大师 - 云端一键部署脚本
# 功能：拉取镜像 + 启动服务
# 支持两种模式：
#   1. 从镜像仓库拉取（需要配置仓库地址）
#   2. 从本地 tar 文件加载（适用于无外网访问）
# ========================================

set -e

echo ""
echo "========================================"
echo "  全能创意大师 - 云端部署"
echo "========================================"
echo ""

# 配置变量
IMAGE_NAME="creative-master"
VERSION="latest"
REGISTRY="registry.cn-hangzhou.aliyuncs.com"
NAMESPACE="your-namespace"
PROJECT_DIR="/opt/creative-master"

# 进入项目目录
cd $PROJECT_DIR

# ========================================
# 选择部署模式
# ========================================
echo "请选择部署模式："
echo "  1. 从镜像仓库拉取（需配置仓库地址）"
echo "  2. 从本地 tar 文件加载（需先上传镜像文件）"
echo ""
read -p "请输入选项 (1/2): " MODE

if [ "$MODE" = "1" ]; then
    # ========================================
    # 模式1：从镜像仓库拉取
    # ========================================
    echo ""
    echo "[模式1] 从镜像仓库拉取..."
    
    # 拉取镜像
    echo "[2/4] 拉取 Docker 镜像..."
    docker pull ${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${VERSION}
    docker tag ${REGISTRY}/${NAMESPACE}/${IMAGE_NAME}:${VERSION} ${IMAGE_NAME}:${VERSION}
    
    echo "[成功] 镜像拉取完成"
    
elif [ "$MODE" = "2" ]; then
    # ========================================
    # 模式2：从本地 tar 文件加载
    # ========================================
    echo ""
    echo "[模式2] 从本地 tar 文件加载..."
    
    # 查找 tar 文件
    TAR_FILE=$(ls -t ${PROJECT_DIR}/creative-master-*.tar 2>/dev/null | head -1)
    
    if [ -z "$TAR_FILE" ]; then
        echo "[错误] 未找到镜像文件"
        echo "[提示] 请先将镜像文件上传到 ${PROJECT_DIR}/ 目录"
        exit 1
    fi
    
    echo "[信息] 找到镜像文件: $TAR_FILE"
    echo "[2/4] 加载镜像..."
    docker load -i "$TAR_FILE"
    
    echo "[成功] 镜像加载完成"
else
    echo "[错误] 无效选项"
    exit 1
fi

# ========================================
# 第一步：拉取最新配置
# ========================================
echo ""
echo "[1/4] 拉取最新配置..."
git pull origin main

# ========================================
# 第三步：启动服务
# ========================================
echo "[3/4] 启动服务..."

# 使用预构建镜像启动（使用 cloud 配置文件）
docker compose -f docker-compose.cloud.yml up -d

echo "[成功] 服务启动完成"

# ========================================
# 第四步：健康检查
# ========================================
echo "[4/4] 健康检查..."
sleep 5

# 检查服务状态
docker compose -f docker-compose.cloud.yml ps

# 检查后端健康
echo ""
echo "等待后端服务就绪..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "[成功] 后端服务健康"
        break
    fi
    echo "  等待中... ($i/30)"
    sleep 2
done

# ========================================
# 完成
# ========================================
echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "访问地址："
echo "  HTTP:  http://$(curl -s ifconfig.me)"
echo "  HTTPS: https://$(curl -s ifconfig.me)"
echo ""
echo "查看日志："
echo "  docker logs creative-master-backend -f"
echo ""
