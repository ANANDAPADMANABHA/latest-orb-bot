import datetime as dt
import time
from typing import Dict, List, Optional

import pandas as pd

from src.trademaster.broker import AngelOneClient
from src.trademaster.utils import token_lookup, Colors, calculate_quantity


class OpeningRangeBreakout(AngelOneClient):
    """A class to implement Opening Range Breakout trading strategy."""

    def safe_place_robo_order(
        self,
        instrument_list,
        ticker: str,
        side: str,
        hi_lo_price: List[float],
        quantity: int,
        retries: int = 3,
        delay: float = 2.0,
        ) -> bool:
        """
        Wrapper for place_robo_order with retry mechanism.
        Falls back to market order if token is under cautionary listings (AB4036).
        """
        for attempt in range(1, retries + 1):
            try:
                response = self.place_robo_order(instrument_list, ticker, side, hi_lo_price, quantity)
                print('response of place robo order' , response)
                if response:
                    return True

                print(f"[Attempt {attempt}] {side} order failed for {ticker}, retrying...")

            except Exception as e:
                print(f"[Attempt {attempt}] Exception while placing {side} order for {ticker}: {e}")

            time.sleep(delay)

        print(f"❌ Failed to place {side} order for {ticker} after {retries} attempts.")
        return False


    def orb_strat(
        self,
        tickers: List[str],
        hi_lo_prices: Dict[str, List[float]],
        positions: pd.DataFrame,
        open_orders: Optional[pd.DataFrame] = None,
        exchange: str = "NSE",
    ) -> None:
        """
        Implements an Opening Range Breakout (ORB) strategy for given tickers.
        """
        
        capital = self.get_trade_capital()
        print(f'current capital is {capital} Rs')
        if not positions.empty:
            tickers = [
                i for i in tickers if i + "-EQ" not in positions["tradingsymbol"].to_list()
            ]
        if open_orders is not None and not open_orders.empty:
            # proceed with the tickers that are not in open orders
            tickers = [
                i for i in tickers if i + "-EQ" not in open_orders["tradingsymbol"].to_list()
            ]

        for ticker in tickers:
            time.sleep(0.4)
            params = {
                "exchange": exchange,
                "symboltoken": token_lookup(ticker, self.instrument_list),
                "interval": "FIVE_MINUTE",
                "fromdate": (dt.date.today() - dt.timedelta(4)).strftime("%Y-%m-%d %H:%M"),
                "todate": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
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
                print(df_data)
                print(
                f"[DATA] {ticker} | "
                f"O:{df_data['open'].iloc[-2]} "
                f"H:{df_data['high'].iloc[-2]} "
                f"L:{df_data['low'].iloc[-2]} "
                f"C:{df_data['close'].iloc[-2]} "
                f"CurrentV:{df_data['volume'].iloc[-2]} "
                f"AvgV:{df_data['avg_vol'].iloc[-2]}"
                )
                print(
                f"[ORB LEVELS] {ticker} | "
                f"High:{hi_lo_prices[ticker][0]} "
                f"Low:{hi_lo_prices[ticker][1]}"
                )

                # if df_data["volume"].iloc[-2] >= df_data["avg_vol"].iloc[-2]:
                #     print("ALERT..............!")
                #     print(
                #         f"{Colors.GREEN}{ticker} has broken the average volume,{Colors.RESET}"
                #     )
                ltp: Optional[float] = self.get_ltp(self.instrument_list, ticker, exchange)
                print(f"Ltp of {ticker} is {ltp}")
                # print(f"previous close of ticker: {ticker} is {df_data["close"].iloc[-2]} and previous candle low is {df_data["low"].iloc[-2]}")
                if (
                        df_data["close"].iloc[-2] >= hi_lo_prices[ticker][0]
                        and df_data["low"].iloc[-2] >= hi_lo_prices[ticker][1]
                    ):
                        
                        sl = round(ltp * 0.99)     # 1% below
                        tgt = round(ltp * 1.02)    # 2% above
                        quantity = calculate_quantity(capital, tgt, sl, risk_pct=0.01, rr=2)
                        self.place_bracket_order(
                            self.instrument_list, ticker, "BUY", quantity, sl, tgt, exchange
                        )
               
                        print(
                                f"{Colors.GREEN}Bought {quantity} stocks of {ticker}{Colors.RESET}"
                            )
                elif (
                        df_data["close"].iloc[-2] <= hi_lo_prices[ticker][1]
                        and df_data["high"].iloc[-2] <= hi_lo_prices[ticker][0]
                    ):
                        sl = round(ltp * 1.01)     # 1% above
                        tgt = round(ltp * 0.98)    # 2% below
                        quantity = calculate_quantity(capital, tgt, sl, risk_pct=0.01, rr=2)
                        self.place_bracket_order(
                            self.instrument_list, ticker, "SELL", quantity, sl, tgt, exchange
                        )
                        print(
                            f"{Colors.RED}Sold {quantity} stocks of {ticker}{Colors.RESET}"
                        )
                else:
                    print(f"{Colors.YELLOW}NO TRADE : {ticker}{Colors.RESET}")
            except Exception as e:
                print(e)
