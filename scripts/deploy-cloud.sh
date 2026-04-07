#!/bin/bash
# ========================================
# 全能创意大师 - 云端一键部署脚本 v2.0
# 功能：拉取镜像 + 数据保护 + 启动服务
# 支持两种模式：
#   1. 从镜像仓库拉取（需要配置仓库地址）
#   2. 从本地 tar 文件加载（适用于无外网访问）
# 
# 数据保护措施：
#   - 自动备份数据库
#   - 自动备份用户数据
#   - 使用 Named Volumes 确保数据持久化
# ========================================

set -e

echo ""
echo "========================================"
echo "  全能创意大师 - 云端部署 v2.0"
echo "========================================"
echo ""

# 配置变量
IMAGE_NAME="creative-master"
VERSION="latest"
REGISTRY="registry.cn-hangzhou.aliyuncs.com"
NAMESPACE="your-namespace"
PROJECT_DIR="/opt/creative-master"
BACKUP_DIR="/opt/creative-master/backups"

# 数据库配置（从环境变量或默认值）
DB_USER="${DB_USER:-creative_user}"
DB_NAME="${DB_NAME:-creative_master}"
DB_PASSWORD="${DB_PASSWORD:-creative_password}"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 进入项目目录
cd $PROJECT_DIR

# ========================================
# 数据保护函数
# ========================================

# 备份数据库
backup_database() {
    echo ""
    echo "[数据保护] 备份数据库..."
    
    local backup_time=$(date +%Y%m%d_%H%M%S)
    local db_backup_path="$BACKUP_DIR/db_$backup_time"
    
    # 检查数据库容器是否运行
    local db_container=$(docker ps --filter "name=creative-master-db" --format "{{.Names}}" | head -1)
    
    if [[ -z "$db_container" ]]; then
        echo "[信息] 数据库容器未运行，跳过备份"
        return 0
    fi
    
    mkdir -p "$db_backup_path"
    
    local backup_file="$db_backup_path/database.sql.gz"
    
    if docker exec -e PGPASSWORD="$DB_PASSWORD" "$db_container" \
        pg_dump -U "$DB_USER" -d "$DB_NAME" --format=plain --no-owner --no-acl 2>/dev/null | \
        gzip > "$backup_file"; then
        local backup_size=$(du -h "$backup_file" | cut -f1)
        echo "[成功] 数据库备份完成: $backup_file ($backup_size)"
    else
        echo "[警告] 数据库备份失败"
        rm -rf "$db_backup_path"
    fi
}

# 备份用户数据
backup_user_data() {
    echo ""
    echo "[数据保护] 备份用户数据..."
    
    local backup_time=$(date +%Y%m%d_%H%M%S)
    local data_backup_path="$BACKUP_DIR/data_$backup_time"
    local data_dir="$PROJECT_DIR/backend/data"
    
    if [[ ! -d "$data_dir" ]]; then
        echo "[信息] 数据目录不存在，跳过备份"
        return 0
    fi
    
    mkdir -p "$data_backup_path"
    
    local data_dirs=("uploads" "chroma" "knowledge_graphs" "character_states" "novel_projects")
    local backed_up=0
    
    for dir in "${data_dirs[@]}"; do
        if [[ -d "$data_dir/$dir" ]]; then
            if tar -czf "$data_backup_path/${dir}.tar.gz" -C "$data_dir" "$dir" 2>/dev/null; then
                ((backed_up++))
            fi
        fi
    done
    
    if [[ $backed_up -gt 0 ]]; then
        local total_size=$(du -sh "$data_backup_path" 2>/dev/null | cut -f1)
        echo "[成功] 用户数据备份完成: $backed_up 个目录 ($total_size)"
    else
        echo "[信息] 没有需要备份的用户数据"
        rm -rf "$data_backup_path"
    fi
}

# 验证数据完整性
verify_data() {
    echo ""
    echo "[验证] 检查数据完整性..."
    
    local errors=0
    
    # 检查数据库
    local db_container=$(docker ps --filter "name=creative-master-db" --format "{{.Names}}" | head -1)
    if [[ -n "$db_container" ]]; then
        if docker exec "$db_container" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
            echo "[成功] 数据库连接正常"
        else
            echo "[错误] 数据库连接失败"
            ((errors++))
        fi
    fi
    
    # 检查 Redis
    local redis_container=$(docker ps --filter "name=creative-master-redis" --format "{{.Names}}" | head -1)
    if [[ -n "$redis_container" ]]; then
        if docker exec "$redis_container" redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo "[成功] Redis 连接正常"
        else
            echo "[错误] Redis 连接失败"
            ((errors++))
        fi
    fi
    
    # 检查数据目录
    if [[ -d "$PROJECT_DIR/backend/data" ]]; then
        echo "[成功] 数据目录存在"
    fi
    
    return $errors
}

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
    echo "[2/5] 拉取 Docker 镜像..."
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
    echo "[2/5] 加载镜像..."
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
echo "[1/5] 拉取最新配置..."
git pull origin main

# ========================================
# 第二步：数据保护（备份现有数据）
# ========================================
echo ""
echo "[数据保护] 开始备份数据..."
backup_database
backup_user_data
echo "[成功] 数据备份完成，备份位置: $BACKUP_DIR"

# ========================================
# 第三步：启动服务
# ========================================
echo ""
echo "[3/5] 启动服务..."

# 停止旧服务（不含 -v，保护数据）
docker compose -f docker-compose.cloud.yml down --remove-orphans 2>/dev/null || true

# 启动新服务
docker compose -f docker-compose.cloud.yml up -d

echo "[成功] 服务启动完成"

# ========================================
# 第四步：健康检查
# ========================================
echo ""
echo "[4/5] 健康检查..."
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
# 第五步：验证数据完整性
# ========================================
echo ""
echo "[5/5] 验证数据完整性..."
verify_data

# ========================================
# 完成
# ========================================
echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "数据保护："
echo "  备份位置: $BACKUP_DIR"
echo "  数据库: Named Volume 'postgres_data'"
echo "  用户数据: Bind Mount '$PROJECT_DIR/backend/data'"
echo ""
echo "访问地址："
echo "  HTTP:  http://$(curl -s ifconfig.me)"
echo "  HTTPS: https://$(curl -s ifconfig.me)"
echo ""
echo "查看日志："
echo "  docker logs creative-master-backend -f"
echo ""
echo "数据恢复（如需）："
echo "  数据库: gunzip -c $BACKUP_DIR/db_*/database.sql.gz | docker exec -i creative-master-db psql -U $DB_USER -d $DB_NAME"
echo ""
