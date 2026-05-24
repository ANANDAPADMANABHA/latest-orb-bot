import datetime as dt
import json
import os
import time
import urllib
from typing import Dict, List, Optional, Union

import pandas as pd
from pyotp import TOTP
from SmartApi import SmartConnect

from trading.utils import token_lookup, calculate_quantity, log_trade_to_sheet


class AngelOneClient:
    def __init__(self) -> None:
        self.api_key: str = self._env('API_KEY')
        self.client_id: str = self._env('CLIENT_ID')
        self.password: str = self._env('PASSWORD')
        self.token: str = self._env('TOKEN')
        self.smart_api = None
        self.instrument_list = None

    @staticmethod
    def _env(name: str) -> str:
        value = os.environ.get(name, '').strip().strip("'\"")
        return value

    def _initialize_smart_api(self) -> None:
        if self.smart_api is not None:
            return

        if not self.api_key:
            raise ValueError('API_KEY is missing. Set it in backend/.env')
        if not self.client_id or not self.password or not self.token:
            raise ValueError('CLIENT_ID, PASSWORD, and TOKEN must be set in backend/.env')

        self.smart_api = SmartConnect(self.api_key)
        totp = TOTP(self.token).now()
        session = self.smart_api.generateSession(self.client_id, self.password, totp)

        if not session or session.get('status') is not True:
            message = (session or {}).get('message', 'Unknown login error')
            error_code = (session or {}).get('errorcode') or (session or {}).get('errorCode', '')
            hint = (
                ' Check API_KEY in backend/.env matches your SmartAPI app '
                '(My Apps → API Key). For static-IP apps, run the bot from '
                f"registered IP {self._env('PRIMARY_STATIC_IP') or '(see Angel One portal)'}."
            )
            raise RuntimeError(f'Angel One login failed: {message} ({error_code}).{hint}')

        if not self.smart_api.access_token:
            raise RuntimeError('Angel One login did not return an access token.')

    def _load_instrument_list(self) -> None:
        if self.instrument_list is None:
            instrument_url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
            response = urllib.request.urlopen(instrument_url)
            self.instrument_list: List[Dict[str, Union[str, int]]] = json.loads(response.read())

    def get_ltp(
        self,
        instrument_list: List[Dict[str, Union[str, int]]],
        ticker: str,
        exchange: str = 'NSE',
    ) -> Optional[float]:
        params: Dict[str, Union[str, int]] = {
            'tradingsymbol': '{}-EQ'.format(ticker),
            'symboltoken': token_lookup(ticker, instrument_list),
        }
        try:
            response = self.smart_api.ltpData(
                exchange, params['tradingsymbol'], params['symboltoken']
            )
            if response:
                return response['data']['ltp']
        except Exception as e:
            print(f'Exception getltp {e}')
        return None

    def get_trade_capital(self) -> int:
        try:
            response = self.smart_api.rmsLimit()
            if not response or response.get('status') is not True:
                message = (response or {}).get('message', 'Failed to fetch capital')
                error_code = (response or {}).get('errorcode') or (response or {}).get('errorCode', '')
                raise RuntimeError(f'{message} ({error_code})')

            data = response.get("data", {})
            if not data:
                return 0
            available_capital = float(data.get("availablecash", 0.0))
            return round(available_capital)
        except Exception as e:
            print("Error fetching capital:", e)
            raise

    def place_market_order(
        self,
        instrument_list,
        ticker: str,
        buy_sell: str,
        quantity: int,
        exchange: str = "NSE",
    ) -> Optional[Dict]:
        ltp: Optional[float] = self.get_ltp(instrument_list, ticker, exchange)
        if not ltp:
            return None
        params = {
            "variety": "NORMAL",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token_lookup(ticker, instrument_list),
            "transactiontype": buy_sell,
            "exchange": exchange,
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": ltp,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": quantity,
        }
        try:
            response = self.smart_api.placeOrder(params)
            return response
        except Exception as e:
            print(f"Market order failed: {e}")
            return None

    def place_bracket_order(
        self,
        instrument_list,
        ticker: str,
        buy_sell: str,
        quantity: int,
        stoploss_price: float,
        target_price: float,
        exchange: str = "NSE",
    ) -> None:
        entry = self.place_market_order(instrument_list, ticker, buy_sell, quantity, exchange)
        if not entry:
            print("Entry order failed, aborting bracket order")
            return

        opposite = "SELL" if buy_sell == "BUY" else "BUY"
        sl_order = {
            "variety": "STOPLOSS",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token_lookup(ticker, instrument_list),
            "transactiontype": opposite,
            "exchange": exchange,
            "ordertype": "STOPLOSS_MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "triggerprice": stoploss_price,
            "quantity": quantity,
        }
        self.smart_api.placeOrderFullResponse(sl_order)

        target_order = {
            "variety": "NORMAL",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token_lookup(ticker, instrument_list),
            "transactiontype": opposite,
            "exchange": exchange,
            "ordertype": "LIMIT",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": target_price,
            "quantity": quantity,
        }
        self.smart_api.placeOrderFullResponse(target_order)

    def get_open_orders(self) -> Optional[pd.DataFrame]:
        try:
            response = self.smart_api.orderBook()
            df: pd.DataFrame = pd.DataFrame(response['data'])
            if len(df) > 0:
                return df[df['orderstatus'] == 'open']
            return None
        except Exception as e:
            print(e)
            return None

    def log_pnl(self):
        response = self.smart_api.position()
        data = response.get("data", [])
        if not data:
            print('No trades today')
            return []
        trades = []
        date_str = dt.datetime.now().strftime("%Y-%m-%d")
        for item in data:
            trades.append({
                "date": date_str,
                "symbol": item.get("symbolname"),
                "pnl": item.get("pnl"),
                "quantity": item.get("sellqty"),
            })
        log_trade_to_sheet("trade-master", "PnL", trades)
        return trades

    def hist_data_0920(
        self,
        tickers: List[str],
        duration: int,
        interval: str,
        instrument_list: List[Dict[str, Union[str, int]]],
        exchange: str = 'NSE',
        retries: int = 5,
        delay: float = 10.0,
    ) -> Dict[str, pd.DataFrame]:
        hist_data_tickers: Dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            token = token_lookup(ticker, instrument_list)
            if not token:
                continue
            params = {
                'exchange': exchange,
                'symboltoken': token,
                'interval': interval,
                'fromdate': (dt.date.today() - dt.timedelta(duration)).strftime('%Y-%m-%d %H:%M'),
                'todate': dt.date.today().strftime('%Y-%m-%d') + ' 09:19',
            }
            df_data = pd.DataFrame()
            for attempt in range(1, retries + 1):
                try:
                    time.sleep(0.4)
                    hist_data = self.smart_api.getCandleData(params)
                    if hist_data and hist_data.get("status") and hist_data.get("data"):
                        df_data = pd.DataFrame(
                            hist_data["data"],
                            columns=["date", "open", "high", "low", "close", "volume"],
                        )
                        df_data.set_index("date", inplace=True)
                        df_data.index = pd.to_datetime(df_data.index)
                        df_data.index = df_data.index.tz_localize(None)
                        df_data["gap"] = ((df_data["open"] / df_data["close"].shift(1)) - 1) * 100
                        hist_data_tickers[ticker] = df_data
                        break
                except Exception as e:
                    print(f"Error fetching {ticker} (attempt {attempt}/{retries}): {e}")
                time.sleep(delay * attempt)
        return hist_data_tickers

    def get_positions(self) -> List[Dict]:
        try:
            response = self.smart_api.position()
            return response.get("data", []) or []
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def get_order_book(self) -> List[Dict]:
        try:
            response = self.smart_api.orderBook()
            return response.get("data", []) or []
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return []
