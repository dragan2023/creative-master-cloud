#!/bin/bash
# ========================================
# 全能创意大师 - 云端智能热更新脚本 v1.1
# 功能：代码同步、镜像构建、服务更新、自动回滚
# 优化：简洁进度条显示，避免日志刷屏
# ========================================

set -o pipefail

# ==================== 全局配置 ====================
PROJECT_NAME="creative-master-prod"
COMPOSE_FILE="docker-compose.prod.yml"
BACKEND_IMAGE="creative-master-prod-backend"
GIT_REMOTE="origin"
GIT_BRANCH="main"
LOG_DIR="/var/log/creative-master"
BACKUP_DIR="/opt/creative-master/backups"
MAX_BACKUPS=5
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=5

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 进度条状态
PROGRESS_TOTAL=0
PROGRESS_CURRENT=0
PROGRESS_START_TIME=0
LAST_PROGRESS_LINE=""

# ==================== 初始化 ====================
init() {
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_ROOT" || exit 1
    
    # 创建必要目录
    mkdir -p "$LOG_DIR" "$BACKUP_DIR"
    
    # 日志文件
    LOG_FILE="$LOG_DIR/hot-update-$(date +%Y%m%d_%H%M%S).log"
    
    # 状态文件（用于回滚）
    STATE_FILE="$BACKUP_DIR/.update_state"
    
    # 参数解析
    parse_args "$@"
}

# ==================== 参数解析 ====================
parse_args() {
    SKIP_CONFIRM=false
    DRY_RUN=false
    FORCE_REBUILD=false
    SKIP_PULL=false
    ROLLBACK_MODE=false
    QUIET_MODE=false
    VERBOSE_MODE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -y|--yes)
                SKIP_CONFIRM=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -r|--rebuild)
                FORCE_REBUILD=true
                shift
                ;;
            -s|--skip-pull)
                SKIP_PULL=true
                shift
                ;;
            -q|--quiet)
                QUIET_MODE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE_MODE=true
                shift
                ;;
            --rollback)
                ROLLBACK_MODE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                show_help
                exit 1
                ;;
        esac
    done
}

# ==================== 帮助信息 ====================
show_help() {
    echo "全能创意大师 - 云端智能热更新脚本 v1.1"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -y, --yes         跳过所有确认提示"
    echo "  -n, --dry-run     模拟运行，不执行实际操作"
    echo "  -r, --rebuild     强制重新构建镜像（不使用缓存）"
    echo "  -s, --skip-pull   跳过代码拉取，使用本地代码"
    echo "  -q, --quiet       静默模式，只显示进度条和错误"
    echo "  -v, --verbose     详细模式，显示所有构建日志"
    echo "  --rollback        执行回滚操作"
    echo "  -h, --help        显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                  # 交互式更新"
    echo "  $0 -y               # 自动确认更新"
    echo "  $0 -y -r            # 自动确认并强制重建镜像"
    echo "  $0 -y -q            # 静默模式更新（简洁输出）"
    echo "  $0 -y -v            # 详细模式更新（完整日志）"
    echo "  $0 --rollback       # 回滚到上一版本"
}

# ==================== 日志函数 ====================
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${BLUE}[INFO]${NC} $message" ;;
        SUCCESS) echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        WARNING) echo -e "${YELLOW}[WARNING]${NC} $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" ;;
        STEP) echo -e "${GREEN}==>${NC} $message" ;;
    esac
    
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

log_info() { log "INFO" "$1"; }
log_success() { log "SUCCESS" "$1"; }
log_warning() { log "WARNING" "$1"; }
log_error() { log "ERROR" "$1"; }
log_step() { log "STEP" "$1"; }

# ==================== 进度条函数 ====================
# 显示简洁进度条
draw_progress_bar() {
    local current=$1
    local total=$2
    local label="$3"
    local speed="$4"
    
    if [[ $total -eq 0 ]]; then
        return
    fi
    
    local percent=$((current * 100 / total))
    local bar_width=30
    local filled=$((percent * bar_width / 100))
    local empty=$((bar_width - filled))
    
    # 构建进度条
    local bar="${GREEN}"
    for ((i=0; i<filled; i++)); do bar+="#"; done
    bar+="${NC}${CYAN}"
    for ((i=0; i<empty; i++)); do bar+="-"; done
    bar+="${NC}"
    
    # 格式化大小
    local current_mb=$((current / 1024 / 1024))
    local total_mb=$((total / 1024 / 1024))
    
    # 构建进度行
    local progress_line="  ${label} [${bar}] ${percent}% (${current_mb}MB/${total_mb}MB) ${speed}"
    
    # 只在终端显示时更新
    if [[ -t 1 ]]; then
        # 清除上一行并显示新行
        echo -en "\r\033[K${progress_line}"
        LAST_PROGRESS_LINE="$progress_line"
    fi
}

# 解析 Docker 构建输出并显示进度
parse_build_output() {
    local line
    local downloading_count=0
    local extracting_count=0
    local current_layer=""
    local layer_progress=0
    local layer_total=0
    local last_update_time=0
    local downloaded_bytes=0
    local total_bytes=0
    local build_stage=""
    local stage_count=0
    local current_stage=0
    
    PROGRESS_START_TIME=$(date +%s)
    
    while IFS= read -r line; do
        # 所有输出写入日志文件
        echo "$line" >> "$LOG_FILE"
        
        # 详细模式：显示所有输出
        if $VERBOSE_MODE; then
            echo "$line"
            continue
        fi
        
        # 解析不同类型的输出
        
        # 检测构建阶段
        if echo "$line" | grep -qE "^#\d+\s+(DONE|ERROR|CANCELED)"; then
            local stage_status=$(echo "$line" | grep -oE "^#\d+\s+(DONE|ERROR|CANCELED)" | awk '{print $2}')
            local stage_num=$(echo "$line" | grep -oE "^#\d+" | tr -d '#')
            if [[ "$stage_status" == "DONE" ]]; then
                current_stage=$stage_num
                echo -e "\r\033[K${GREEN}✓${NC} 阶段 #${stage_num} 完成"
            elif [[ "$stage_status" == "ERROR" ]]; then
                echo -e "\r\033[K${RED}✗${NC} 阶段 #${stage_num} 失败"
            fi
            continue
        fi
        
        # 检测正在执行的阶段
        if echo "$line" | grep -qE "^#\d+\s+"; then
            local stage_info=$(echo "$line" | sed 's/^#[0-9]*\s*//')
            local stage_num=$(echo "$line" | grep -oE "^#\d+" | tr -d '#')
            
            # 过滤进度详情，只显示阶段描述
            if [[ -n "$stage_info" ]] && ! echo "$stage_info" | grep -qE "Downloading|Extracting|sha256|COPY|WORKDIR|ENV|RUN|EXPOSE|CMD|HEALTHCHECK"; then
                echo -e "\r\033[K${BLUE}▸${NC} 阶段 #${stage_num}: $stage_info"
            fi
            continue
        fi
        
        # 解析下载进度
        if echo "$line" | grep -qE "Downloading|extracting"; then
            # 提取进度信息
            local progress_info=$(echo "$line" | grep -oE "[0-9]+\.[0-9]+[KMGT]?B/[0-9]+\.[0-9]+[KMGT]?B" | head -1)
            local speed_info=$(echo "$line" | grep -oE "[0-9]+\.[0-9]+[KMGT]?B/s" | head -1)
            
            if [[ -n "$progress_info" ]]; then
                # 解析进度
                local current=$(echo "$progress_info" | cut -d'/' -f1)
                local total=$(echo "$progress_info" | cut -d'/' -f2)
                
                # 转换为字节
                local current_bytes=$(parse_size "$current")
                local total_bytes=$(parse_size "$total")
                
                # 限制更新频率（每秒最多2次）
                local now=$(date +%s)
                if [[ $((now - last_update_time)) -ge 1 ]]; then
                    draw_progress_bar "$current_bytes" "$total_bytes" "下载中" "$speed_info"
                    last_update_time=$now
                fi
            fi
            continue
        fi
        
        # 显示错误和警告
        if echo "$line" | grep -qiE "error|failed|fatal"; then
            echo -e "\r\033[K${RED}$line${NC}"
            continue
        fi
        
        # 静默模式：跳过其他输出
        if $QUIET_MODE; then
            continue
        fi
        
        # 默认模式：显示关键信息
        if echo "$line" | grep -qE "Step \d+/\d+|Successfully|built|Sending build context"; then
            echo -e "\r\033[K$line"
        fi
    done
    
    # 完成后换行
    echo ""
}

# 解析大小字符串为字节
parse_size() {
    local size="$1"
    local value=$(echo "$size" | grep -oE "[0-9]+(\.[0-9]+)?")
    local unit=$(echo "$size" | grep -oE "[KMGT]?B" | head -1)
    
    case "$unit" in
        KB|K) echo "$(echo "$value * 1024" | bc | cut -d'.' -f1)" ;;
        MB|M) echo "$(echo "$value * 1024 * 1024" | bc | cut -d'.' -f1)" ;;
        GB|G) echo "$(echo "$value * 1024 * 1024 * 1024" | bc | cut -d'.' -f1)" ;;
        TB|T) echo "$(echo "$value * 1024 * 1024 * 1024 * 1024" | bc | cut -d'.' -f1)" ;;
        *) echo "$value" ;;
    esac
}

# ==================== 错误处理 ====================
error_exit() {
    log_error "$1"
    echo ""
    echo -e "${RED}更新失败！正在执行自动回滚...${NC}"
    rollback
    exit 1
}

# ==================== 确认提示 ====================
confirm() {
    local message=$1
    local default=${2:-n}
    
    if $SKIP_CONFIRM; then
        return 0
    fi
    
    local prompt
    if [[ "$default" == "y" ]]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi
    
    echo -en "${YELLOW}$message ${prompt}: ${NC}"
    read -r response
    
    if [[ -z "$response" ]]; then
        response=$default
    fi
    
    [[ "$response" =~ ^[Yy]$ ]]
}

# ==================== 等待用户输入 ====================
pause() {
    if ! $SKIP_CONFIRM; then
        echo -en "${YELLOW}按回车键继续...${NC}"
        read -r
    fi
}

# ==================== 检查环境 ====================
check_environment() {
    log_step "检查运行环境..."
    
    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        error_exit "Docker 未安装"
    fi
    
    if ! docker info &> /dev/null; then
        error_exit "Docker 未运行，请先启动 Docker 服务"
    fi
    
    # 检查 docker-compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error_exit "docker-compose 未安装"
    fi
    
    # 检查 Git
    if ! command -v git &> /dev/null; then
        error_exit "Git 未安装"
    fi
    
    # 检查磁盘空间（至少需要 5GB）
    local available=$(df -BG "$PROJECT_ROOT" | awk 'NR==2 {print $4}' | tr -d 'G')
    if [[ $available -lt 5 ]]; then
        log_warning "磁盘空间不足 5GB (当前: ${available}GB)，可能导致构建失败"
        if ! confirm "是否继续？"; then
            exit 0
        fi
    fi
    
    # 检查端口占用
    if netstat -tuln 2>/dev/null | grep -q ":80 " || ss -tuln 2>/dev/null | grep -q ":80 "; then
        if ! docker ps --format '{{.Ports}}' | grep -q "80->"; then
            log_warning "端口 80 已被其他程序占用"
        fi
    fi
    
    log_success "环境检查通过"
}

# ==================== 保存当前状态 ====================
save_state() {
    log_info "保存当前状态..."
    
    # 获取当前 Git 提交
    local current_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
    
    # 获取当前镜像 ID
    local current_image=$(docker images --format '{{.ID}}' "$BACKEND_IMAGE:latest" 2>/dev/null | head -1 || echo "none")
    
    # 获取当前容器状态
    local containers_running=$(docker-compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | wc -l)
    
    # 保存状态
    cat > "$STATE_FILE" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "commit": "$current_commit",
    "image_id": "$current_image",
    "containers_running": $containers_running
}
EOF
    
    log_info "状态已保存到 $STATE_FILE"
}

# ==================== 备份配置 ====================
backup_config() {
    log_step "备份配置文件..."
    
    local backup_time=$(date +%Y%m%d_%H%M%S)
    local backup_path="$BACKUP_DIR/config_$backup_time"
    
    mkdir -p "$backup_path"
    
    # 备份关键配置文件
    local config_files=(
        ".env"
        "docker-compose.prod.yml"
        "docker-compose.cloud.yml"
        "nginx/nginx.conf"
        "nginx/conf.d"
        "backend/requirements.txt"
    )
    
    for file in "${config_files[@]}"; do
        if [[ -e "$PROJECT_ROOT/$file" ]]; then
            cp -rp "$PROJECT_ROOT/$file" "$backup_path/"
            log_info "已备份: $file"
        fi
    done
    
    # 记录备份信息
    echo "$backup_time" > "$backup_path/.backup_info"
    
    # 清理旧备份
    local backup_count=$(ls -d "$BACKUP_DIR"/config_* 2>/dev/null | wc -l)
    if [[ $backup_count -gt $MAX_BACKUPS ]]; then
        local old_backups=$(ls -dt "$BACKUP_DIR"/config_* | tail -n +$((MAX_BACKUPS + 1)))
        for old in $old_backups; do
            rm -rf "$old"
            log_info "已清理旧备份: $(basename $old)"
        done
    fi
    
    log_success "配置备份完成: $backup_path"
}

# ==================== 代码同步 ====================
sync_code() {
    log_step "同步代码仓库..."
    
    if $SKIP_PULL; then
        log_info "跳过代码拉取，使用本地代码"
        return 0
    fi
    
    # 检查是否有未提交的更改
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        log_warning "检测到未提交的本地更改"
        if confirm "是否暂存本地更改后继续？"; then
            git stash push -m "auto-stash-$(date +%Y%m%d_%H%M%S)"
            log_info "本地更改已暂存"
        fi
    fi
    
    # 获取远程分支信息
    log_info "获取远程更新..."
    local retry_count=0
    local max_retries=3
    
    while [[ $retry_count -lt $max_retries ]]; do
        if git fetch "$GIT_REMOTE" "$GIT_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
            break
        fi
        
        retry_count=$((retry_count + 1))
        if [[ $retry_count -lt $max_retries ]]; then
            log_warning "网络请求失败，${retry_count}/${max_retries} 次重试..."
            sleep 5
        else
            error_exit "无法连接到远程仓库，请检查网络连接"
        fi
    done
    
    # 检查是否有更新
    local local_commit=$(git rev-parse HEAD)
    local remote_commit=$(git rev-parse "$GIT_REMOTE/$GIT_BRANCH")
    
    if [[ "$local_commit" == "$remote_commit" ]]; then
        log_info "本地代码已是最新版本"
        return 0
    fi
    
    log_info "发现新版本: $remote_commit"
    log_info "更新内容:"
    git log --oneline HEAD.."$GIT_REMOTE/$GIT_BRANCH" | head -10 | while read line; do
        log_info "  $line"
    done
    
    if ! $SKIP_CONFIRM; then
        if ! confirm "是否拉取最新代码？"; then
            log_info "用户取消更新"
            exit 0
        fi
    fi
    
    # 拉取代码
    log_info "拉取最新代码..."
    if ! git pull "$GIT_REMOTE" "$GIT_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
        error_exit "代码拉取失败，可能存在冲突"
    fi
    
    log_success "代码同步完成"
}

# ==================== 清理旧镜像 ====================
cleanup_old_images() {
    log_step "清理旧版本镜像..."
    
    # 获取所有项目相关镜像
    local all_images=$(docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}' | \
        grep -E "^$BACKEND_IMAGE" | sort -k3 -r)
    
    if [[ -z "$all_images" ]]; then
        log_info "没有找到旧镜像"
        return 0
    fi
    
    # 保留最新的镜像，删除其他版本
    local image_count=$(echo "$all_images" | wc -l)
    if [[ $image_count -gt 1 ]]; then
        log_info "发现 $image_count 个版本镜像"
        
        # 获取最新镜像ID
        local latest_id=$(echo "$all_images" | head -1 | awk '{print $2}')
        
        # 删除旧版本
        echo "$all_images" | tail -n +2 | while read -r line; do
            local old_id=$(echo "$line" | awk '{print $2}')
            local old_tag=$(echo "$line" | awk '{print $1}')
            
            # 确保不删除正在使用的镜像
            if ! docker ps -a --format '{{.Image}}' | grep -q "$old_id"; then
                log_info "删除旧镜像: $old_tag ($old_id)"
                docker rmi -f "$old_id" 2>/dev/null || true
            fi
        done
    fi
    
    # 清理悬空镜像
    log_info "清理悬空镜像..."
    docker image prune -f 2>/dev/null | tail -1 | while read line; do
        log_info "  $line"
    done
    
    # 清理构建缓存（如果磁盘空间紧张）
    local available=$(df -BG "$PROJECT_ROOT" | awk 'NR==2 {print $4}' | tr -d 'G')
    if [[ $available -lt 10 ]]; then
        log_info "磁盘空间紧张，清理构建缓存..."
        docker builder prune -f --filter "until=24h" 2>/dev/null || true
    fi
    
    log_success "镜像清理完成"
}

# ==================== 构建镜像 ====================
build_image() {
    log_step "构建 Docker 镜像..."
    
    local build_args="--progress=plain"
    if $FORCE_REBUILD; then
        build_args="--no-cache --progress=plain"
        log_info "强制重建模式（不使用缓存）"
    fi
    
    log_info "开始构建镜像: $BACKEND_IMAGE:latest"
    
    # 显示构建进度
    local build_start=$(date +%s)
    
    if $DRY_RUN; then
        log_info "[模拟] 构建命令: docker-compose -f $COMPOSE_FILE build $build_args backend"
        return 0
    fi
    
    # 使用进度条解析器处理构建输出
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Docker 镜像构建中...${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    local build_exit_code=0
    docker-compose -f "$COMPOSE_FILE" build $build_args backend 2>&1 | parse_build_output || build_exit_code=${PIPESTATUS[0]}
    
    if [[ $build_exit_code -ne 0 ]]; then
        echo ""
        echo -e "${RED}构建失败！查看详细日志: $LOG_FILE${NC}"
        error_exit "镜像构建失败"
    fi
    
    local build_end=$(date +%s)
    local build_duration=$((build_end - build_start))
    
    echo ""
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    log_success "镜像构建完成 (耗时: ${build_duration}秒)"
    echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # 显示镜像信息
    local image_size=$(docker images --format '{{.Size}}' "$BACKEND_IMAGE:latest")
    local image_id=$(docker images --format '{{.ID}}' "$BACKEND_IMAGE:latest")
    log_info "镜像ID: $image_id, 大小: $image_size"
}

# ==================== 停止服务 ====================
stop_services() {
    log_step "停止服务..."
    
    # 检查是否有运行中的服务
    if ! docker-compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | grep -q .; then
        log_info "服务未运行"
        return 0
    fi
    
    if $DRY_RUN; then
        log_info "[模拟] 停止服务"
        return 0
    fi
    
    log_info "正在停止服务..."
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans 2>&1 | tee -a "$LOG_FILE"
    
    log_success "服务已停止"
}

# ==================== 启动服务 ====================
start_services() {
    log_step "启动服务..."
    
    if $DRY_RUN; then
        log_info "[模拟] 启动服务"
        return 0
    fi
    
    log_info "正在启动服务..."
    if ! docker-compose -f "$COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG_FILE"; then
        error_exit "服务启动失败"
    fi
    
    log_success "服务启动命令已执行"
}

# ==================== 健康检查 ====================
health_check() {
    log_step "执行健康检查..."
    
    if $DRY_RUN; then
        log_info "[模拟] 健康检查通过"
        return 0
    fi
    
    log_info "等待服务就绪..."
    
    local retry=0
    while [[ $retry -lt $HEALTH_CHECK_RETRIES ]]; do
        # 检查容器状态
        local unhealthy=$(docker-compose -f "$COMPOSE_FILE" ps --format '{{.Status}}' 2>/dev/null | grep -c "unhealthy\|exited" || echo "0")
        
        if [[ "$unhealthy" -gt 0 ]]; then
            log_error "检测到不健康容器"
            docker-compose -f "$COMPOSE_FILE" ps
            return 1
        fi
        
        # 检查后端健康接口
        if curl -sf http://localhost/health > /dev/null 2>&1; then
            log_success "后端服务健康"
            
            # 检查所有容器状态
            local healthy_count=$(docker-compose -f "$COMPOSE_FILE" ps --format '{{.Status}}' 2>/dev/null | grep -c "healthy" || echo "0")
            local total_count=$(docker-compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | wc -l)
            
            log_info "健康容器: $healthy_count / $total_count"
            
            if [[ "$healthy_count" -ge "$((total_count - 1))" ]]; then
                log_success "所有服务健康检查通过"
                return 0
            fi
        fi
        
        retry=$((retry + 1))
        log_info "等待中... ($retry/$HEALTH_CHECK_RETRIES)"
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    log_error "健康检查超时"
    docker-compose -f "$COMPOSE_FILE" ps
    docker-compose -f "$COMPOSE_FILE" logs backend --tail=50
    return 1
}

# ==================== 回滚操作 ====================
rollback() {
    log_step "执行回滚..."
    
    if [[ ! -f "$STATE_FILE" ]]; then
        log_error "未找到状态文件，无法回滚"
        return 1
    fi
    
    # 读取状态
    local saved_commit=$(cat "$STATE_FILE" | grep -o '"commit": *"[^"]*"' | cut -d'"' -f4)
    local saved_image=$(cat "$STATE_FILE" | grep -o '"image_id": *"[^"]*"' | cut -d'"' -f4)
    
    log_info "回滚到提交: $saved_commit"
    log_info "回滚到镜像: $saved_image"
    
    # 停止服务
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
    
    # 恢复代码
    if [[ "$saved_commit" != "unknown" ]]; then
        git reset --hard "$saved_commit" 2>&1 | tee -a "$LOG_FILE" || true
    fi
    
    # 查找最近的备份
    local latest_backup=$(ls -dt "$BACKUP_DIR"/config_* 2>/dev/null | head -1)
    if [[ -n "$latest_backup" ]]; then
        log_info "恢复配置: $latest_backup"
        cp -rp "$latest_backup"/* "$PROJECT_ROOT/" 2>/dev/null || true
    fi
    
    # 重新构建（如果需要）
    if [[ "$saved_image" != "none" ]] && docker images --format '{{.ID}}' | grep -q "$saved_image"; then
        log_info "使用现有镜像: $saved_image"
    else
        log_info "重新构建镜像..."
        docker-compose -f "$COMPOSE_FILE" build 2>&1 | tee -a "$LOG_FILE" || true
    fi
    
    # 启动服务
    docker-compose -f "$COMPOSE_FILE" up -d 2>&1 | tee -a "$LOG_FILE" || true
    
    log_success "回滚完成"
}

# ==================== 显示状态 ====================
show_status() {
    log_step "当前服务状态:"
    echo ""
    
    docker-compose -f "$COMPOSE_FILE" ps 2>/dev/null || true
    
    echo ""
    log_info "访问地址:"
    local server_ip=$(curl -sf ifconfig.me 2>/dev/null || echo "localhost")
    echo "  HTTP:  http://$server_ip"
    echo "  HTTPS: https://$server_ip"
    echo ""
    log_info "查看日志: docker-compose -f $COMPOSE_FILE logs -f"
    log_info "日志文件: $LOG_FILE"
}

# ==================== 主函数 ====================
main() {
    init "$@"
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  全能创意大师 - 云端智能热更新${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    # 如果是回滚模式
    if $ROLLBACK_MODE; then
        rollback
        show_status
        exit 0
    fi
    
    # 检查环境
    check_environment
    
    # 确认更新
    if ! $SKIP_CONFIRM; then
        echo ""
        log_warning "即将执行热更新，服务将短暂中断"
        if ! confirm "是否继续？"; then
            exit 0
        fi
    fi
    
    # 记录开始时间
    local start_time=$(date +%s)
    
    # 执行更新流程
    save_state
    backup_config
    sync_code
    cleanup_old_images
    build_image
    stop_services
    start_services
    
    # 健康检查
    if ! health_check; then
        error_exit "健康检查失败"
    fi
    
    # 记录结束时间
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  更新完成！总耗时: ${duration}秒${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    show_status
}

# ==================== 执行 ====================
main "$@"
