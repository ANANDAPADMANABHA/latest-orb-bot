import datetime as dt
import time

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.models import WatchlistTicker
from trading.broker import IST
from trading.broker_cache import format_broker_error, get_angel_client

_CHARTS_CACHE_TTL_SECONDS = 60
# Trading days of intraday history to include in chart candles (0 = today only).
_CHART_LOOKBACK_DAYS = 30
_MAX_CHART_LOOKBACK_DAYS = 90
_charts_cache: dict = {}
_orb_cache: dict = {}


def _df_to_candles(df) -> list:
    if df is None or df.empty:
        return []
    candles = []
    for ts, row in df.iterrows():
        candles.append({
            'time': ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': int(row['volume']),
        })
    return candles


def _cache_key(symbols: list) -> str:
    today = dt.datetime.now(IST).date().isoformat()
    return f"{today}:{','.join(sorted(symbols))}"


def _fetch_symbol_market_rows(
    symbols: list, include_candles: bool = False, days_back: int = 0
) -> list:
    client = get_angel_client()
    client._load_instrument_list()
    instrument_list = client.instrument_list

    results = []
    for symbol in symbols:
        entry = {
            'symbol': symbol,
            'orb_high': None,
            'orb_low': None,
            'last_close': None,
            'error': None,
        }
        if include_candles:
            entry['candles'] = []
        try:
            chart = client.get_chart_data(
                symbol, instrument_list, days_back=days_back
            )
            if chart is None:
                entry['error'] = 'No intraday candle data'
            else:
                intraday, orb_high, orb_low = chart
                if orb_high is not None and orb_low is not None:
                    entry['orb_high'] = orb_high
                    entry['orb_low'] = orb_low
                else:
                    entry['error'] = (
                        'Could not compute ORB levels (no pre-9:20 data)'
                    )
                if intraday is not None and not intraday.empty:
                    entry['last_close'] = float(intraday['close'].iloc[-1])
                    if include_candles:
                        entry['candles'] = _df_to_candles(intraday)
                elif not entry['error']:
                    entry['error'] = 'No intraday candle data'
        except Exception as e:
            entry['error'] = str(e)

        results.append(entry)

    return results


def _fetch_watchlist_charts(symbols: list, days_back: int = 0) -> dict:
    return {
        'updated_at': dt.datetime.now(IST).isoformat(),
        'symbols': _fetch_symbol_market_rows(
            symbols, include_candles=True, days_back=days_back
        ),
    }


def _fetch_orb_snapshot(symbols: list) -> dict:
    return {
        'updated_at': dt.datetime.now(IST).isoformat(),
        'symbols': _fetch_symbol_market_rows(symbols, include_candles=False),
    }


@api_view(['GET'])
def charts_watchlist(request):
    """
    Intraday candles + ORB for watchlist. One Angel call per symbol.
    Cached 60s unless ?refresh=1. Live ticks via WebSocket /ws/charts/.
    """
    symbols_qs = (
        WatchlistTicker.objects.filter(is_active=True).order_by('symbol')
    )
    symbols = [t.symbol for t in symbols_qs]

    if not symbols:
        return Response({
            'updated_at': dt.datetime.now(IST).isoformat(),
            'symbols': [],
        })

    force_refresh = request.query_params.get('refresh') in ('1', 'true', 'yes')

    try:
        days_back = int(request.query_params.get('days', _CHART_LOOKBACK_DAYS))
    except (TypeError, ValueError):
        days_back = _CHART_LOOKBACK_DAYS
    days_back = max(0, min(days_back, _MAX_CHART_LOOKBACK_DAYS))

    key = f"{_cache_key(symbols)}:d{days_back}"
    now = time.time()

    if not force_refresh:
        cached = _charts_cache.get(key)
        if cached and now - cached['stored_at'] < _CHARTS_CACHE_TTL_SECONDS:
            return Response(cached['payload'])

    try:
        payload = _fetch_watchlist_charts(symbols, days_back=days_back)
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    _charts_cache[key] = {'stored_at': now, 'payload': payload}
    return Response(payload)


@api_view(['GET'])
def orb_watchlist(request):
    """
    ORB high/low + latest price for watchlist (no candle arrays).
    Cached 60s unless ?refresh=1.
    """
    symbols_qs = (
        WatchlistTicker.objects.filter(is_active=True).order_by('symbol')
    )
    symbols = [t.symbol for t in symbols_qs]

    if not symbols:
        return Response({
            'updated_at': dt.datetime.now(IST).isoformat(),
            'symbols': [],
        })

    force_refresh = request.query_params.get('refresh') in ('1', 'true', 'yes')
    key = f"orb:{_cache_key(symbols)}"
    now = time.time()

    if not force_refresh:
        cached = _orb_cache.get(key)
        if cached and now - cached['stored_at'] < _CHARTS_CACHE_TTL_SECONDS:
            return Response(cached['payload'])

    try:
        payload = _fetch_orb_snapshot(symbols)
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    _orb_cache[key] = {'stored_at': now, 'payload': payload}
    return Response(payload)
