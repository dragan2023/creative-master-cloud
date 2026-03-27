#!/bin/bash
# ========================================
# 全能创意大师 - 本地自签名SSL证书生成
# 用于模拟HTTPS环境
# ========================================

set -e

SSL_DIR="./nginx/ssl"
CERT_FILE="$SSL_DIR/localhost.crt"
KEY_FILE="$SSL_DIR/localhost.key"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 创建SSL目录
mkdir -p "$SSL_DIR"

# 检查证书是否已存在
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    log_warn "SSL证书已存在"
    read -p "是否重新生成? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "使用现有证书"
        exit 0
    fi
fi

log_info "生成自签名SSL证书..."

# 生成私钥和证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$KEY_FILE" \
    -out "$CERT_FILE" \
    -subj "/C=CN/ST=Shanghai/L=Shanghai/O=Development/OU=Local/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"

# 设置权限
chmod 644 "$CERT_FILE"
chmod 600 "$KEY_FILE"

log_info "SSL证书生成完成!"
echo ""
echo "证书文件: $CERT_FILE"
echo "私钥文件: $KEY_FILE"
echo ""
echo "Windows信任证书步骤:"
echo "1. 双击 $CERT_FILE"
echo "2. 点击 '安装证书'"
echo "3. 选择 '本地计算机' -> '将所有的证书都放入下列存储'"
echo "4. 选择 '受信任的根证书颁发机构'"
echo "5. 完成安装后重启浏览器"
