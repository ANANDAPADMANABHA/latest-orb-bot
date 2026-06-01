"""Angel One order-book row helpers."""

from typing import List, Optional

TERMINAL_ORDER_STATUSES = frozenset({
    'complete', 'completed', 'cancelled', 'canceled', 'rejected', 'expired',
    'cancel', 'cancelled after market order',
})

FILLED_ORDER_STATUSES = frozenset({
    'complete', 'completed', 'executed', 'fully executed', 'trade confirmed',
})

PENDING_ORDER_STATUSES = frozenset({
    'open',
    'trigger pending',
    'open pending',
    'modify pending',
    'not modified',
    'after market order req received',
    'modify after market order req received',
    'amo open',
    'amo submitted',
    'put order req received',
    'validation pending',
    'confirm pending',
})


def _field(order: dict, *keys: str):
    for key in keys:
        val = order.get(key)
        if val not in (None, ''):
            return val
    return None


def order_status_values(order: dict) -> List[str]:
    """All status strings on an order row (Angel uses both status and orderstatus)."""
    values: List[str] = []
    for key in ('status', 'orderstatus', 'orderStatus'):
        raw = _field(order, key)
        if raw is None:
            continue
        s = str(raw).lower().strip()
        if s and s not in values:
            values.append(s)
    return values


def unfilled_order_qty(order: dict) -> int:
    """Shares still open on this order."""
    for key in (
        'unfilledshares', 'unfilledqty', 'UnfilledShares',
        'pendingqty', 'leavesqty', 'cancelsize',
    ):
        raw = _field(order, key)
        if raw in (None, ''):
            continue
        try:
            qty = int(float(raw))
            if qty > 0:
                return qty
        except (TypeError, ValueError):
            continue
    try:
        total = int(float(_field(order, 'quantity', 'Quantity') or 0))
        filled = int(float(
            _field(order, 'filledshares', 'filledquantity', 'FilledShares') or 0
        ))
        if total > filled:
            return total - filled
    except (TypeError, ValueError):
        pass
    return 0


def is_filled_order(order: dict) -> bool:
    """True when the order has executed (target/SL hit)."""
    statuses = order_status_values(order)
    if any(s in FILLED_ORDER_STATUSES for s in statuses):
        return True
    try:
        total = int(float(_field(order, 'quantity', 'Quantity') or 0))
        filled = int(float(
            _field(order, 'filledshares', 'filledquantity', 'FilledShares') or 0
        ))
        return total > 0 and filled >= total
    except (TypeError, ValueError):
        return False


def is_pending_order(order: dict) -> bool:
    """
    True if the order may still be live on the exchange.
    Uses status + orderstatus + unfilledshares (Angel One forum pattern).
    """
    if unfilled_order_qty(order) > 0:
        return True

    statuses = order_status_values(order)
    if not statuses:
        return False

    any_pending = False
    for status in statuses:
        if status in TERMINAL_ORDER_STATUSES:
            continue
        if status in PENDING_ORDER_STATUSES or status == 'open' or 'pending' in status:
            any_pending = True
        else:
            any_pending = True

    return any_pending


def order_id_from_order(order: dict) -> Optional[str]:
    oid = _field(order, 'orderid', 'orderId', 'OrderID')
    return str(oid).strip() if oid else None


def order_variety(order: dict) -> str:
    return str(_field(order, 'variety', 'Variety') or 'NORMAL').strip().upper()
