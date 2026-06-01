import datetime as dt
import time
from typing import Set

import pandas as pd
import pytz

from api.models import ManagedPosition
from trading.sl_target import compute_next_trailing_sl
from trading.utils import token_lookup, Colors


def _open_position_symbols(positions: pd.DataFrame) -> Set[str]:
    from trading.position_utils import net_position_qty, position_tradingsymbol

    if positions.empty:
        return set()
    symbols = set()
    for _, row in positions.iterrows():
        if net_position_qty(row) == 0:
            continue
        sym = position_tradingsymbol(row)
        if sym:
            symbols.add(sym.replace('-EQ', '').upper())
    return symbols


def _fetch_prev_candle(client, ticker: str, instrument_list, exchange: str):
    IST = pytz.timezone('Asia/Kolkata')
    now_ist = dt.datetime.now(IST)
    params = {
        'exchange': exchange,
        'symboltoken': token_lookup(ticker, instrument_list),
        'interval': 'FIVE_MINUTE',
        'fromdate': (now_ist - dt.timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
        'todate': now_ist.strftime('%Y-%m-%d %H:%M'),
    }
    hist_data = client.smart_api.getCandleData(params)
    if not hist_data or not hist_data.get('data'):
        return None, None
    df = pd.DataFrame(
        hist_data['data'],
        columns=['date', 'open', 'high', 'low', 'close', 'volume'],
    )
    if len(df) < 2:
        return None, None
    return float(df['low'].iloc[-2]), float(df['high'].iloc[-2])


def update_trailing_stops(client, positions: pd.DataFrame, instrument_list, exchange: str = 'NSE') -> None:
    """Adjust SL orders for active trailing positions each bot loop."""
    from api.models import BotSettings
    from trading.sl_target import STRATEGY_TRAILING

    active_symbols = _open_position_symbols(positions)
    managed = ManagedPosition.objects.filter(is_active=True)
    settings = BotSettings.get_singleton()
    trail_sl = settings.stop_loss_strategy == STRATEGY_TRAILING

    for mp in managed:
        if mp.symbol.upper() not in active_symbols:
            # Do not cancel bracket legs here — cancel_orphan_exit_orders reconciles
            # one leg when the other fills; blanket cancel broke open positions.
            continue

        if not trail_sl:
            continue

        time.sleep(0.4)
        try:
            ltp = client.get_ltp(instrument_list, mp.symbol, exchange)
            if not ltp:
                continue

            prev_low, prev_high = _fetch_prev_candle(client, mp.symbol, instrument_list, exchange)
            if prev_low is None or prev_high is None:
                continue

            result = compute_next_trailing_sl(
                mp.side,
                mp.entry_price,
                ltp,
                prev_low,
                prev_high,
                mp.current_sl,
                mp.initial_sl,
            )
            if not result:
                continue

            new_sl, new_stage = result
            if not mp.sl_order_id:
                print(f"No SL order id for {mp.symbol}, skipping trailing update")
                continue

            updated_order_id = client.modify_stop_loss_order(
                mp.sl_order_id,
                instrument_list,
                mp.symbol,
                mp.side,
                mp.quantity,
                new_sl,
                exchange,
            )
            if not updated_order_id:
                print(f"Failed to update trailing SL for {mp.symbol}")
                continue

            mp.current_sl = new_sl
            mp.trail_stage = new_stage
            mp.sl_order_id = updated_order_id
            mp.save(update_fields=['current_sl', 'trail_stage', 'sl_order_id'])
            print(
                f"{Colors.GREEN}Trailing SL {mp.symbol}: {new_sl} ({new_stage}){Colors.RESET}"
            )
        except Exception as e:
            print(f"Error updating trailing stop for {mp.symbol}: {e}")
