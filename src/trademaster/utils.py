from typing import Dict, List, Optional, Union
import pandas as pd
import os
from datetime import datetime

def token_lookup(
    ticker: str,
    instrument_list: List[Dict[str, Union[str, int]]],
    exchange: str = 'NSE',
) -> Optional[int]:
    """Lookup the token for a given ticker."""
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

def log_trade_to_csv(ticker, side, amount, filename='trade_log.csv'):
    """Logs a trade to a CSV file, including a default timestamp if one is not provided."""
    
    # Use the current date and time if trade_time is not provided

    trade_time = datetime.now()

    data = {
        'ticker': [ticker],
        'trade_time': [trade_time],
        'side': [side],
        'amount': [amount]
    }
    
    df = pd.DataFrame(data)
    
    # Check if file exists to decide whether to write headers
    if not os.path.isfile(filename):
        df.to_csv(filename, mode='a', header=True, index=False)
    else:
        df.to_csv(filename, mode='a', header=False, index=False)