import datetime as dt
import json
import os
import time
import urllib
from typing import Dict, List, Optional, Union

import pandas as pd
from pyotp import TOTP
from SmartApi import SmartConnect

from src.trademaster.utils import token_lookup, calculate_quantity, log_trade_to_sheet


class AngelOneClient:
    def __init__(self) -> None:
        self.api_key: str = os.environ.get('API_KEY')
        self.client_id: str = os.environ.get('CLIENT_ID')
        self.password: str = os.environ.get('PASSWORD')
        self.token: str = os.environ.get('TOKEN')
        self.totp: str = TOTP(self.token).now()
        self.smart_api = None
        self.instrument_list = None

    def _initialize_smart_api(self) -> None:
        """Initialize the SmartAPI session."""
        if self.smart_api is None:
            self.smart_api = SmartConnect(self.api_key)
            self.smart_api.generateSession(
                self.client_id, self.password, self.totp
            )

    def _load_instrument_list(self) -> None:
        """Load the instrument list."""
        if self.instrument_list is None:
            instrument_url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
            response = urllib.request.urlopen(instrument_url)
            self.instrument_list: List[
                Dict[str, Union[str, int]]
            ] = json.loads(response.read())

    def quantity(self, ticker: str, exchange: str = 'NSE') -> int:
        """Calculate the quantity of stocks to buy/sell."""
        pos_size: int = 500
        ltp: Optional[float] = self.get_ltp(
            self.instrument_list, ticker, exchange
        )
        if ltp:
            return int(pos_size / ltp)
        return 0

    def get_ltp(
        self,
        instrument_list: List[Dict[str, Union[str, int]]],
        ticker: str,
        exchange: str = 'NSE',
    ) -> Optional[float]:
        """Get the Last Traded Price (LTP) of a given ticker."""
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
        """
        Fetch the available trading capital (cash balance) from SmartAPI.
        Returns:
            int: Available cash (rounded) that can be used for trading.
        """
        try:
            response = self.smart_api.rmsLimit()
            data = response.get("data", {})

            if not data:
                return 0

            # Available cash for trading (rounded)
            available_capital = float(data.get("availablecash", 0.0))
            return round(available_capital)   # ✅ round to nearest integer

        except Exception as e:
            print("Error fetching capital:", e)
            return 0
    
    def place_robo_order(
        self,
        instrument_list: List[Dict[str, Union[str, int]]],
        ticker: str,
        buy_sell: str,
        prices: List[float],
        quantity: int,
        exchange: str = 'NSE',
    ) -> Optional[Dict[str, Union[str, int]]]:
        """Place a robo order."""
        ltp: Optional[float] = self.get_ltp(instrument_list, ticker, exchange)
        if not ltp:
            return None
        limit_price =ltp + 1 if buy_sell == 'BUY' else ltp - 1
        if buy_sell == "SELL":
            stop_loss_price = limit_price * 1.02   # 1% above
        else:  # BUY
            stop_loss_price = limit_price * 0.98   # 1% below

        capital = self.get_trade_capital()
        quantity, target_price= calculate_quantity(capital, limit_price, stop_loss_price, risk_pct=0.01, rr=2)
        params: Dict[str, Union[str, int, float]] = {
            'variety': 'ROBO',
            'tradingsymbol': '{}-EQ'.format(ticker),
            'symboltoken': token_lookup(ticker, instrument_list),
            'transactiontype': buy_sell,
            'exchange': exchange,
            'ordertype': 'LIMIT',
            'producttype': 'BO',
            'price': limit_price,
            'duration': 'DAY',
            'stoploss': round(abs(stop_loss_price - limit_price)),
            'squareoff': round(abs(target_price - limit_price)),
            'quantity': quantity,
        }
        try:
            print('Payload of robo order:', params)
            response = self.smart_api.placeOrder(params)
            return response
        except Exception as e:
            print(e)
            return None

    def place_market_order(
    self,
    instrument_list: List[Dict[str, Union[str, int]]],
    ticker: str,
    buy_sell: str,
    quantity: int,
    exchange: str = "NSE",
    ) -> Optional[Dict[str, Union[str, int]]]:
        """Place a market order."""
        ltp: Optional[float] = self.get_ltp(instrument_list, ticker, exchange)
        if not ltp:
            return None

        params: Dict[str, Union[str, int, float]] = {
            "variety": "NORMAL",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token_lookup(ticker, instrument_list),
            "transactiontype": buy_sell,
            "exchange": exchange,
            "ordertype": "MARKET",
            "producttype": "INTRADAY",   # Can change to CNC if delivery
            "duration": "DAY",
            "price": ltp,                # For MARKET order, broker ignores price
            "squareoff": "0",
            "stoploss": "0",
            "quantity": quantity,
        }
        print('payload of market order', params)
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
        """Mimic Bracket Order: Entry + Stoploss + Target."""
        # Step 1: Place entry market order
        entry = self.place_market_order(instrument_list, ticker, buy_sell, quantity, exchange)
        if not entry:
            print("Entry order failed, aborting bracket order")
            return

        # Step 2: Opposite side stoploss
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
        print("=-=-=-=-=-=-")
        a = self.smart_api.placeOrderFullResponse(sl_order)
        print(a)
        # Step 3: Opposite side target
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
        b = self.smart_api.placeOrderFullResponse(target_order)
        print(b)
        print("Bracket order placed with Stoploss & Target")

    def get_open_orders(self) -> Optional[pd.DataFrame]:
        """Retrieve open orders."""
        try:
            response = self.smart_api.orderBook()
            df: pd.DataFrame = pd.DataFrame(response['data'])
            if len(df) > 0:
                return df[df['orderstatus'] == 'open']
            else:
                return None
        except Exception as e:
            print(e)
            return None
        
    def log_pnl(self):
        response = self.smart_api.position()
        data = response.get("data", [])
        if not data:
            print('No trades today')
            return
        trades = []
        date_str = dt.datetime.now().strftime("%Y-%m-%d")  # ✅ only date

        for item in data:
            trades.append({
                "date": date_str,
                "symbol": item.get("symbolname"),
                "pnl": item.get("pnl"),
                "quantity": item.get("sellqty")
            })

        # ✅ log to Google Sheet
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
        """Get historical data at 9:20 am with retry support."""
        hist_data_tickers: Dict[str, pd.DataFrame] = {}

        for ticker in tickers:
            token = token_lookup(ticker, instrument_list)
            if not token:
                print(f"⚠️ No token found for {ticker}, skipping.")
                continue

            params: Dict[str, Union[str, int]] = {
                'exchange': exchange,
                'symboltoken': token,
                'interval': interval,
                'fromdate': (
                    dt.date.today() - dt.timedelta(duration)
                ).strftime('%Y-%m-%d %H:%M'),
                'todate': dt.date.today().strftime('%Y-%m-%d') + ' 09:19',
            }

            df_data = pd.DataFrame()
            for attempt in range(1, retries + 1):
                try:
                    time.sleep(0.4)  # rate limiting
                    hist_data = self.smart_api.getCandleData(params)

                    if hist_data and hist_data.get("status") and hist_data.get("data"):
                        df_data = pd.DataFrame(
                            hist_data["data"],
                            columns=["date", "open", "high", "low", "close", "volume"],
                        )
                        df_data.set_index("date", inplace=True)
                        df_data.index = pd.to_datetime(df_data.index)
                        df_data.index = df_data.index.tz_localize(None)
                        df_data["gap"] = (
                            (df_data["open"] / df_data["close"].shift(1)) - 1
                        ) * 100
                        hist_data_tickers[ticker] = df_data
                        break  # success, exit retry loop
                    else:
                        print(f"⚠️ Empty response for {ticker} (attempt {attempt}/{retries})")
                except Exception as e:
                    print(f"⚠️ Error fetching {ticker} (attempt {attempt}/{retries}): {e}")

                time.sleep(delay * attempt)  # exponential backoff

            if df_data.empty:
                print(f"❌ Failed to fetch data for {ticker} after {retries} attempts.")

        return hist_data_tickers


    def place_oco_orders(
        self,
        instrument_list,
        ticker: str,
        buy_sell: str,
        ltp: float,
        quantity: int,
        exchange: str = 'NSE',
        stoploss_pct: float = 0.02, # Use a higher percentage
        target_pct: float = 0.04,   # Use a higher percentage
    ) -> Optional[Dict]:
        """
        Places a main order, followed by a stop-loss and a target order.
        Returns the main order's response or None on failure.
        """
        try:
            # 1. Calculate prices for SL and Target
            if buy_sell == 'BUY':
                sl_price = round(ltp * (1 - stoploss_pct), 2)
                target_price = round(ltp * (1 + target_pct), 2)
                sl_transaction_type = 'SELL'
                target_transaction_type = 'SELL'
            else: # SELL
                sl_price = round(ltp * (1 + stoploss_pct), 2)
                target_price = round(ltp * (1 - target_pct), 2)
                sl_transaction_type = 'BUY'
                target_transaction_type = 'BUY'

            # 2. Place the Main Order (as an intraday MARKET order for simplicity)
            main_order_params = {
                'variety': 'NORMAL',
                'tradingsymbol': f"{ticker}-EQ",
                'symboltoken': token_lookup(ticker, instrument_list),
                'transactiontype': buy_sell,
                'exchange': exchange,
                'ordertype': 'MARKET', # Or 'LIMIT' based on your strategy
                'producttype': 'MIS',
                'quantity': quantity,
            }
            print(f"Placing main {buy_sell} order for {ticker}: {main_order_params}")
            main_order_response = self.smart_api.placeOrder(main_order_params)
            print('respnse of main order : ', main_order_response)
            # Check if the main order was placed successfully
            if main_order_response and 'orderid' in main_order_response.get('data', {}):
                main_order_id = main_order_response['data']['orderid']

                # 3. Place the Stop-Loss Order
                sl_order_params = {
                    'variety': 'NORMAL',
                    'tradingsymbol': f"{ticker}-EQ",
                    'symboltoken': token_lookup(ticker, instrument_list),
                    'transactiontype': sl_transaction_type,
                    'exchange': exchange,
                    'ordertype': 'STOPLOSS_LIMIT',
                    'producttype': 'MIS',
                    'price': sl_price,
                    'triggerprice': sl_price, # Simplified trigger price
                    'quantity': quantity,
                }
                print(f"Placing SL order for {ticker}: {sl_order_params}")
                sl_order_response = self.smart_api.placeOrder(sl_order_params) # No need to store response for now
                print('respnse of sl_order : ', sl_order_response)
                # 4. Place the Target Order
                target_order_params = {
                    'variety': 'NORMAL',
                    'tradingsymbol': f"{ticker}-EQ",
                    'symboltoken': token_lookup(ticker, instrument_list),
                    'transactiontype': target_transaction_type,
                    'exchange': exchange,
                    'ordertype': 'LIMIT',
                    'producttype': 'MIS',
                    'price': target_price,
                    'quantity': quantity,
                }
                print(f"Placing Target order for {ticker}: {target_order_params}")
                target_order_response = self.smart_api.placeOrder(target_order_params) # No need to store response
                print('respnse of target_order : ', target_order_response)
                return main_order_response
            
            return None # Main order failed

        except Exception as e:
            print(f"Error in place_oco_orders: {e}")
            return None
        

    def cancel_pending_oco_order(self, orders: pd.DataFrame, ticker: str):
        """
        Monitors orders for a specific ticker and cancels the other leg of an OCO pair.
        """
        filled_order = orders[
            (orders['tradingsymbol'] == f"{ticker}-EQ") & (orders['status'].isin(['complete', 'executed']))
        ]
        
        open_order = orders[
            (orders['tradingsymbol'] == f"{ticker}-EQ") & (orders['status'] == 'open')
        ]
        
        if not filled_order.empty and not open_order.empty:
            order_to_cancel = open_order.iloc[0]
            try:
                print(f"Cancelling open order {order_to_cancel['orderid']} for {ticker}")
                self.smart_api.cancelOrder(
                    orderid=order_to_cancel['orderid'],
                    variety='NORMAL'
                )
                print(f"Successfully cancelled the other leg for {ticker}.")
            except Exception as e:
                print(f"Error cancelling order for {ticker}: {e}")