from typing import Dict, List, Optional, Union
import pandas as pd
import os
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
load_dotenv()


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


def get_stock_tickers(sheet_name: str, worksheet_name: str = 'Sheet1') -> list:
    # Define the scope
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

    # Add credentials
    credentials_json = os.environ.get("GOOGLE_CREDS_JSON")

    credentials_dict = json.loads(credentials_json)

    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    

    # Authorize the client
    client = gspread.authorize(credentials)

    # Open the spreadsheet
    sheet = client.open(sheet_name).worksheet(worksheet_name)
    # sheet = client.open_by_key("1XYxdlCobrQlM2OmyFbTsckDHWigvpj7mAJip2LrhnDw").worksheet("Sheet1")
    # Get all values from the first column
    tickers = sheet.col_values(1)

    # Optional: clean empty rows
    tickers = [t.strip().upper() for t in tickers if t.strip()]

    return tickers


def calculate_quantity(capital, entry_price, stop_loss_price, risk_pct=0.01, rr=2):
    risk_per_trade = capital * risk_pct
    per_share_risk = abs(entry_price - stop_loss_price)
    quantity = int(risk_per_trade // per_share_risk)
    
    # Target based on R:R
    if entry_price > stop_loss_price:  # BUY
        target_price = entry_price + (per_share_risk * rr)
    else:  # SELL
        target_price = entry_price - (per_share_risk * rr)
    
    return quantity, target_price