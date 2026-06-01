"""Helpers for Angel One position rows."""


def _row_field(row, *keys):
    if row is None or not hasattr(row, 'get'):
        return None
    for key in keys:
        val = row.get(key)
        if val not in (None, ''):
            return val
    return None


def equity_base_symbol(tradingsymbol: str) -> str:
    """TATASTEEL-EQ and TATASTEEL both map to TATASTEEL."""
    sym = str(tradingsymbol or '').upper().strip()
    if sym.endswith('-EQ'):
        return sym[:-3]
    return sym


def normalize_tradingsymbol(tradingsymbol: str) -> str:
    base = equity_base_symbol(tradingsymbol)
    return f'{base}-EQ' if base else ''


def symbols_match(a: str, b: str) -> bool:
    return equity_base_symbol(a) == equity_base_symbol(b)


def net_position_qty(row) -> int:
    """
    Net open quantity for a position row.
    Do not use fill `quantity` — closed trades can still show qty 40 with netqty 0.
    """
    if row is None:
        return 0
    netqty = _row_field(row, 'netqty', 'netQty', 'NetQty')
    if netqty not in (None, ''):
        try:
            return int(float(netqty))
        except (TypeError, ValueError):
            pass
    try:
        buy = int(float(_row_field(row, 'buyqty', 'buyQty', 'BuyQty') or 0))
        sell = int(float(_row_field(row, 'sellqty', 'sellQty', 'SellQty') or 0))
        return buy - sell
    except (TypeError, ValueError):
        return 0


def position_tradingsymbol(row) -> str:
    if row is None:
        return ''
    raw = (
        _row_field(row, 'tradingsymbol', 'tradingSymbol', 'TradingSymbol')
        or _row_field(row, 'symbolname', 'symbolName', 'SymbolName')
        or _row_field(row, 'symbol', 'Symbol')
        or ''
    )
    return normalize_tradingsymbol(str(raw))
