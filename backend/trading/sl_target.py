from typing import Optional, Tuple

STRATEGY_FIXED = 'fixed_percent'
STRATEGY_PREV_CANDLE = 'prev_candle'
STRATEGY_TRAILING = 'trailing_candle'

STAGE_INITIAL = 'initial'
STAGE_BREAKEVEN = 'breakeven'
STAGE_TRAILING = 'trailing'


def compute_sl_target(
    strategy: str,
    side: str,
    ltp: float,
    prev_low: float,
    prev_high: float,
) -> Optional[Tuple[float, float]]:
    """
    Compute stop-loss and target for a trade.

    side: 'BUY' (long) or 'SELL' (short)
    Returns (sl, tgt) or None if levels are invalid.
    """
    if ltp <= 0:
        return None

    if strategy == STRATEGY_TRAILING:
        if side == 'BUY':
            sl = round(prev_low)
            tgt = round(ltp * 1.05)
            if sl >= ltp or sl <= 0:
                return None
        elif side == 'SELL':
            sl = round(prev_high)
            tgt = round(ltp * 0.95)
            if sl <= ltp:
                return None
        else:
            return None
    elif strategy == STRATEGY_PREV_CANDLE:
        if side == 'BUY':
            sl = round(prev_low)
            tgt = round(ltp * 1.01)
            if sl >= ltp or sl <= 0:
                return None
        elif side == 'SELL':
            sl = round(prev_high)
            tgt = round(ltp * 0.99)
            if sl <= ltp:
                return None
        else:
            return None
    else:
        if side == 'BUY':
            sl = round(ltp * 0.99)
            tgt = round(ltp * 1.02)
        elif side == 'SELL':
            sl = round(ltp * 1.01)
            tgt = round(ltp * 0.98)
        else:
            return None

    if abs(ltp - sl) == 0:
        return None

    return sl, tgt


def compute_next_trailing_sl(
    side: str,
    entry: float,
    ltp: float,
    prev_low: float,
    prev_high: float,
    current_sl: float,
    initial_sl: float,
) -> Optional[Tuple[float, str]]:
    """
    Compute the next trailing stop level and stage.

    Returns (new_sl, stage) or None if no update needed.
    SL only ratchets in the protective direction.
    """
    if entry <= 0 or ltp <= 0:
        return None

    if side == 'BUY':
        if ltp >= entry * 1.02:
            candidate = round(max(current_sl, prev_low, initial_sl))
            stage = STAGE_TRAILING
        elif ltp >= entry * 1.01:
            candidate = round(max(current_sl, entry, initial_sl))
            stage = STAGE_BREAKEVEN
        else:
            candidate = round(max(current_sl, initial_sl))
            stage = STAGE_INITIAL

        if candidate <= current_sl:
            return None
        if candidate >= ltp:
            return None
        return candidate, stage

    if side == 'SELL':
        if ltp <= entry * 0.98:
            candidate = round(min(current_sl, prev_high, initial_sl))
            stage = STAGE_TRAILING
        elif ltp <= entry * 0.99:
            candidate = round(min(current_sl, entry, initial_sl))
            stage = STAGE_BREAKEVEN
        else:
            candidate = round(min(current_sl, initial_sl))
            stage = STAGE_INITIAL

        if candidate >= current_sl:
            return None
        if candidate <= ltp:
            return None
        return candidate, stage

    return None
