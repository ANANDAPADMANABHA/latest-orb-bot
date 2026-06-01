import datetime as dt
import time
from typing import Set

import pandas as pd
import pytz

from api.models import ManagedPosition
from trading.sl_target import compute_next_trailing_sl
from trading.utils import token_lookup, Colors


def _open_position_symbols(positions: pd.DataFrame) -> Set[str]:
    if positions.empty:
        return set()
    symbols = set()
    for _, row in positions.iterrows():
        netqty = row.get('netqty') or row.get('quantity') or 0
        try:
            if int(float(netqty)) == 0:
                continue
        except (TypeError, ValueError):
            continue
        sym = row.get('symbolname') or row.get('tradingsymbol', '')
        if sym:
            symbols.add(str(sym).replace('-EQ', '').upper())
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
    active_symbols = _open_position_symbols(positions)
    managed = ManagedPosition.objects.filter(is_active=True)

    for mp in managed:
        if mp.symbol.upper() not in active_symbols:
            tradingsymbol = f'{mp.symbol.upper()}-EQ'
            result = client.cancel_orders_for_symbol(tradingsymbol)
            if result['cancelled_orders']:
                print(
                    f"Cancelled pending orders for {mp.symbol}: "
                    f"{result['cancelled_orders']}"
                )
            mp.is_active = False
            mp.save(update_fields=['is_active'])
            print(f"Trailing position closed: {mp.symbol}")
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
