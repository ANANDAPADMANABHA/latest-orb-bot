#!/usr/bin/env bash
# Install or update TradeMaster application (run from repo root on VPS)
set -euo pipefail

APP_DIR="/var/www/trademaster"
cd "${APP_DIR}"

echo "==> Pulling latest code..."
git pull

echo "==> Backend: venv + dependencies..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  echo "ERROR: backend/.env not found. Copy from .env.production.example and fill in secrets."
  exit 1
fi

echo "==> Django migrate + collectstatic..."
python manage.py migrate --noinput
python manage.py collectstatic --noinput
deactivate

echo "==> Frontend: build..."
cd ../frontend
npm ci || npm install
npm run build

echo "==> Setting permissions for www-data..."
cd "${APP_DIR}"
chown -R www-data:www-data backend/db.sqlite3 backend/staticfiles 2>/dev/null || true
chown -R www-data:www-data backend
chmod 640 backend/.env 2>/dev/null || true

echo "==> Restarting services (if installed)..."
for svc in trademaster-web trademaster-celery trademaster-celery-beat; do
  if systemctl is-enabled "${svc}" &>/dev/null; then
    systemctl restart "${svc}"
    echo "  restarted ${svc}"
  fi
done

echo "Deploy complete."
