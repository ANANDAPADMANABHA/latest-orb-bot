import datetime as dt
import time
import sys
import pytz
# sys.path.append('D:\projects\Trade-master')
import pandas as pd

from src.trademaster.strategies.opening_range_breakout import (
    OpeningRangeBreakout,
)
from src.trademaster.utils import get_stock_tickers


class TradeMaster(OpeningRangeBreakout):
    def make_some_money(self) -> None:
        print('Lets make some money')
        # 1. Define the target timezone (IST)
        IST = pytz.timezone('Asia/Calcutta')

        starttime = time.time()
        hi_lo_prices = {}
        self._load_instrument_list()
        self._initialize_smart_api()
        # ✅ Always fetch the latest tickers from Google Sheets
        ORB_TICKERS = get_stock_tickers(sheet_name='trade-master')
        data_0920 = self.hist_data_0920(
            ORB_TICKERS, 4, 'FIVE_MINUTE', self.instrument_list
        )
        for ticker in ORB_TICKERS:
            hi_lo_prices[ticker] = [
                data_0920[ticker]['high'].iloc[-1],
                data_0920[ticker]['low'].iloc[-1],
            ]
        df = pd.DataFrame.from_dict(hi_lo_prices)
        print(df)

        # 2. Get the current time, making it IST-aware
        now = dt.datetime.now(IST)
        seconds_to_sleep = (300 - (now.minute % 5) * 60 - now.second - now.microsecond / 1000000)
        print(f"Waiting for {seconds_to_sleep:.2f} seconds to align with the next 5-minute mark.")
        time.sleep(seconds_to_sleep)
        starttime = time.time()


        # 3. Define the Target End Time (3:30 PM IST) as a timezone-aware object
        # This replaces the entire problematic dt.datetime.strptime call
        market_end_time_ist = dt.datetime(
            now.year, now.month, now.day, 
            hour=15,          # 15 for 3 PM
            minute=30,        # 30 minutes
            tzinfo=IST        # ✅ CRITICAL: Make it IST-aware
        )

        while dt.datetime.now(IST) < market_end_time_ist:
            print('starting passthrough at {}'.format(dt.datetime.now()))
            positions = pd.DataFrame(self.smart_api.position()['data'])
            open_orders = self.get_open_orders()
            self.orb_strat(ORB_TICKERS, hi_lo_prices, positions, open_orders)
            time.sleep(300 - ((time.time() - starttime) % 300.0))
        now = dt.datetime.now(IST)
        print('current_time',now)
        self.log_pnl()
        print('bot exiting after market time')