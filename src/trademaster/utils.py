from typing import Dict, List, Optional, Union
import pandas as pd
import os
from datetime import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import CellFormat, Color, format_cell_ranges
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


def log_trade_to_sheets(sheet_name: str, worksheet_name: str, trades: list):
    """
    Append trade data into Google Sheet.
    
    trades: list of dicts with keys -> ['date', 'symbol', 'pnl']
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials_json = os.environ.get("GOOGLE_CREDS_JSON")
    credentials_dict = json.loads(credentials_json)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    
    client = gspread.authorize(credentials)
    sheet = client.open(sheet_name).worksheet(worksheet_name)
    
    # Append each trade as a new row
    for trade in trades:
        sheet.append_row([trade['date'], trade['symbol'],  trade['quantity'], trade['pnl']])
    print('log added for today in sheet')


def log_trade_to_sheet(sheet_name: str, worksheet_name: str, trades: list):
    """
    Append trade data into Google Sheet.
    Colors PnL column: green if positive, red if negative.
    
    trades: list of dicts with keys -> ['date', 'symbol', 'quantity', 'pnl']
    """
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials_json = os.environ.get("GOOGLE_CREDS_JSON")
    credentials_dict = json.loads(credentials_json)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    
    client = gspread.authorize(credentials)
    sheet = client.open(sheet_name).worksheet(worksheet_name)
    
    for trade in trades:
        # Append the row
        sheet.append_row([trade['date'], trade['symbol'], trade['quantity'], trade['pnl']])
        
        # Find the last row number
        last_row = len(sheet.get_all_values())
        
        # Convert PnL to float for checking
        pnl_value = float(trade['pnl'])
        
        # ✅ Define formatting (text color + light background)
        if pnl_value >= 0:
            fmt = CellFormat(
                backgroundColor=Color(0.85, 1, 0.85),  # light green
                textFormat={"foregroundColor": {"red": 0, "green": 0.5, "blue": 0}}
            )
        else:
            fmt = CellFormat(
                backgroundColor=Color(1, 0.85, 0.85),  # light red
                textFormat={"foregroundColor": {"red": 0.7, "green": 0, "blue": 0}}
            )
        
        # Apply formatting to only the PnL column (D → 4th column)
        format_cell_ranges(sheet, [("D{}".format(last_row), fmt)])
    
    print('log added for today in sheet')
