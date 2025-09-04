from src.trademaster.utils import get_stock_tickers

ORB_TICKERS = get_stock_tickers(sheet_name='trade-master')
# TODO write down different list of stocks based on the strategies they work on and use it from here
# eg : if one of the orb stock is not working as expected or a new stock need to be added it should be added here
YRB_TICKERS = [
    'POWERGRID',
    'SBIN',
    'TATASTEEL',
    'HINDALCO',
    'UPL',
    'WIPRO',
    'NTPC',
    'COALINDIA',
]
