import datetime as dt
import time
import pytz
from typing import Dict, List, Optional

import pandas as pd

from trading.broker import AngelOneClient
from trading.utils import token_lookup, Colors, calculate_quantity


class OpeningRangeBreakout(AngelOneClient):

    def orb_strat(
        self,
        tickers: List[str],
        hi_lo_prices: Dict[str, List[float]],
        positions: pd.DataFrame,
        open_orders: Optional[pd.DataFrame] = None,
        exchange: str = "NSE",
    ) -> None:
        IST = pytz.timezone("Asia/Kolkata")
        now_ist = dt.datetime.now(IST)
        capital = self.get_trade_capital()
        print(f'Current capital: {capital} Rs')

        active_tickers = list(tickers)
        if not positions.empty:
            active_tickers = [
                i for i in active_tickers
                if i + "-EQ" not in positions["tradingsymbol"].to_list()
            ]
        if open_orders is not None and not open_orders.empty:
            active_tickers = [
                i for i in active_tickers
                if i + "-EQ" not in open_orders["tradingsymbol"].to_list()
            ]

        for ticker in active_tickers:
            time.sleep(0.4)
            params = {
                "exchange": exchange,
                "symboltoken": token_lookup(ticker, self.instrument_list),
                "interval": "FIVE_MINUTE",
                "fromdate": (now_ist - dt.timedelta(days=4)).strftime("%Y-%m-%d %H:%M"),
                "todate": now_ist.strftime("%Y-%m-%d %H:%M"),
            }
            try:
                hist_data = self.smart_api.getCandleData(params)
                df_data = pd.DataFrame(
                    hist_data["data"],
                    columns=["date", "open", "high", "low", "close", "volume"],
                )
                df_data.set_index("date", inplace=True)
                df_data.index = pd.to_datetime(df_data.index)
                df_data.index = df_data.index.tz_localize(None)
                df_data["avg_vol"] = df_data["volume"].rolling(10).mean().shift(1)

                volume_breakout = df_data["volume"].iloc[-2] >= df_data["avg_vol"].iloc[-2]
                if volume_breakout:
                    ltp: Optional[float] = self.get_ltp(self.instrument_list, ticker, exchange)
                    if not ltp:
                        continue

                    bullish = (
                        df_data["close"].iloc[-2] >= hi_lo_prices[ticker][0]
                        and df_data["low"].iloc[-2] >= hi_lo_prices[ticker][1]
                    )
                    bearish = (
                        df_data["close"].iloc[-2] <= hi_lo_prices[ticker][1]
                        and df_data["high"].iloc[-2] <= hi_lo_prices[ticker][0]
                    )

                    if bullish:
                        sl = round(ltp * 0.99)
                        tgt = round(ltp * 1.02)
                        quantity = calculate_quantity(capital, tgt, sl, risk_pct=0.01, rr=2)
                        if quantity:
                            self.place_bracket_order(
                                self.instrument_list, ticker, "BUY", quantity, sl, tgt, exchange
                            )
                            print(f"{Colors.GREEN}BUY {quantity} x {ticker}{Colors.RESET}")
                    elif bearish:
                        sl = round(ltp * 1.01)
                        tgt = round(ltp * 0.98)
                        quantity = calculate_quantity(capital, tgt, sl, risk_pct=0.01, rr=2)
                        if quantity:
                            self.place_bracket_order(
                                self.instrument_list, ticker, "SELL", quantity, sl, tgt, exchange
                            )
                            print(f"{Colors.RED}SELL {quantity} x {ticker}{Colors.RESET}")
                    else:
                        print(f"No breakout for {ticker}")
                else:
                    print(f"{Colors.YELLOW}NO TRADE: {ticker} — no volume breakout{Colors.RESET}")
            except Exception as e:
                print(f"Error in orb_strat for {ticker}: {e}")
