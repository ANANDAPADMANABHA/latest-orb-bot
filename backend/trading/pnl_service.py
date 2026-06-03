import datetime as dt
from typing import List, Tuple

from api.models import PnLRecord, Trade
from trading.position_utils import position_invested_capital

PNL_MATCH_EPSILON = 0.01


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


def normalize_symbol(raw: str) -> str:
    symbol = str(raw or '').upper().strip()
    if symbol.endswith('-EQ'):
        symbol = symbol[:-3]
    return symbol.strip()


def pnl_matches(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) < PNL_MATCH_EPSILON


def pnl_percent(pnl: float, invested_capital: float | None) -> float | None:
    if not invested_capital or invested_capital <= 0:
        return None
    return (float(pnl) / float(invested_capital)) * 100.0


def invested_capital_for_pnl_record(record: PnLRecord) -> float | None:
    """Stored capital, or estimate from bot Trade entry if missing."""
    if record.invested_capital and record.invested_capital > 0:
        return float(record.invested_capital)
    trade = (
        Trade.objects.filter(
            symbol=record.symbol,
            executed_at__date=record.date,
        )
        .order_by('-executed_at')
        .first()
    )
    if trade and trade.entry_price and trade.quantity:
        return float(trade.entry_price) * int(trade.quantity)
    return None


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

        raw_symbol = (
            item.get('tradingsymbol')
            or item.get('symbolname')
            or item.get('symbol')
            or ''
        )
        symbol = normalize_symbol(raw_symbol)
        if not symbol:
            continue

        qty = 0
        for key in ('buyqty', 'sellqty', 'quantity', 'netqty'):
            qty = max(qty, abs(_safe_int(item.get(key))))

        invested = position_invested_capital(item)
        trades.append({
            'date': today,
            'symbol': symbol,
            'quantity': qty,
            'pnl': pnl,
            'netqty': netqty,
            'invested_capital': invested if invested > 0 else None,
        })

    return trades


def merge_pnl_rows_by_symbol(rows: List[dict]) -> List[dict]:
    """One row per symbol; broker may send duplicate lines with the same P&L."""
    merged: dict[str, dict] = {}
    for row in rows:
        symbol = normalize_symbol(row['symbol'])
        pnl = float(row['pnl'])
        qty = int(row['quantity'])
        netqty = int(row.get('netqty', 0))

        if symbol not in merged:
            merged[symbol] = {**row, 'symbol': symbol}
            continue

        existing = merged[symbol]
        if pnl_matches(existing['pnl'], pnl):
            existing['quantity'] = max(int(existing['quantity']), qty)
            inv = row.get('invested_capital')
            if inv and (not existing.get('invested_capital') or inv > existing['invested_capital']):
                existing['invested_capital'] = inv
            continue

        existing['pnl'] = float(existing['pnl']) + pnl
        existing['quantity'] = max(int(existing['quantity']), qty)
        existing['netqty'] = netqty
        inv = row.get('invested_capital')
        if inv:
            existing['invested_capital'] = float(existing.get('invested_capital') or 0) + float(inv)

    return list(merged.values())


def _already_recorded(symbol: str, pnl: float, exclude_date: dt.date | None = None) -> bool:
    """True if this symbol+P&L was already saved on another day (stale broker row)."""
    qs = PnLRecord.objects.filter(symbol=symbol)
    if exclude_date:
        qs = qs.exclude(date=exclude_date)
    for row in qs.only('pnl'):
        if pnl_matches(row.pnl, pnl):
            return True
    return False


def dedupe_pnl_records_in_db() -> int:
    """Merge duplicate rows for the same date+symbol."""
    from django.db.models import Count

    removed = 0
    duplicate_groups = (
        PnLRecord.objects
        .values('date', 'symbol')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )
    for entry in duplicate_groups:
        rows = list(
            PnLRecord.objects
            .filter(date=entry['date'], symbol=entry['symbol'])
            .order_by('id')
        )
        if len(rows) < 2:
            continue

        keep = rows[0]
        pnls = [float(r.pnl) for r in rows]
        keep.pnl = pnls[0] if max(pnls) - min(pnls) < PNL_MATCH_EPSILON else sum(pnls)
        keep.quantity = max(r.quantity for r in rows)
        invested = [float(r.invested_capital) for r in rows if r.invested_capital]
        if invested:
            keep.invested_capital = max(invested)
        keep.save(update_fields=['pnl', 'quantity', 'invested_capital'])

        deleted, _ = (
            PnLRecord.objects
            .filter(date=entry['date'], symbol=entry['symbol'])
            .exclude(pk=keep.pk)
            .delete()
        )
        removed += deleted

    return removed


def dedupe_stale_cross_day_pnl() -> int:
    """
    Remove later copies when the same symbol+P&L appears on multiple days.
    Angel One often keeps yesterday's closed position in the book; sync re-saves it today.
    """
    removed = 0
    symbols = PnLRecord.objects.values_list('symbol', flat=True).distinct()

    for symbol in symbols:
        records = list(PnLRecord.objects.filter(symbol=symbol).order_by('date', 'id'))
        kept_pnls: list[float] = []

        for record in records:
            pnl = float(record.pnl)
            if any(pnl_matches(pnl, prev) for prev in kept_pnls):
                record.delete()
                removed += 1
                continue
            kept_pnls.append(pnl)

    return removed


def cleanup_pnl_records() -> int:
    return dedupe_pnl_records_in_db() + dedupe_stale_cross_day_pnl()


def record_pnl_trade(
    symbol: str,
    quantity: int,
    pnl: float,
    trade_date: dt.date | None = None,
    invested_capital: float | None = None,
) -> PnLRecord:
    """Upsert one symbol's P&L for a given day."""
    trade_date = trade_date or dt.date.today()
    symbol = normalize_symbol(symbol)
    defaults = {
        'quantity': int(quantity or 0),
        'pnl': float(pnl or 0),
    }
    if invested_capital and invested_capital > 0:
        defaults['invested_capital'] = float(invested_capital)
    obj, _ = PnLRecord.objects.update_or_create(
        date=trade_date,
        symbol=symbol,
        defaults=defaults,
    )
    return obj


def sync_pnl_records(client, replace_today: bool = True) -> Tuple[List[dict], int]:
    """
    Pull today's P&L from broker positions and save to PnLRecord.
    Skips rows already recorded on a prior day (stale closed positions).
    """
    rows = merge_pnl_rows_by_symbol(parse_position_rows(client.get_positions()))
    today = dt.date.today()

    if not rows:
        cleanup_pnl_records()
        return [], 0

    if replace_today:
        PnLRecord.objects.filter(date=today).delete()

    written = 0
    saved_rows = []
    for t in rows:
        symbol = t['symbol']
        pnl = float(t['pnl'])

        if _already_recorded(symbol, pnl, exclude_date=today):
            continue

        defaults = {
            'quantity': t['quantity'],
            'pnl': pnl,
        }
        if t.get('invested_capital'):
            defaults['invested_capital'] = float(t['invested_capital'])
        PnLRecord.objects.update_or_create(
            date=today,
            symbol=symbol,
            defaults=defaults,
        )
        saved_rows.append(t)
        written += 1

    cleanup_pnl_records()
    return saved_rows, written
