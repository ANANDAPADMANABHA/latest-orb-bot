#!/usr/bin/env bash
# One-time VPS bootstrap for Ubuntu 22.04+
# Run as root or with sudo on a fresh VPS.
set -euo pipefail

echo "==> Updating system packages..."
apt update && apt upgrade -y

echo "==> Installing system dependencies..."
apt install -y \
  python3 python3-venv python3-pip \
  nginx redis-server git \
  ufw certbot python3-certbot-nginx \
  curl

echo "==> Installing Node.js 20..."
if ! command -v node &>/dev/null || [[ "$(node -v)" != v20* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi

echo "==> Enabling Redis..."
systemctl enable redis-server
systemctl start redis-server

echo "==> Configuring firewall (SSH, HTTP, HTTPS)..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "==> Creating app directory..."
mkdir -p /var/www/trademaster
if id www-data &>/dev/null; then
  chown -R www-data:www-data /var/www/trademaster
fi

echo ""
echo "Bootstrap complete. Next steps:"
echo "  1. Clone repo:  git clone <repo-url> /var/www/trademaster"
echo "  2. Copy env:    cp backend/.env.production.example backend/.env && nano backend/.env"
echo "  3. Run deploy:  sudo bash deploy/deploy.sh"
echo "  4. Install svc: sudo bash deploy/install-services.sh"
echo "  5. Nginx+SSL:   sudo bash deploy/ssl.sh yourdomain.com"
