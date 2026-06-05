# Chartink webhook — auto watchlist + bot start

TradeMaster can receive [Chartink](https://chartink.com) scan alerts, replace the daily watchlist, and start the ORB bot. Use this instead of manual stock entry and the legacy 9:20 AM Celery auto-start.

## 1. Server configuration

On the VPS, add to `/var/www/trademaster/backend/.env`:

```bash
BOT_AUTO_START_0920=false
CHARTINK_WEBHOOK_ENABLED=true
CHARTINK_WEBHOOK_SECRET=<paste-random-token>
CHARTINK_SKIP_ETF=true
```

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Deploy and restart:

```bash
cd /var/www/trademaster
bash deploy/deploy.sh
sudo systemctl restart trademaster-celery-beat
```

## 2. Get your webhook URL

1. Sign in to TradeMaster
2. Open **Watchlist** in the navbar
3. Copy the **Chartink webhook** URL shown at the top

Format:

```
https://YOUR_DOMAIN/api/webhooks/chartink/YOUR_SECRET/
```

## 3. Chartink alert setup

1. Open your scanner on [chartink.com](https://chartink.com) (e.g. `uptrend`)
2. Click **Create/Modify Alert**
3. Schedule: **weekdays, 11:00 AM IST**
4. Paste the webhook URL into **Webhook URL (optional)**
5. Save

Chartink sends a JSON POST like:

```json
{
  "stocks": "RELIANCE,TCS,INFY",
  "trigger_prices": "2500,400,1800",
  "triggered_at": "11:00 am",
  "scan_name": "uptrend",
  "alert_name": "Alert for uptrend"
}
```

TradeMaster will:

1. Stop any running bot session
2. **Replace** the entire watchlist with valid NSE EQ symbols (ETFs filtered out)
3. Start a new bot session

## 4. Test before 11 AM

Replace `YOUR_DOMAIN` and `YOUR_SECRET`:

```bash
curl -X POST "https://YOUR_DOMAIN/api/webhooks/chartink/YOUR_SECRET/" \
  -H "Content-Type: application/json" \
  -d '{"stocks":"RELIANCE,TCS,INFY","triggered_at":"11:00 am","scan_name":"uptrend","alert_name":"test"}'
```

Expected response:

```json
{
  "ok": true,
  "symbols_added": 3,
  "bot_started": true,
  "session_id": 42
}
```

Then check:

- **Watchlist** page — 3 symbols listed
- **Dashboard → Bot Control** — status **Running**
- Logs: `journalctl -u trademaster-celery -f`

## 5. Debugging

| Issue | Fix |
|-------|-----|
| 404 on webhook | Wrong secret or `CHARTINK_WEBHOOK_SECRET` not set |
| `symbols_added: 0` | All symbols filtered (ETFs, invalid tickers) — check `skipped` in response |
| Bot not running | `systemctl status trademaster-celery` |
| Webhook URL not shown in UI | Set `CHARTINK_WEBHOOK_SECRET` in `.env` and redeploy |

Webhook events are logged in Django admin under **Chartink webhook events**.
