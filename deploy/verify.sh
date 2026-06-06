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
BOT_HTTP=$(curl -so /dev/null -w "%{http_code}" "${BASE_URL}/api/bot/status/" || echo "000")
if [[ "${BOT_HTTP}" == "401" || "${BOT_HTTP}" == "403" ]]; then
  echo "  OK  /api/bot/status/ (${BOT_HTTP} — auth required, as expected)"
else
  curl -sf "${BASE_URL}/api/bot/status/" | head -c 200 && echo "" || echo "  FAIL /api/bot/status/ (HTTP ${BOT_HTTP})"
fi

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
echo "==> Angel One capital (requires valid .env credentials + logged-in session)..."
CAPITAL_HTTP=$(curl -so /dev/null -w "%{http_code}" "${BASE_URL}/api/capital/" || echo "000")
if [[ "${CAPITAL_HTTP}" == "401" || "${CAPITAL_HTTP}" == "403" ]]; then
  echo "  OK  /api/capital/ (${CAPITAL_HTTP} — auth required, as expected)"
else
  CAPITAL=$(curl -sf "${BASE_URL}/api/capital/" || echo '{"error":"failed"}')
  echo "  ${CAPITAL}" | head -c 300
fi
echo ""

echo "Done. Review output above for any FAIL lines."
