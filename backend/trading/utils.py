from typing import Dict, List, Optional, Union

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def token_lookup(
    ticker: str,
    instrument_list: List[Dict[str, Union[str, int]]],
    exchange: str = 'NSE',
) -> Optional[int]:
    for instrument in instrument_list:
        if (
            instrument['name'] == ticker
            and instrument['exch_seg'] == exchange
            and instrument['symbol'].split('-')[-1] == 'EQ'
        ):
            return instrument['token']
    return None


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'


def calculate_quantity(
    capital,
    entry_price,
    stop_loss_price,
    risk_pct=0.01,
    max_capital_usage_percent=100,
    min_sl_distance_pct=0.005,
):
    """
    Position size: min(risk-based qty, affordable qty by cash).
    min_sl_distance_pct floors per-share risk to avoid huge qty on tight SL.
    """
    if entry_price <= 0 or capital <= 0:
        return 0

    per_share_risk = abs(entry_price - stop_loss_price)
    min_risk = entry_price * min_sl_distance_pct
    per_share_risk = max(per_share_risk, min_risk)

    risk_per_trade = capital * risk_pct
    risk_qty = int(risk_per_trade // per_share_risk) if per_share_risk else 0

    deployable = capital * (max_capital_usage_percent / 100.0)
    cash_cap_qty = int(deployable // entry_price)

    quantity = max(0, min(risk_qty, cash_cap_qty))
    if risk_qty > cash_cap_qty and cash_cap_qty > 0:
        print(
            f'Quantity capped by capital: risk-based {risk_qty} -> {quantity} '
            f'({max_capital_usage_percent}% of Rs {capital})'
        )
    return quantity
