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

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/watchlist/` | List active watchlist tickers |
| POST | `/api/watchlist/` | Add a ticker |
| DELETE | `/api/watchlist/<id>/` | Remove a ticker |
| GET | `/api/bot/status/` | Bot running status |
| POST | `/api/bot/start/` | Start bot manually |
| POST | `/api/bot/stop/` | Stop running bot |
| GET | `/api/positions/` | Live positions from Angel One |
| GET | `/api/orders/` | Live order book |
| GET | `/api/capital/` | Available trading capital |
| GET | `/api/pnl/` | Full P&L history (optional `?date=YYYY-MM-DD`) |
| GET | `/api/pnl/today/` | Today's trades + total P&L |
| GET | `/api/pnl/summary/` | Daily aggregate P&L (for chart) |
| GET | `/api/sessions/` | Past bot sessions |

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
# Edit .env with your Angel One credentials and Google Sheets creds

# Apply migrations
python manage.py migrate

# Create a superuser (optional, for /admin)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and proxies `/api` calls to the Django server at `http://localhost:8000`.

### 3. Celery (background task scheduler)

Make sure Redis is running, then in separate terminals:

```bash
# Worker
cd backend
celery -A trademaster_project worker --loglevel=info

# Beat scheduler (triggers bot at 9:20 AM weekdays)
celery -A trademaster_project beat --loglevel=info
```

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
| `GOOGLE_CREDS_JSON` | Google service account JSON (single line) |
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
