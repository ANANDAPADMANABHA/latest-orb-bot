#!/usr/bin/env bash
# Install systemd units and Nginx site config
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="/var/www/trademaster"

echo "==> Installing systemd services..."
cp "${SCRIPT_DIR}/systemd/trademaster-web.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/systemd/trademaster-celery.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/systemd/trademaster-celery-beat.service" /etc/systemd/system/
systemctl daemon-reload

echo "==> Installing Nginx config..."
cp "${SCRIPT_DIR}/nginx/trademaster.conf" /etc/nginx/sites-available/trademaster
ln -sf /etc/nginx/sites-available/trademaster /etc/nginx/sites-enabled/trademaster
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> Enabling and starting services..."
systemctl enable trademaster-web trademaster-celery trademaster-celery-beat
systemctl start trademaster-web trademaster-celery trademaster-celery-beat

echo "Services installed. Check status:"
systemctl status trademaster-web --no-pager
systemctl status trademaster-celery --no-pager
systemctl status trademaster-celery-beat --no-pager
