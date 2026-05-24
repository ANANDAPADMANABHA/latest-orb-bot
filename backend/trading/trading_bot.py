import datetime as dt
import time
import pytz
import pandas as pd

from trading.strategies.opening_range_breakout import OpeningRangeBreakout
from trading.utils import get_stock_tickers


class TradeMaster(OpeningRangeBreakout):

    def make_some_money(self, tickers=None) -> None:
        print('Starting TradeMaster bot...')
        IST = pytz.timezone('Asia/Calcutta')

        self._load_instrument_list()
        self._initialize_smart_api()

        # Use provided tickers, or fall back to Google Sheets
        ORB_TICKERS = tickers if tickers else get_stock_tickers(sheet_name='trade-master')
        data_0920 = self.hist_data_0920(ORB_TICKERS, 4, 'FIVE_MINUTE', self.instrument_list)

        hi_lo_prices = {}
        for ticker in ORB_TICKERS:
            if ticker in data_0920 and not data_0920[ticker].empty:
                hi_lo_prices[ticker] = [
                    data_0920[ticker]['high'].iloc[-1],
                    data_0920[ticker]['low'].iloc[-1],
                ]

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
            print(f'Loop pass at {dt.datetime.now(IST).strftime("%H:%M:%S")}')
            positions_data = self.get_positions()
            positions = pd.DataFrame(positions_data) if positions_data else pd.DataFrame()
            open_orders = self.get_open_orders()
            self.orb_strat(list(hi_lo_prices.keys()), hi_lo_prices, positions, open_orders)
            time.sleep(300 - ((time.time() - starttime) % 300.0))

        self.log_pnl()
        print('Bot exiting after market close.')
