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
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials_json = os.environ.get("GOOGLE_CREDS_JSON")
    credentials_dict = json.loads(credentials_json)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(credentials)
    sheet = client.open(sheet_name).worksheet(worksheet_name)
    tickers = sheet.col_values(1)
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    return tickers


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


def log_trade_to_sheet(sheet_name: str, worksheet_name: str, trades: list):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    credentials_json = os.environ.get("GOOGLE_CREDS_JSON")
    credentials_dict = json.loads(credentials_json)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(credentials)
    sheet = client.open(sheet_name).worksheet(worksheet_name)

    for trade in trades:
        sheet.append_row([trade['date'], trade['symbol'], trade['quantity'], trade['pnl']])
        last_row = len(sheet.get_all_values())
        pnl_value = float(trade['pnl'])
        if pnl_value >= 0:
            fmt = CellFormat(
                backgroundColor=Color(0.85, 1, 0.85),
                textFormat={"foregroundColor": {"red": 0, "green": 0.5, "blue": 0}}
            )
        else:
            fmt = CellFormat(
                backgroundColor=Color(1, 0.85, 0.85),
                textFormat={"foregroundColor": {"red": 0.7, "green": 0, "blue": 0}}
            )
        format_cell_ranges(sheet, [("D{}".format(last_row), fmt)])

    print('log added for today in sheet')
