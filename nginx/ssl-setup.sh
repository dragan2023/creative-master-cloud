#!/bin/bash
# ========================================
# 全能创意大师 - SSL证书自动配置脚本
# 使用Let's Encrypt免费证书
# ========================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    log_error "请使用root用户运行此脚本"
    exit 1
fi

# 配置变量
DOMAIN="${1:-}"
EMAIL="${2:-admin@example.com}"

if [ -z "$DOMAIN" ]; then
    log_error "请提供域名参数"
    echo "用法: $0 your-domain.com [email]"
    echo "示例: $0 app.example.com admin@example.com"
    exit 1
fi

log_info "开始配置SSL证书..."
log_info "域名: $DOMAIN"
log_info "邮箱: $EMAIL"

# 1. 安装Certbot
log_info "检查Certbot安装..."
if ! command -v certbot &> /dev/null; then
    log_info "安装Certbot..."
    apt update
    apt install -y certbot python3-certbot-nginx
else
    log_info "Certbot已安装"
fi

# 2. 创建webroot目录
log_info "创建证书验证目录..."
mkdir -p /var/www/certbot
chown -R www-data:www-data /var/www/certbot
chmod -R 755 /var/www/certbot

# 3. 临时Nginx配置（用于证书申请）
log_info "创建临时Nginx配置..."
TEMP_NGINX_CONF="/etc/nginx/sites-available/certbot-temp"
cat > "$TEMP_NGINX_CONF" << EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN www.$DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 200 "Server is running. Please wait for SSL configuration.";
        add_header Content-Type text/plain;
    }
}
EOF

# 启用临时配置
ln -sf "$TEMP_NGINX_CONF" /etc/nginx/sites-enabled/certbot-temp

# 测试并重载Nginx
log_info "重载Nginx配置..."
nginx -t && systemctl reload nginx

# 4. 申请证书
log_info "申请SSL证书..."
certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "www.$DOMAIN" \
    --non-interactive

# 5. 检查证书是否申请成功
CERT_PATH="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if [ -f "$CERT_PATH" ]; then
    log_info "SSL证书申请成功！"
    log_info "证书路径: $CERT_PATH"
else
    log_error "SSL证书申请失败，请检查域名解析和Nginx配置"
    exit 1
fi

# 6. 设置自动续期
log_info "配置证书自动续期..."
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook \"systemctl reload nginx\"") | crontab -
    log_info "已添加自动续期定时任务（每天凌晨3点执行）"
else
    log_info "自动续期任务已存在"
fi

# 测试续期
log_info "测试证书续期..."
certbot renew --dry-run

# 7. 更新Nginx配置中的证书路径
log_info "更新Nginx配置..."
NGINX_CONF="/etc/nginx/sites-available/creative-master"
if [ -f "$NGINX_CONF" ]; then
    # 替换证书路径
    sed -i "s|ssl_certificate .*|ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;|g" "$NGINX_CONF"
    sed -i "s|ssl_certificate_key .*|ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;|g" "$NGINX_CONF"
    log_info "Nginx配置已更新"
fi

# 8. 清理临时配置
log_info "清理临时配置..."
rm -f /etc/nginx/sites-enabled/certbot-temp

# 9. 重载Nginx
log_info "重载Nginx..."
nginx -t && systemctl reload nginx

# 10. 验证HTTPS
log_info "验证HTTPS配置..."
sleep 2
if curl -sI "https://$DOMAIN" | grep -q "HTTP"; then
    log_info "HTTPS配置成功！"
else
    log_warn "HTTPS验证失败，请手动检查"
fi

# 完成
echo ""
log_info "========================================"
log_info "SSL证书配置完成！"
log_info "========================================"
echo ""
echo "证书信息:"
echo "  域名: $DOMAIN"
echo "  证书路径: /etc/letsencrypt/live/$DOMAIN/fullchain.pem"
echo "  私钥路径: /etc/letsencrypt/live/$DOMAIN/privkey.pem"
echo "  过期时间: 90天后自动续期"
echo ""
echo "后续步骤:"
echo "  1. 确保Nginx配置中的server_name已设置为 $DOMAIN"
echo "  2. 重启Nginx: systemctl restart nginx"
echo "  3. 访问 https://$DOMAIN 验证"
echo ""
