import datetime as dt
import json
import os
import time
import urllib
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import pytz
from pyotp import TOTP
from SmartApi import SmartConnect

from trading.utils import token_lookup, calculate_quantity

IST = pytz.timezone('Asia/Calcutta')


def orb_high_low_from_df(df: Optional[pd.DataFrame]) -> Optional[Tuple[float, float]]:
    if df is None or df.empty:
        return None
    return float(df['high'].iloc[-1]), float(df['low'].iloc[-1])


def orb_levels_from_intraday_df(df: Optional[pd.DataFrame]) -> Optional[Tuple[float, float]]:
    """Last 5m bar on or before 09:19 IST today (matches hist_data_0920 todate)."""
    if df is None or df.empty:
        return None
    today = dt.datetime.now(IST).date()
    cutoff = dt.datetime.combine(today, dt.time(9, 19))
    index_dates = pd.to_datetime(df.index).date
    pre = df[(index_dates == today) & (df.index <= cutoff)]
    return orb_high_low_from_df(pre if not pre.empty else None)


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

    def _extract_order_id(self, response) -> Optional[str]:
        if not response:
            return None
        if isinstance(response, dict):
            data = response.get('data') or {}
            if isinstance(data, dict):
                oid = data.get('orderid') or data.get('orderId')
                if oid:
                    return str(oid)
            oid = response.get('orderid') or response.get('orderId')
            if oid:
                return str(oid)
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
    ) -> Optional[Dict[str, Optional[str]]]:
        entry = self.place_market_order(instrument_list, ticker, buy_sell, quantity, exchange)
        if not entry:
            print("Entry order failed, aborting bracket order")
            return None

        entry_order_id = str(entry) if entry else None
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
        sl_response = self.smart_api.placeOrderFullResponse(sl_order)
        sl_order_id = self._extract_order_id(sl_response)

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
        target_response = self.smart_api.placeOrderFullResponse(target_order)
        target_order_id = self._extract_order_id(target_response)

        return {
            'entry_order_id': entry_order_id,
            'sl_order_id': sl_order_id,
            'target_order_id': target_order_id,
        }

    def modify_stop_loss_order(
        self,
        order_id: str,
        instrument_list,
        ticker: str,
        position_side: str,
        quantity: int,
        new_trigger: float,
        exchange: str = "NSE",
    ) -> Optional[str]:
        """
        Modify an open STOPLOSS order trigger price.
        Returns order id (unchanged or replaced) on success, None on failure.
        """
        opposite = "SELL" if position_side == "BUY" else "BUY"
        params = {
            "variety": "STOPLOSS",
            "orderid": order_id,
            "ordertype": "STOPLOSS_MARKET",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token_lookup(ticker, instrument_list),
            "transactiontype": opposite,
            "exchange": exchange,
            "producttype": "INTRADAY",
            "duration": "DAY",
            "triggerprice": new_trigger,
            "quantity": quantity,
            "price": "0",
        }
        try:
            response = self.smart_api.modifyOrder(params)
            if isinstance(response, dict) and response.get('status') is True:
                return order_id
            print(f"modifyOrder failed for {ticker}: {response}")
        except Exception as e:
            print(f"modifyOrder exception for {ticker}: {e}")

        return self._replace_stop_loss_order(
            order_id, instrument_list, ticker, position_side, quantity, new_trigger, exchange
        )

    def _replace_stop_loss_order(
        self,
        order_id: str,
        instrument_list,
        ticker: str,
        position_side: str,
        quantity: int,
        new_trigger: float,
        exchange: str = "NSE",
    ) -> Optional[str]:
        try:
            self.smart_api.cancelOrder(order_id, "STOPLOSS")
        except Exception as e:
            print(f"cancelOrder failed for {ticker}: {e}")
            return None

        opposite = "SELL" if position_side == "BUY" else "BUY"
        sl_order = {
            "variety": "STOPLOSS",
            "tradingsymbol": f"{ticker}-EQ",
            "symboltoken": token_lookup(ticker, instrument_list),
            "transactiontype": opposite,
            "exchange": exchange,
            "ordertype": "STOPLOSS_MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "triggerprice": new_trigger,
            "quantity": quantity,
        }
        try:
            response = self.smart_api.placeOrderFullResponse(sl_order)
            new_id = self._extract_order_id(response)
            if new_id:
                return new_id
            print(f"replace SL order failed for {ticker}: {response}")
        except Exception as e:
            print(f"replace SL order exception for {ticker}: {e}")
        return None

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
        from trading.pnl_service import parse_position_rows

        data = self.get_positions()
        trades = parse_position_rows(data)
        if not trades:
            print('No trades today')
            return []
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

    def _fetch_intraday_candle_df(
        self,
        ticker: str,
        instrument_list: List[Dict[str, Union[str, int]]],
        interval: str = 'FIVE_MINUTE',
        exchange: str = 'NSE',
        retries: int = 3,
        delay: float = 10.0,
        rate_limit_pause: bool = True,
    ) -> Optional[pd.DataFrame]:
        token = token_lookup(ticker, instrument_list)
        if not token:
            return None

        now = dt.datetime.now(IST)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        params = {
            'exchange': exchange,
            'symboltoken': token,
            'interval': interval,
            'fromdate': market_open.strftime('%Y-%m-%d %H:%M'),
            'todate': now.strftime('%Y-%m-%d %H:%M'),
        }
        for attempt in range(1, retries + 1):
            try:
                if rate_limit_pause:
                    time.sleep(0.4)
                hist_data = self.smart_api.getCandleData(params)
                if hist_data and hist_data.get('status') and hist_data.get('data'):
                    df_data = pd.DataFrame(
                        hist_data['data'],
                        columns=['date', 'open', 'high', 'low', 'close', 'volume'],
                    )
                    df_data.set_index('date', inplace=True)
                    df_data.index = pd.to_datetime(df_data.index)
                    df_data.index = df_data.index.tz_localize(None)
                    return df_data
            except Exception as e:
                print(
                    f'Error fetching intraday {ticker} '
                    f'(attempt {attempt}/{retries}): {e}'
                )
            time.sleep(delay * attempt)
        return None

    def get_intraday_candles(
        self,
        ticker: str,
        instrument_list: List[Dict[str, Union[str, int]]],
        interval: str = 'FIVE_MINUTE',
        exchange: str = 'NSE',
        retries: int = 3,
        delay: float = 10.0,
    ) -> Optional[pd.DataFrame]:
        return self._fetch_intraday_candle_df(
            ticker,
            instrument_list,
            interval=interval,
            exchange=exchange,
            retries=retries,
            delay=delay,
            rate_limit_pause=True,
        )

    def get_chart_data(
        self,
        ticker: str,
        instrument_list: List[Dict[str, Union[str, int]]],
        interval: str = 'FIVE_MINUTE',
        exchange: str = 'NSE',
        retries: int = 2,
        delay: float = 1.0,
    ) -> Optional[Tuple[pd.DataFrame, Optional[float], Optional[float]]]:
        df = self._fetch_intraday_candle_df(
            ticker,
            instrument_list,
            interval=interval,
            exchange=exchange,
            retries=retries,
            delay=delay,
            rate_limit_pause=False,
        )
        if df is None or df.empty:
            return None
        levels = orb_levels_from_intraday_df(df)
        if levels:
            return df, levels[0], levels[1]
        return df, None, None

    def ensure_feed_token(self) -> None:
        """Refresh feed token via refresh token when WebSocket auth may be stale."""
        self._initialize_smart_api()
        if self.smart_api.feed_token:
            return
        refresh = getattr(self.smart_api, 'refresh_token', None) or ''
        if not refresh:
            raise RuntimeError('Angel One feed token missing; re-login required.')
        self.smart_api.generateToken(refresh)
        if not self.smart_api.feed_token:
            raise RuntimeError('Angel One feed token refresh failed.')

    def get_websocket_credentials(self) -> Dict[str, str]:
        """JWT, feed token, and client code for SmartAPI WebSocket v2."""
        self._initialize_smart_api()
        self.ensure_feed_token()
        jwt = self.smart_api.access_token or ''
        if jwt and not jwt.startswith('Bearer '):
            jwt = f'Bearer {jwt}'
        client_code = getattr(self.smart_api, 'userId', None) or self.client_id
        feed_token = self.smart_api.feed_token or ''
        if not feed_token:
            raise RuntimeError('Angel One feed token missing; re-login required.')
        return {
            'auth_token': jwt,
            'api_key': self.api_key,
            'client_code': str(client_code),
            'feed_token': str(feed_token),
        }

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
            if not isinstance(response, dict):
                print(f'orderBook unexpected response type: {type(response)}')
                return []
            api_status = response.get('status')
            if api_status not in (True, 'success', 'SUCCESS'):
                print(
                    f"orderBook API error: {response.get('message')} "
                    f"({response.get('errorcode', '')})"
                )
                return []
            data = response.get('data')
            if isinstance(data, list):
                return data
            if data in (None, '', []):
                return []
            print(f'orderBook unexpected data: {type(data)}')
            return []
        except Exception as e:
            print(f"Error fetching order book: {e}")
            return []

    @staticmethod
    def _is_cancellable_order(order: dict) -> bool:
        from trading.order_utils import is_pending_order

        return is_pending_order(order)

    @staticmethod
    def _open_position_bases(positions: pd.DataFrame) -> set:
        """Equity bases (e.g. TATASTEEL) with non-zero net quantity."""
        from trading.position_utils import equity_base_symbol, net_position_qty, position_tradingsymbol

        open_bases: set = set()
        if positions.empty:
            return open_bases
        for _, row in positions.iterrows():
            if net_position_qty(row) == 0:
                continue
            sym = position_tradingsymbol(row)
            if sym:
                open_bases.add(equity_base_symbol(sym))
        return open_bases

    def _cancel_single_order(self, order: dict) -> tuple[bool, str | None]:
        from trading.order_utils import order_id_from_order, order_variety

        order_id = order_id_from_order(order)
        if not order_id:
            return False, 'missing order id'

        varieties: list[str] = []
        primary = order_variety(order)
        if primary:
            varieties.append(primary)
        for extra in ('NORMAL', 'STOPLOSS', 'ROBO', 'AMO'):
            if extra not in varieties:
                varieties.append(extra)

        last_error = None
        for var in varieties:
            try:
                response = self.smart_api.cancelOrder(order_id, var)
                if isinstance(response, dict):
                    if response.get('status') is True:
                        return True, None
                    msg = response.get('message') or response.get('errorcode') or str(response)
                    last_error = str(msg)
                else:
                    return True, None
            except Exception as e:
                last_error = str(e)
        return False, last_error

    def cancel_orphan_exit_orders(
        self,
        positions: pd.DataFrame,
        force_symbols: Optional[List[str]] = None,
    ) -> dict:
        """
        Cancel pending SL/target orders when the position is flat.
        Bracket legs are separate orders — Angel One does not auto-cancel the other leg.
        """
        from trading.order_utils import (
            is_pending_order,
            order_id_from_order,
            order_status_values,
            unfilled_order_qty,
        )
        from trading.position_utils import equity_base_symbol, normalize_tradingsymbol

        force_bases = {
            equity_base_symbol(s) for s in (force_symbols or []) if str(s).strip()
        }
        open_bases = self._open_position_bases(positions)
        order_book = self.get_order_book()

        summary = {
            'cancelled': [],
            'errors': [],
            'skipped_open_position': [f'{b}-EQ' for b in sorted(open_bases)],
            'pending_found': [],
            'order_book_count': len(order_book),
        }

        for order in order_book:
            if not is_pending_order(order):
                continue
            raw_sym = (
                order.get('tradingsymbol')
                or order.get('tradingSymbol')
                or order.get('symbol')
                or ''
            )
            sym = normalize_tradingsymbol(str(raw_sym))
            if not sym:
                continue
            base = equity_base_symbol(sym)
            oid = order_id_from_order(order)

            summary['pending_found'].append({
                'order_id': oid,
                'tradingsymbol': sym,
                'status': order.get('status'),
                'orderstatus': order.get('orderstatus'),
                'unfilled': unfilled_order_qty(order),
                'statuses': order_status_values(order),
                'variety': order.get('variety'),
            })

            if base in open_bases and base not in force_bases:
                continue

            if not oid:
                summary['errors'].append({'order_id': None, 'error': 'missing order id'})
                continue

            ok, err = self._cancel_single_order(order)
            if ok:
                summary['cancelled'].append(str(oid))
                print(f'Cancelled pending order {oid} for {sym}')
            elif err:
                summary['errors'].append({'order_id': str(oid), 'error': err})

        self._cancel_managed_exit_legs_for_flat_positions(positions, summary)

        print(
            f'Orphan order scan: book={len(order_book)} pending={len(summary["pending_found"])} '
            f'open_bases={sorted(open_bases)} force={sorted(force_bases)} '
            f'cancelled={summary["cancelled"]} errors={summary["errors"]}'
        )
        return summary

    def _cancel_managed_exit_legs_for_flat_positions(
        self, positions: pd.DataFrame, summary: dict
    ) -> None:
        from api.models import ManagedPosition

        open_bases = self._open_position_bases(positions)

        for mp in ManagedPosition.objects.filter(is_active=True):
            if mp.symbol.upper() in open_bases:
                continue
            from trading.position_utils import normalize_tradingsymbol

            tradingsymbol = normalize_tradingsymbol(mp.symbol)
            for order_id in (mp.target_order_id, mp.sl_order_id):
                if not order_id:
                    continue
                order = self._find_order_by_id(order_id)
                if order and self._is_cancellable_order(order):
                    ok, err = self._cancel_single_order(order)
                    if ok:
                        summary['cancelled'].append(str(order_id))
                        print(f'Cancelled managed leg {order_id} for {mp.symbol}')
                    elif err:
                        summary['errors'].append({'order_id': str(order_id), 'error': err})
            mp.is_active = False
            mp.save(update_fields=['is_active'])

    def _find_order_by_id(self, order_id: str) -> Optional[dict]:
        oid = str(order_id).strip()
        for order in self.get_order_book():
            book_id = str(order.get('orderid') or order.get('orderId') or '')
            if book_id == oid:
                return order
        return None

    def cancel_orders_for_symbol(self, tradingsymbol: str) -> dict:
        """Cancel open/pending orders for a symbol. Returns cancelled ids and errors."""
        from trading.position_utils import normalize_tradingsymbol, symbols_match

        symbol_key = normalize_tradingsymbol(tradingsymbol)
        cancelled = []
        errors = []

        from trading.order_utils import order_id_from_order

        for order in self.get_order_book():
            order_sym = str(
                order.get('tradingsymbol')
                or order.get('tradingSymbol')
                or order.get('symbol')
                or ''
            )
            if not symbols_match(order_sym, symbol_key):
                continue
            if not self._is_cancellable_order(order):
                continue
            order_id = order_id_from_order(order)
            ok, err = self._cancel_single_order(order)
            if ok:
                cancelled.append(str(order_id))
            else:
                errors.append({'order_id': str(order_id), 'error': err or 'cancel failed'})

        return {'cancelled_orders': cancelled, 'cancel_errors': errors}

    def exit_position(self, tradingsymbol: str, exchange: str = 'NSE') -> dict:
        """
        Cancel pending orders for symbol, then square off open position at market.
        """
        symbol_key = tradingsymbol.upper().strip()
        if not symbol_key.endswith('-EQ'):
            symbol_key = f'{symbol_key}-EQ'

        self._load_instrument_list()

        positions = self.get_positions()
        position_row = None
        for row in positions:
            if str(row.get('tradingsymbol', '')).upper() == symbol_key:
                position_row = row
                break

        if not position_row:
            raise ValueError(f'No position found for {symbol_key}')

        try:
            netqty = int(float(position_row.get('netqty') or position_row.get('quantity') or 0))
        except (TypeError, ValueError):
            netqty = 0

        if netqty == 0:
            raise ValueError(f'No open quantity for {symbol_key}')

        ticker = symbol_key.replace('-EQ', '')
        realized_pnl = float(position_row.get('pnl') or 0)
        cancel_result = self.cancel_orders_for_symbol(symbol_key)

        exit_side = 'SELL' if netqty > 0 else 'BUY'
        qty = abs(netqty)

        square_off = {'placed': False, 'order_id': None, 'error': None}
        try:
            order_id = self.place_market_order(
                self.instrument_list, ticker, exit_side, qty, exchange
            )
            if order_id:
                square_off = {'placed': True, 'order_id': str(order_id), 'error': None}
            else:
                square_off = {
                    'placed': False,
                    'order_id': None,
                    'error': 'Market square-off order was not placed',
                }
        except Exception as e:
            square_off = {'placed': False, 'order_id': None, 'error': str(e)}

        return {
            'tradingsymbol': symbol_key,
            'ticker': ticker,
            'exit_side': exit_side,
            'quantity': qty,
            'realized_pnl': realized_pnl,
            'cancelled_orders': cancel_result['cancelled_orders'],
            'cancel_errors': cancel_result['cancel_errors'],
            'square_off': square_off,
        }
