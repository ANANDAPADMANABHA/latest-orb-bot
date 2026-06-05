# Deploy TradeMaster on a Single VPS

Angel One requires API requests to originate from your **registered static IP**. Run the full stack (Django + React + Celery + Redis) on one VPS whose public IP matches your SmartAPI app.

## Prerequisites

- Ubuntu 22.04 VPS with static public IPv4
- Domain pointed to VPS (optional but recommended for HTTPS)
- Git repo pushed (clone on server)
- Angel One SmartAPI app with **Primary Static IP = VPS public IP**

## Quick start (on the VPS)

```bash
# 1. Bootstrap server (once, as root)
sudo bash deploy/setup-server.sh

# 2. Clone and configure
sudo git clone <your-repo-url> /var/www/trademaster
sudo chown -R www-data:www-data /var/www/trademaster
sudo cp /var/www/trademaster/backend/.env.production.example /var/www/trademaster/backend/.env
sudo nano /var/www/trademaster/backend/.env   # fill all secrets

# 3. Edit Nginx server_name
sudo nano deploy/nginx/trademaster.conf   # replace yourdomain.com

# 4. Deploy app + install services
cd /var/www/trademaster
sudo bash deploy/deploy.sh
sudo bash deploy/install-services.sh

# 4b. Create web login user (once)
cd /var/www/trademaster/backend
sudo -u www-data venv/bin/python manage.py createsuperuser

# 5. HTTPS (after DNS propagates)
sudo bash deploy/ssl.sh yourdomain.com

# 6. Verify
sudo bash deploy/verify.sh https://yourdomain.com
```

## Architecture

```
Browser → Nginx (443)
            ├── /          → frontend/dist (React)
            ├── /api/*     → Gunicorn → Django
            └── /static/*  → Django staticfiles

Celery Worker  → Angel One SmartAPI (trades)
Celery Beat    → triggers bot at 9:20 AM IST Mon–Fri
Redis          → Celery broker
```

## Environment variables

Copy [backend/.env.production.example](../backend/.env.production.example) to `backend/.env` on the server.

| Variable | Required | Notes |
|----------|----------|-------|
| `DJANGO_SECRET_KEY` | Yes | Long random string |
| `DEBUG` | Yes | `False` in production |
| `ALLOWED_HOSTS` | Yes | Domain + VPS IP, comma-separated |
| `SECURE_SSL_REDIRECT` | After HTTPS | `True` once Certbot is done |
| `API_KEY` | Yes | Angel One SmartAPI key |
| `PRIMARY_STATIC_IP` | Yes | Must equal VPS public IP |
| `CLIENT_ID`, `PASSWORD`, `TOKEN` | Yes | Angel One credentials |
| `REDIS_URL` | Yes | `redis://127.0.0.1:6379/0` |
| `DATABASE_URL` | Optional | PostgreSQL; omit for SQLite |
| `CORS_ALLOWED_ORIGINS` | Optional | Only if UI on different domain |

## Web login

All API routes except `/api/health/` and login require a Django user session. After first deploy:

```bash
cd /var/www/trademaster/backend
sudo -u www-data venv/bin/python manage.py createsuperuser
```

Sign in at `https://yourdomain.com/login`.

## Angel One IP setup

When moving from local PC to VPS:

1. Note VPS IP: `curl ifconfig.me`
2. In [SmartAPI portal](https://smartapi.angelone.in) → My Apps → update **Primary Static IP** to VPS IP  
   **OR** create a new app with VPS IP and update `API_KEY` in `.env`
3. No Python code changes needed — only `.env`

## Chartink auto-watchlist (11 AM bot start)

See **[CHARTINK.md](CHARTINK.md)** for webhook URL setup, Chartink alert configuration, and curl testing.

Summary: set `CHARTINK_WEBHOOK_SECRET` in `.env`, set `BOT_AUTO_START_0920=false`, deploy, copy webhook URL from the Watchlist page into Chartink.

## Ongoing updates

```bash
cd /var/www/trademaster
sudo bash deploy/deploy.sh
```

## Files in `deploy/`

| File | Purpose |
|------|---------|
| `setup-server.sh` | One-time OS package install |
| `deploy.sh` | git pull, pip install, migrate, build frontend, restart |
| `install-services.sh` | systemd + Nginx setup |
| `ssl.sh` | Let's Encrypt HTTPS |
| `verify.sh` | Health checks |
| `systemd/*.service` | Gunicorn, Celery worker, Celery beat |
| `nginx/trademaster.conf` | Reverse proxy + static UI |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Invalid API Key | Check `API_KEY` in `.env` matches Angel One portal |
| IP mismatch on orders | VPS IP must match registered Primary Static IP |
| 502 Bad Gateway | `sudo systemctl status trademaster-web` |
| Bot not auto-starting at 11 AM | Chartink webhook + `CHARTINK_WEBHOOK_SECRET` — see [CHARTINK.md](CHARTINK.md) |
| Celery beat issues | `sudo systemctl status trademaster-celery-beat` |
| Rate limit errors | Avoid refreshing Dashboard too often |

## Security checklist

- [ ] `DEBUG=False`
- [ ] `.env` not in git (chmod 640, owned by www-data)
- [ ] UFW allows only 22, 80, 443
- [ ] Redis not exposed to internet
- [ ] HTTPS enabled via Certbot
