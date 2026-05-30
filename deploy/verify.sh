#!/usr/bin/env bash
# Post-deploy health checks (run on VPS)
set -euo pipefail

BASE_URL="${1:-http://localhost}"
BASE_URL="${BASE_URL%/}"

echo "==> Checking systemd services..."
for svc in trademaster-web trademaster-celery trademaster-celery-beat redis-server nginx; do
  if systemctl is-active --quiet "${svc}"; then
    echo "  OK  ${svc}"
  else
    echo "  FAIL ${svc}"
  fi
done

echo ""
echo "==> Checking API endpoints..."
curl -sf "${BASE_URL}/api/bot/status/" | head -c 200 && echo "" || echo "  FAIL /api/bot/status/"
curl -sf "${BASE_URL}/api/watchlist/" | head -c 200 && echo "" || echo "  FAIL /api/watchlist/"
curl -sf "${BASE_URL}/api/health/" | head -c 400 && echo "" || echo "  FAIL /api/health/"

echo ""
echo "==> Checking frontend..."
HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" "${BASE_URL}/")
if [[ "${HTTP_CODE}" == "200" ]]; then
  echo "  OK  frontend (${HTTP_CODE})"
else
  echo "  FAIL frontend (HTTP ${HTTP_CODE})"
fi

echo ""
echo "==> VPS public IP (must match Angel One Primary Static IP)..."
curl -sf ifconfig.me && echo ""

echo ""
echo "==> Angel One capital (requires valid .env credentials)..."
CAPITAL=$(curl -sf "${BASE_URL}/api/capital/" || echo '{"error":"failed"}')
echo "  ${CAPITAL}" | head -c 300
echo ""

echo "Done. Review output above for any FAIL lines."
