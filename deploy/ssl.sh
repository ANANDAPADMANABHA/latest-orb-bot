#!/usr/bin/env bash
# Enable HTTPS with Let's Encrypt (domain must already point to this VPS)
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "${DOMAIN}" ]]; then
  echo "Usage: sudo bash deploy/ssl.sh yourdomain.com"
  exit 1
fi

echo "==> Obtaining SSL certificate for ${DOMAIN}..."
certbot --nginx -d "${DOMAIN}" -d "www.${DOMAIN}" --non-interactive --agree-tos -m "admin@${DOMAIN}" || \
  certbot --nginx -d "${DOMAIN}" --agree-tos

echo ""
echo "SSL enabled. Update backend/.env on the server:"
echo "  SECURE_SSL_REDIRECT=True"
echo "  ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN},<VPS_IP>"
echo "  CORS_ALLOWED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}"
echo ""
echo "Then run: sudo bash deploy/deploy.sh"
