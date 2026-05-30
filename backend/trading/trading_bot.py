import datetime as dt
import time
import pytz
import pandas as pd

from trading.broker import orb_high_low_from_df
from trading.strategies.opening_range_breakout import OpeningRangeBreakout
def _should_stop_bot() -> bool:
    try:
        from api.tasks import is_bot_stop_requested
        return is_bot_stop_requested()
    except Exception:
        return False


class TradeMaster(OpeningRangeBreakout):

    def make_some_money(self, tickers=None, session_id=None):
        print('Starting TradeMaster bot...')
        IST = pytz.timezone('Asia/Calcutta')

        self._load_instrument_list()
        self._initialize_smart_api()

        ORB_TICKERS = list(tickers) if tickers else []
        if not ORB_TICKERS:
            raise ValueError(
                'Watchlist is empty. Add symbols on the Watchlist page before starting the bot.'
            )
        data_0920 = self.hist_data_0920(ORB_TICKERS, 4, 'FIVE_MINUTE', self.instrument_list)

        hi_lo_prices = {}
        for ticker in ORB_TICKERS:
            levels = orb_high_low_from_df(data_0920.get(ticker))
            if levels:
                hi_lo_prices[ticker] = list(levels)

        now = dt.datetime.now(IST)
        seconds_to_sleep = 300 - (now.minute % 5) * 60 - now.second - now.microsecond / 1_000_000
        print(f"Syncing to next 5-minute mark in {seconds_to_sleep:.1f}s...")
        time.sleep(max(0, seconds_to_sleep))

        starttime = time.time()
        market_end_time = dt.datetime(
            now.year, now.month, now.day,
            hour=15, minute=30,
            tzinfo=IST,
        )

        while dt.datetime.now(IST) < market_end_time:
            if _should_stop_bot():
                print('Bot stop requested — exiting loop.')
                break
            print(f'Loop pass at {dt.datetime.now(IST).strftime("%H:%M:%S")}')
            from api.tasks import touch_bot_heartbeat
            touch_bot_heartbeat(session_id)
            positions_data = self.get_positions()
            positions = pd.DataFrame(positions_data) if positions_data else pd.DataFrame()
            open_orders = self.get_open_orders()
            self.orb_strat(list(hi_lo_prices.keys()), hi_lo_prices, positions, open_orders)
            time.sleep(300 - ((time.time() - starttime) % 300.0))

        trades = self.log_pnl()
        print('Bot exiting after market close.')
        return trades
