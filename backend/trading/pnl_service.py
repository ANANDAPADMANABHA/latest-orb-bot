import datetime as dt
from typing import List, Tuple

from api.models import PnLRecord


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_position_rows(data: list) -> List[dict]:
    """
    Build P&L rows from Angel One position API.
    Includes closed intraday lines (netqty=0 but pnl set).
    """
    trades = []
    today = dt.date.today().isoformat()

    for item in data or []:
        pnl = _safe_float(item.get('pnl') or item.get('realisedpnl'))
        netqty = _safe_int(item.get('netqty') or item.get('quantity'))

        if abs(pnl) < 0.001 and netqty == 0:
            continue

        raw_symbol = item.get('symbolname') or item.get('tradingsymbol') or ''
        symbol = str(raw_symbol).upper().replace('-EQ', '').strip()
        if not symbol:
            continue

        qty = 0
        for key in ('buyqty', 'sellqty', 'quantity', 'netqty'):
            qty = max(qty, abs(_safe_int(item.get(key))))

        trades.append({
            'date': today,
            'symbol': symbol,
            'quantity': qty,
            'pnl': pnl,
        })

    return trades


def record_pnl_trade(
    symbol: str,
    quantity: int,
    pnl: float,
    trade_date: dt.date | None = None,
) -> PnLRecord:
    """Upsert one symbol's P&L for a given day."""
    trade_date = trade_date or dt.date.today()
    symbol = str(symbol).upper().replace('-EQ', '').strip()
    obj, _ = PnLRecord.objects.update_or_create(
        date=trade_date,
        symbol=symbol,
        defaults={
            'quantity': int(quantity or 0),
            'pnl': float(pnl or 0),
        },
    )
    return obj


def sync_pnl_records(client, replace_today: bool = True) -> Tuple[List[dict], int]:
    """
    Pull today's P&L from broker positions and save to PnLRecord.
    Returns (trade dicts, number of records written).
    """
    from trading.utils import log_trade_to_sheet

    rows = parse_position_rows(client.get_positions())
    today = dt.date.today()

    if not rows:
        return [], 0

    if replace_today:
        PnLRecord.objects.filter(date=today).delete()

    for t in rows:
        PnLRecord.objects.create(
            date=today,
            symbol=t['symbol'],
            quantity=t['quantity'],
            pnl=t['pnl'],
        )

    try:
        log_trade_to_sheet('trade-master', 'PnL', rows)
    except Exception as exc:
        print(f'Google Sheet P&L log skipped: {exc}')

    return rows, len(rows)
