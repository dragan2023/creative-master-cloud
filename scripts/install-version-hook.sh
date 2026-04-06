#!/bin/bash
#
# 安装 Git pre-push hook
#
# 使用方法: bash scripts/install-version-hook.sh
#

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GIT_HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo -e "${YELLOW}正在安装 Git pre-push hook...${NC}"

# 检查 .git 目录是否存在
if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    echo "错误: 未找到 .git 目录，请确保在 Git 仓库中运行此脚本"
    exit 1
fi

# 创建 hooks 目录（如果不存在）
mkdir -p "$GIT_HOOKS_DIR"

# 复制 hook 文件
cp "$SCRIPT_DIR/git-hooks/pre-push" "$GIT_HOOKS_DIR/pre-push"

# 设置执行权限
chmod +x "$GIT_HOOKS_DIR/pre-push"

echo -e "${GREEN}✓ Git pre-push hook 安装成功！${NC}"
echo ""
echo "功能说明:"
echo "  - 推送到 main/master 分支时自动更新版本号"
echo "  - 根据提交信息自动判断版本递增类型"
echo "  - 自动更新 version.json 和 CHANGELOG.md"
echo ""
echo "人工干预标记（在提交信息中添加）:"
echo "  [skip version]  - 跳过版本更新"
echo "  [major]         - 强制主版本递增"
echo "  [minor]         - 强制次版本递增"
echo "  [patch]         - 强制修订号递增"
