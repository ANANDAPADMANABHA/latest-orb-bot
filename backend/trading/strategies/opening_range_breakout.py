import datetime as dt
import time
import pytz
from typing import Dict, List, Optional

import pandas as pd

from trading.broker import AngelOneClient
from trading.sl_target import STRATEGY_TRAILING, compute_sl_target
from trading.trailing_stop import update_trailing_stops
from trading.utils import token_lookup, Colors, calculate_quantity


class OpeningRangeBreakout(AngelOneClient):

    def _record_trailing_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float,
        sl: float,
        order_ids: dict,
    ) -> None:
        from api.models import BotSession, ManagedPosition

        session = BotSession.objects.filter(status='running').order_by('-started_at').first()
        sl_order_id = order_ids.get('sl_order_id') or ''
        if not sl_order_id:
            print(f"Warning: no SL order id for trailing position {ticker}")
        ManagedPosition.objects.create(
            symbol=ticker,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            initial_sl=sl,
            current_sl=sl,
            sl_order_id=sl_order_id,
            target_order_id=order_ids.get('target_order_id') or '',
            trail_stage=ManagedPosition.STAGE_INITIAL,
            session=session,
        )

    def _place_trade(
        self,
        ticker: str,
        side: str,
        quantity: int,
        ltp: float,
        sl: float,
        tgt: float,
        sl_strategy: str,
        exchange: str,
    ) -> None:
        order_ids = self.place_bracket_order(
            self.instrument_list, ticker, side, quantity, sl, tgt, exchange
        )
        if not order_ids:
            return

        color = Colors.GREEN if side == 'BUY' else Colors.RED
        print(f"{color}{side} {quantity} x {ticker} SL={sl} TGT={tgt}{Colors.RESET}")

        if sl_strategy == STRATEGY_TRAILING:
            self._record_trailing_position(ticker, side, quantity, ltp, sl, order_ids)

    def orb_strat(
        self,
        tickers: List[str],
        hi_lo_prices: Dict[str, List[float]],
        positions: pd.DataFrame,
        open_orders: Optional[pd.DataFrame] = None,
        exchange: str = "NSE",
    ) -> None:
        IST = pytz.timezone("Asia/Kolkata")
        now_ist = dt.datetime.now(IST)
        capital = self.get_trade_capital()
        print(f'Current capital: {capital} Rs')

        from api.models import BotSettings
        bot_settings = BotSettings.get_singleton()
        sl_strategy = bot_settings.stop_loss_strategy
        risk_pct = bot_settings.risk_percent / 100.0
        print(f'Stop-loss strategy: {sl_strategy}')
        print(f'Risk per trade: {bot_settings.risk_percent}%')

        update_trailing_stops(self, positions, self.instrument_list, exchange)

        active_tickers = list(tickers)
        if not positions.empty:
            active_tickers = [
                i for i in active_tickers
                if i + "-EQ" not in positions["tradingsymbol"].to_list()
            ]
        if open_orders is not None and not open_orders.empty:
            active_tickers = [
                i for i in active_tickers
                if i + "-EQ" not in open_orders["tradingsymbol"].to_list()
            ]

        for ticker in active_tickers:
            time.sleep(0.4)
            params = {
                "exchange": exchange,
                "symboltoken": token_lookup(ticker, self.instrument_list),
                "interval": "FIVE_MINUTE",
                "fromdate": (now_ist - dt.timedelta(days=4)).strftime("%Y-%m-%d %H:%M"),
                "todate": now_ist.strftime("%Y-%m-%d %H:%M"),
            }
            try:
                hist_data = self.smart_api.getCandleData(params)
                df_data = pd.DataFrame(
                    hist_data["data"],
                    columns=["date", "open", "high", "low", "close", "volume"],
                )
                df_data.set_index("date", inplace=True)
                df_data.index = pd.to_datetime(df_data.index)
                df_data.index = df_data.index.tz_localize(None)
                df_data["avg_vol"] = df_data["volume"].rolling(10).mean().shift(1)

                volume_breakout = df_data["volume"].iloc[-2] >= df_data["avg_vol"].iloc[-2]
                if volume_breakout:
                    ltp: Optional[float] = self.get_ltp(self.instrument_list, ticker, exchange)
                    if not ltp:
                        continue

                    bullish = (
                        df_data["close"].iloc[-2] >= hi_lo_prices[ticker][0]
                        and df_data["low"].iloc[-2] >= hi_lo_prices[ticker][1]
                    )
                    bearish = (
                        df_data["close"].iloc[-2] <= hi_lo_prices[ticker][1]
                        and df_data["high"].iloc[-2] <= hi_lo_prices[ticker][0]
                    )

                    if bullish:
                        prev_low = float(df_data["low"].iloc[-2])
                        prev_high = float(df_data["high"].iloc[-2])
                        levels = compute_sl_target(
                            sl_strategy, 'BUY', ltp, prev_low, prev_high
                        )
                        if not levels:
                            print(f"Invalid SL/target for {ticker} (BUY), skipping")
                            continue
                        sl, tgt = levels
                        quantity = calculate_quantity(capital, ltp, sl, risk_pct=risk_pct)
                        if quantity:
                            self._place_trade(
                                ticker, 'BUY', quantity, ltp, sl, tgt, sl_strategy, exchange
                            )
                    elif bearish:
                        prev_low = float(df_data["low"].iloc[-2])
                        prev_high = float(df_data["high"].iloc[-2])
                        levels = compute_sl_target(
                            sl_strategy, 'SELL', ltp, prev_low, prev_high
                        )
                        if not levels:
                            print(f"Invalid SL/target for {ticker} (SELL), skipping")
                            continue
                        sl, tgt = levels
                        quantity = calculate_quantity(capital, ltp, sl, risk_pct=risk_pct)
                        if quantity:
                            self._place_trade(
                                ticker, 'SELL', quantity, ltp, sl, tgt, sl_strategy, exchange
                            )
                    else:
                        print(f"No breakout for {ticker}")
                else:
                    print(f"{Colors.YELLOW}NO TRADE: {ticker} — no volume breakout{Colors.RESET}")
            except Exception as e:
                print(f"Error in orb_strat for {ticker}: {e}")
