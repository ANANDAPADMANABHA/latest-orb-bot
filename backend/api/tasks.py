import datetime as dt
import threading

from celery import shared_task
from django.utils import timezone

# Set when user clicks Stop in local (no-Redis) mode; trading loop checks this.
_local_stop = threading.Event()


def is_bot_stop_requested() -> bool:
    return _local_stop.is_set()


def clear_bot_stop_flag() -> None:
    _local_stop.clear()


def request_bot_stop() -> None:
    _local_stop.set()


def execute_trade_bot(task_id: str = '', session_id: int | None = None) -> None:
    """Core bot run logic (used by Celery and local thread fallback)."""
    from api.models import BotSession, PnLRecord, WatchlistTicker
    from trading.trading_bot import TradeMaster

    if session_id:
        session = BotSession.objects.get(pk=session_id)
        session.task_id = task_id or session.task_id
        session.status = 'running'
        session.save(update_fields=['task_id', 'status'])
    else:
        session = BotSession.objects.create(status='running', task_id=task_id)

    clear_bot_stop_flag()
    try:
        db_tickers = list(
            WatchlistTicker.objects.filter(is_active=True).values_list('symbol', flat=True)
        )
        bot = TradeMaster()
        trades = bot.make_some_money(tickers=db_tickers if db_tickers else None)

        if trades:
            for t in trades:
                PnLRecord.objects.create(
                    date=dt.date.today(),
                    symbol=t.get('symbol', ''),
                    quantity=int(t.get('quantity') or 0),
                    pnl=float(t.get('pnl') or 0),
                )

        if session.status == 'running':
            session.status = 'completed'
    except Exception as exc:
        session.status = 'error'
        session.log = str(exc)
        raise
    finally:
        session.stopped_at = timezone.now()
        session.save()


@shared_task(bind=True)
def run_trade_task(self):
    execute_trade_bot(task_id=self.request.id or '')


def run_trade_bot_in_thread(session_id: int) -> None:
    """Background thread entrypoint for local dev without Redis."""
    execute_trade_bot(task_id='local-thread', session_id=session_id)
