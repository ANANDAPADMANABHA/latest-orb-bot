"""
Angel One SmartAPI WebSocket v2 (market data) -> Django Channels broadcast.

One Angel WebSocket per process; library auto-retry disabled to avoid duplicate
connections that trigger rate limits.

See: https://smartapi.angelbroking.com/docs/WebSocket2
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import time
from typing import Dict, List, Optional

import pytz
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from trading.broker import IST
from trading.broker_cache import format_broker_error, get_angel_client, invalidate_angel_client
from trading.utils import token_lookup

logger = logging.getLogger(__name__)

CHANNEL_GROUP = 'charts_live'
NSE_CM = SmartWebSocketV2.NSE_CM
LTP_MODE = SmartWebSocketV2.LTP_MODE
SUBSCRIBE_CORRELATION_ID = 'tmcharts01'
STOP_GRACE_SECONDS = 45.0
MIN_RECONNECT_SECONDS = 15.0
MAX_RECONNECT_BACKOFF_SECONDS = 120.0


def _bar_open_time_utc(now_ist) -> int:
    minute = (now_ist.minute // 5) * 5
    bar = now_ist.replace(minute=minute, second=0, microsecond=0)
    return int(bar.timestamp())


def _ltp_to_rupees(raw: int) -> float:
    return float(raw) / 100.0


class _ChartWebSocket(SmartWebSocketV2):
    """Disable SmartAPI internal reconnect loop (we manage reconnect in the manager)."""

    def __init__(self, manager: 'MarketStreamManager', **kwargs):
        kwargs['max_retry_attempt'] = 0
        kwargs['retry_strategy'] = 0
        kwargs['retry_delay'] = 0
        super().__init__(**kwargs)
        self._manager = manager

    def _on_error(self, wsapp, error=None, *args, **kwargs):
        logger.warning('Angel chart WebSocket error: %s', error)
        self._manager._on_angel_connection_lost(str(error or 'error'))

    def _on_close(self, wsapp, *args, **kwargs):
        close_code = args[0] if len(args) > 0 else ''
        close_msg = args[1] if len(args) > 1 else ''
        logger.info('Angel chart WebSocket closed (%s %s)', close_code, close_msg)
        self._manager._on_angel_connection_lost('closed')


class MarketStreamManager:
    _lock = threading.Lock()
    _instance: Optional['MarketStreamManager'] = None

    def __init__(self) -> None:
        self._client_count = 0
        self._ws: Optional[_ChartWebSocket] = None
        self._thread: Optional[threading.Thread] = None
        self._token_to_symbol: Dict[str, str] = {}
        self._live_bars: Dict[str, dict] = {}
        self._subscribed_tokens: set[str] = set()
        self._stop_timer: Optional[threading.Timer] = None
        self._reconnect_timer: Optional[threading.Timer] = None
        self._reconnect_attempts = 0
        self._starting = False
        self._last_start_at = 0.0

    @classmethod
    def instance(cls) -> 'MarketStreamManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = MarketStreamManager()
            return cls._instance

    def register_client(self, symbols: List[str]) -> None:
        with self._lock:
            if self._stop_timer:
                self._stop_timer.cancel()
                self._stop_timer = None
            self._client_count += 1
            self._ensure_symbol_map(symbols)
            if not self._token_to_symbol:
                self._broadcast({
                    'type': 'status',
                    'message': 'no_tokens',
                    'detail': 'Could not resolve symbol tokens for WebSocket',
                })
                return
            if self._stream_is_active():
                self._notify_live()
            elif not self._starting:
                self._start_stream_locked(refresh_credentials=False)

    def unregister_client(self) -> None:
        with self._lock:
            self._client_count = max(0, self._client_count - 1)
            if self._client_count == 0:
                self._cancel_reconnect_timer()
                self._schedule_stop()

    def _schedule_stop(self) -> None:
        if self._stop_timer:
            self._stop_timer.cancel()

        def _do_stop():
            with self._lock:
                if self._client_count == 0:
                    self._stop_stream_locked()

        self._stop_timer = threading.Timer(STOP_GRACE_SECONDS, _do_stop)
        self._stop_timer.daemon = True
        self._stop_timer.start()

    def _ensure_symbol_map(self, symbols: List[str]) -> None:
        client = get_angel_client()
        client._load_instrument_list()
        for symbol in symbols:
            token = token_lookup(symbol, client.instrument_list)
            if token is not None:
                self._token_to_symbol[str(token).strip()] = symbol

    def _stream_is_active(self) -> bool:
        if not self._ws or not self._thread or not self._thread.is_alive():
            return False
        if getattr(self._ws, 'DISCONNECT_FLAG', True):
            return False
        return bool(self._subscribed_tokens)

    def _notify_live(self) -> None:
        self._broadcast({
            'type': 'status',
            'message': 'live',
            'symbols': list(self._token_to_symbol.values()),
        })

    def _get_credentials(self, refresh: bool) -> dict:
        if refresh:
            invalidate_angel_client()
        client = get_angel_client(force_refresh=refresh)
        client.ensure_feed_token()
        return client.get_websocket_credentials()

    def _start_stream_locked(self, refresh_credentials: bool = False) -> None:
        now = time.time()
        if now - self._last_start_at < MIN_RECONNECT_SECONDS and not refresh_credentials:
            logger.info('Skipping Angel WS start (cooldown)')
            return

        if self._stream_is_active():
            self._notify_live()
            return

        self._starting = True
        self._last_start_at = now
        self._stop_stream_locked(join_thread=False)

        try:
            creds = self._get_credentials(refresh=refresh_credentials)
        except Exception as exc:
            self._starting = False
            msg = format_broker_error(exc)
            logger.error('Angel WS credentials failed: %s', msg)
            self._broadcast({
                'type': 'status',
                'message': 'error',
                'detail': msg,
            })
            self._schedule_reconnect()
            return

        self._ws = _ChartWebSocket(
            manager=self,
            auth_token=creds['auth_token'],
            api_key=creds['api_key'],
            client_code=creds['client_code'],
            feed_token=creds['feed_token'],
        )
        self._ws.on_open = self._on_open
        self._ws.on_data = self._on_data
        self._ws.on_message = lambda _w, _m: None

        self._thread = threading.Thread(
            target=self._run_connect,
            name='angel-ws-v2',
            daemon=True,
        )
        self._thread.start()

    def _run_connect(self) -> None:
        try:
            if self._ws:
                self._ws.connect()
        except Exception as exc:
            logger.exception('Angel WS connect failed: %s', exc)
            self._on_angel_connection_lost(str(exc))
        finally:
            with self._lock:
                self._starting = False

    def _stop_stream_locked(self, join_thread: bool = True) -> None:
        self._cancel_reconnect_timer()
        if self._ws:
            try:
                self._ws.RESUBSCRIBE_FLAG = False
                self._ws.close_connection()
            except Exception:
                pass
        self._ws = None
        self._subscribed_tokens.clear()
        if join_thread and self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._starting = False

    def _on_open(self, _wsapp) -> None:
        with self._lock:
            self._reconnect_attempts = 0
            tokens = list(self._token_to_symbol.keys())
            if not tokens or not self._ws:
                return
            try:
                token_list = [{'exchangeType': NSE_CM, 'tokens': tokens}]
                self._ws.subscribe(SUBSCRIBE_CORRELATION_ID, LTP_MODE, token_list)
                self._subscribed_tokens.update(tokens)
            except Exception as exc:
                logger.exception('Angel WS subscribe failed: %s', exc)
                self._broadcast({
                    'type': 'status',
                    'message': 'error',
                    'detail': str(exc),
                })
                self._schedule_reconnect_locked(refresh_credentials=True)
                return
        self._notify_live()

    def _on_data(self, _wsapp, data: dict) -> None:
        if not isinstance(data, dict):
            return
        raw_token = str(data.get('token', '')).strip()
        symbol = self._token_to_symbol.get(raw_token)
        if not symbol and raw_token.isdigit():
            symbol = self._token_to_symbol.get(str(int(raw_token)))
        if not symbol:
            return
        raw_ltp = data.get('last_traded_price')
        if raw_ltp is None:
            return

        ltp = _ltp_to_rupees(int(raw_ltp))
        now_ist = dt.datetime.now(IST)
        bar_time = _bar_open_time_utc(now_ist)

        bar = self._live_bars.get(symbol)
        if not bar or bar.get('time') != bar_time:
            bar = {
                'time': bar_time,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
            }
        else:
            bar = {
                **bar,
                'high': max(bar['high'], ltp),
                'low': min(bar['low'], ltp),
                'close': ltp,
            }
        self._live_bars[symbol] = bar

        self._broadcast({
            'type': 'tick',
            'symbol': symbol,
            'ltp': ltp,
            'bar': bar,
        })

    def _on_angel_connection_lost(self, reason: str) -> None:
        with self._lock:
            self._subscribed_tokens.clear()
            self._broadcast({
                'type': 'status',
                'message': 'disconnected',
                'detail': reason,
            })
            if self._client_count > 0:
                self._schedule_reconnect_locked(
                    refresh_credentials=self._reconnect_attempts >= 1,
                )

    def _cancel_reconnect_timer(self) -> None:
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None

    def _schedule_reconnect(self) -> None:
        with self._lock:
            self._schedule_reconnect_locked(refresh_credentials=False)

    def _schedule_reconnect_locked(self, refresh_credentials: bool = False) -> None:
        if self._client_count <= 0 or self._starting:
            return
        if self._reconnect_timer:
            return

        self._reconnect_attempts += 1
        delay = min(
            MIN_RECONNECT_SECONDS * self._reconnect_attempts,
            MAX_RECONNECT_BACKOFF_SECONDS,
        )
        logger.info(
            'Scheduling Angel WS reconnect in %.0fs (attempt %s)',
            delay,
            self._reconnect_attempts,
        )
        self._broadcast({
            'type': 'status',
            'message': 'reconnecting',
            'detail': f'Retry in {int(delay)}s',
        })

        def _reconnect():
            with self._lock:
                self._reconnect_timer = None
                if self._client_count <= 0:
                    return
                if self._stream_is_active():
                    self._notify_live()
                    return
                self._start_stream_locked(refresh_credentials=refresh_credentials)

        self._reconnect_timer = threading.Timer(delay, _reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _broadcast(self, message: dict) -> None:
        layer = get_channel_layer()
        if not layer:
            return
        try:
            async_to_sync(layer.group_send)(
                CHANNEL_GROUP,
                {'type': 'chart_message', 'payload': message},
            )
        except Exception as exc:
            logger.warning('Channel broadcast failed: %s', exc)


def start_live_stream(symbols: List[str]) -> None:
    MarketStreamManager.instance().register_client(symbols)


def stop_live_stream() -> None:
    MarketStreamManager.instance().unregister_client()
