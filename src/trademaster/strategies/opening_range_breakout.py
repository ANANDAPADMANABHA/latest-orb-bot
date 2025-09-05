import datetime as dt
import time
from typing import Dict, List, Optional

import pandas as pd

from src.trademaster.broker import AngelOneClient
from src.trademaster.utils import token_lookup, Colors
from src.trademaster.utils import log_trade_to_csv


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
                if response and response.get("status"):
                    return True

                # check if failed due to cautionary listing
                if response and response.get("errorcode") == "AB4036":
                    print(f"⚠️ {ticker} is under cautionary listing. Placing MARKET order instead.")
                    market_resp = self.place_market_order(instrument_list, ticker, side, quantity)
                    print('response of place robo order' , response)
                    if market_resp and market_resp.get("status"):
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
        quantity = 3
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
                "symboltoken": token_lookup("WIPRO", self.instrument_list),
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

                print(
                    "current_volume: ",
                    df_data["volume"].iloc[-1],
                    "average volume: ",
                    df_data["avg_vol"].iloc[-1],
                )

                if df_data["volume"].iloc[-1] >= df_data["avg_vol"].iloc[-1]:
                    print("ALERT..............!")
                    print(
                        f"{Colors.GREEN}{ticker} has broken the average volume,{Colors.RESET}"
                    )
                    if (
                        df_data["close"].iloc[-1] >= hi_lo_prices[ticker][0]
                        and df_data["low"].iloc[-1] >= hi_lo_prices[ticker][1]
                    ):
                        if self.safe_place_robo_order(
                            self.instrument_list, ticker, "BUY", hi_lo_prices[ticker], quantity
                        ):
                            log_trade_to_csv(
                                ticker,
                                "BUY",
                                df_data["close"].iloc[-1],
                                filename="trade_log.csv",
                            )
                            print(
                                f"{Colors.GREEN}Bought {quantity} stocks of {ticker}{Colors.RESET}"
                            )
                    elif (
                        df_data["close"].iloc[-1] <= hi_lo_prices[ticker][1]
                        and df_data["high"].iloc[-1] <= hi_lo_prices[ticker][0]
                    ):
                        if self.safe_place_robo_order(
                            self.instrument_list, ticker, "SELL", hi_lo_prices[ticker], quantity
                        ):
                            log_trade_to_csv(
                                ticker,
                                "SELL",
                                df_data["close"].iloc[-1],
                                filename="trade_log.csv",
                            )
                            print(
                                f"{Colors.RED}Sold {quantity} stocks of {ticker}{Colors.RESET}"
                            )
                else:
                    print(f"{Colors.YELLOW}NO TRADE : {ticker}{Colors.RESET}")
            except Exception as e:
                print(e)
