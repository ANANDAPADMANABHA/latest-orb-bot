"""Parse Chartink webhook payloads and sync the watchlist."""
from __future__ import annotations

import json
import os
import urllib.request
from typing import List, Tuple

from trading.utils import token_lookup


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name, str(default)).strip().lower()
    return raw in ('1', 'true', 'yes', 'on')


def _load_instrument_list() -> list:
    url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def parse_chartink_stocks(raw: str) -> List[str]:
    """Split Chartink comma-separated stocks string into normalized symbols."""
    if not raw:
        return []
    seen: set[str] = set()
    symbols: list[str] = []
    for part in str(raw).split(','):
        symbol = part.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _should_skip_symbol(symbol: str) -> str | None:
    """Return skip reason, or None if symbol passes basic filters."""
    if 'ETF' in symbol:
        return 'etf'
    if symbol.endswith('-RE') or '-RE' in symbol:
        return 'rights'
    if len(symbol) > 20:
        return 'too_long'
    return None


def filter_chartink_symbols(
    symbols: List[str],
    *,
    instrument_list: list | None = None,
) -> Tuple[List[str], List[dict]]:
    """
    Return (accepted, skipped_details).
    skipped_details: [{'symbol': 'X', 'reason': '...'}, ...]
    """
    skip_etf = _env_bool('CHARTINK_SKIP_ETF', True)
    instruments = instrument_list if instrument_list is not None else _load_instrument_list()

    accepted: list[str] = []
    skipped: list[dict] = []

    for symbol in symbols:
        basic = _should_skip_symbol(symbol)
        if basic:
            if basic == 'etf' and not skip_etf:
                pass
            else:
                skipped.append({'symbol': symbol, 'reason': basic})
                continue

        if token_lookup(symbol, instruments) is None:
            skipped.append({'symbol': symbol, 'reason': 'not_nse_eq'})
            continue

        accepted.append(symbol)

    return accepted, skipped


def replace_watchlist(symbols: List[str]) -> Tuple[List[str], List[dict]]:
    """Replace entire watchlist with accepted symbols. Returns (added, skipped)."""
    from api.models import WatchlistTicker

    accepted, skipped = filter_chartink_symbols(symbols)
    WatchlistTicker.objects.all().delete()
    if accepted:
        WatchlistTicker.objects.bulk_create(
            [WatchlistTicker(symbol=s, is_active=True) for s in accepted]
        )
    return accepted, skipped


def process_chartink_payload(payload: dict) -> dict:
    """
    Full Chartink webhook handling: stop bot, replace watchlist, start bot.
    Returns summary dict for HTTP response.
    """
    from trading.bot_control_service import BotStartError, start_bot, stop_running_bot

    scan_name = str(payload.get('scan_name') or '')
    alert_name = str(payload.get('alert_name') or '')
    triggered_at = str(payload.get('triggered_at') or '')
    raw_stocks = payload.get('stocks') or ''
    parsed = parse_chartink_stocks(raw_stocks)

    stop_running_bot()
    added, skipped = replace_watchlist(parsed)

    result = {
        'ok': len(added) > 0,
        'scan_name': scan_name,
        'alert_name': alert_name,
        'triggered_at': triggered_at,
        'symbols_received': len(parsed),
        'symbols_added': len(added),
        'symbols_skipped': len(skipped),
        'skipped': skipped[:20],
        'bot_started': False,
        'session_id': None,
        'error': None,
    }

    if not added:
        result['error'] = 'No valid NSE EQ symbols after filtering'
        return result

    try:
        start_payload = start_bot()
        result['bot_started'] = True
        result['session_id'] = start_payload.get('session_id')
        result['mode'] = start_payload.get('mode')
        if start_payload.get('warning'):
            result['warning'] = start_payload['warning']
    except BotStartError as exc:
        result['ok'] = False
        result['error'] = str(exc)

    return result
