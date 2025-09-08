from celery import shared_task

from src.trademaster.trading_bot import TradeMaster
from datetime import datetime, time
scheduled_time = time(hour=9, minute=20)
@shared_task
def run_trade_task():
    if abs((datetime.combine(datetime.today(), scheduled_time) - datetime.now()).total_seconds()) > 3600:
        print("Skipping task, not scheduled time")
        return
    trade = TradeMaster()
    trade.make_some_money()
