# TradeMaster — ORB Bot

An intraday algorithmic trading system for the Indian equity market (NSE) using an **Opening Range Breakout (ORB)** strategy with **Angel One SmartAPI**.

The project is structured as a **Django REST API backend** + **React frontend**.

---

## Project Structure

```
latest-orb-bot/
├── backend/               ← Django backend
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example       ← copy to .env and fill in secrets
│   ├── trademaster_project/   ← Django settings, urls, celery
│   ├── api/               ← REST API (models, views, serializers, tasks)
│   └── trading/           ← Core trading logic (broker, strategy, utils)
│       └── strategies/
│           └── opening_range_breakout.py
└── frontend/              ← React + Vite frontend
    └── src/
        ├── pages/         ← Dashboard, Watchlist, Positions, P&L, Sessions
        ├── components/    ← Navbar, BotControl, StatCard
        └── api/           ← axios client
```

---

## Production deployment (VPS)

See **[deploy/DEPLOY.md](deploy/DEPLOY.md)** for full instructions to host on a single Ubuntu VPS with Nginx, Gunicorn, Celery, and Let's Encrypt HTTPS.

Quick summary:

```bash
sudo bash deploy/setup-server.sh          # one-time server bootstrap
git clone <repo> /var/www/trademaster
cp backend/.env.production.example backend/.env && nano backend/.env
sudo bash deploy/deploy.sh
sudo bash deploy/install-services.sh
sudo bash deploy/ssl.sh yourdomain.com
sudo bash deploy/verify.sh https://yourdomain.com
```

**Important:** Your VPS public IP must match the **Primary Static IP** registered on your Angel One SmartAPI app.

---

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/watchlist/` | List active watchlist tickers |
| POST | `/api/watchlist/` | Add a ticker |
| DELETE | `/api/watchlist/<id>/` | Remove a ticker |
| GET | `/api/bot/status/` | Bot running status |
| POST | `/api/bot/start/` | Start bot manually |
| POST | `/api/bot/stop/` | Stop running bot |
| POST | `/api/webhooks/chartink/<secret>/` | Chartink alert webhook (public; replaces watchlist + starts bot) |
| GET | `/api/webhooks/chartink/config/` | Webhook URL for Chartink setup (login required) |
| GET | `/api/positions/` | Live positions from Angel One |
| GET | `/api/orders/` | Live order book |
| GET | `/api/capital/` | Available trading capital |
| GET | `/api/pnl/` | Full P&L history (optional `?date=YYYY-MM-DD`) |
| GET | `/api/pnl/today/` | Today's trades + total P&L |
| GET | `/api/pnl/summary/` | Daily aggregate P&L (for chart) |
| GET | `/api/sessions/` | Past bot sessions |
| GET | `/api/health/` | System status (public; no login). Add `?probe=1` to test Angel One login |
| GET | `/api/auth/csrf/` | Set CSRF cookie (public) |
| POST | `/api/auth/login/` | Sign in (public) |
| POST | `/api/auth/logout/` | Sign out |
| GET | `/api/auth/me/` | Current user |

All endpoints except `/api/health/` and `/api/auth/csrf|login/` require a logged-in session.

---

## Login

The app uses **Django session login**. Create a user once, then sign in at `/login`.

**Local dev:**

```bash
cd backend
python manage.py createsuperuser
```

**Production (VPS):**

```bash
cd /var/www/trademaster/backend
source venv/bin/activate
python manage.py createsuperuser
deactivate
```

Then open your site (e.g. `https://trademaster.fit/login`) and sign in. The session cookie keeps you logged in until you click **Log out**.

---

## Setup

### 1. Backend

```bash
cd backend

# Create and activate virtual environment (recommended)
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
# Edit .env with your Angel One credentials

# Apply migrations
python manage.py migrate

# Create login user (required for the web UI)
python manage.py createsuperuser

# Optional: Django admin at /admin

# Start development server
python manage.py runserver
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies `/api` calls to the Django server at `http://localhost:8000`. Sign in at http://localhost:5173/login after creating a user.

### 3. Start Bot (Celery + Redis)

**Option A — No Redis (easiest for local Windows):**  
Click **Start Bot** in the dashboard. If Redis is not running, the backend starts the bot in a **background thread** automatically.

**Option B — With Redis + Celery (recommended for production-like setup):**

```bash
# Start Redis (from project root)
docker compose up -d

# Worker (new terminal)
cd backend
venv\Scripts\activate
celery -A trademaster_project worker --loglevel=info --pool=solo

# Beat scheduler — optional, auto-starts bot at 9:20 AM weekdays (new terminal)
celery -A trademaster_project beat --loglevel=info
```

If you see `Error 10061 connecting to localhost:6379`, Redis is not running — use Option A or start Redis with `docker compose up -d`.

**If API returns 500 with `cannot schedule new futures after interpreter shutdown`:**  
The dev server crashed (usually after saving code and autoreload). Press `Ctrl+C` in the backend terminal and start again:

```bash
python manage.py runserver
```

This is a local dev-only issue; production on the VPS does not use `runserver`.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for dev, `False` for prod |
| `API_KEY` | Angel One SmartAPI key (from My Apps) |
| `SMARTAPI_SECRET_KEY` | Secret key shown when creating the app (store for reference) |
| `PRIMARY_STATIC_IP` | Public IPv4 registered on your SmartAPI app |
| `CLIENT_ID` | Angel One client ID |
| `PASSWORD` | Angel One login password |
| `TOKEN` | TOTP secret (from Angel One) |
| `REDIS_URL` | Redis URL (default: `redis://localhost:6379/0`) |

---

## How the Bot Works

1. Celery Beat triggers `run_trade_task` every weekday at **9:20 AM IST**
2. Bot authenticates to Angel One via TOTP
3. Tickers are loaded from the **Watchlist** (stored in the database)
4. For each ticker, the opening range is computed from 5-minute candles up to 9:19 AM
5. Every 5 minutes until 3:30 PM, the bot checks for breakouts with a **volume filter**
6. On signal, a **bracket order** is placed (entry + stop-loss + target)
7. At session end, P&L is saved to the database and displayed in the UI
