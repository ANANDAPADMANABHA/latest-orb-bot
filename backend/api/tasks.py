import datetime as dt
from celery import shared_task
from django.utils import timezone


@shared_task(bind=True)
def run_trade_task(self):
    from api.models import BotSession, PnLRecord, WatchlistTicker
    from trading.trading_bot import TradeMaster

    session = BotSession.objects.create(status='running', task_id=self.request.id or '')
    try:
        # Pull tickers from DB watchlist instead of Google Sheets
        db_tickers = list(
            WatchlistTicker.objects.filter(is_active=True).values_list('symbol', flat=True)
        )
        bot = TradeMaster()
        trades = bot.make_some_money(tickers=db_tickers if db_tickers else None)

        # Persist PnL records from today's session
        if trades:
            for t in trades:
                PnLRecord.objects.create(
                    date=dt.date.today(),
                    symbol=t.get('symbol', ''),
                    quantity=int(t.get('quantity') or 0),
                    pnl=float(t.get('pnl') or 0),
                )

        session.status = 'completed'
    except Exception as exc:
        session.status = 'error'
        session.log = str(exc)
        raise
    finally:
        session.stopped_at = timezone.now()
        session.save()
