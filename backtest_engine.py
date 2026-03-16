import os
import pandas as pd
from datetime import datetime, time, timedelta
from typing import List, Dict, Optional

from gann_fetcher import GannFetcher
from strategy_calculator import StrategyCalculator
import MetaTrader5 as mt5


class BacktestEngine:
    """
    Backtests the Gann 15min scalping strategy on historical data
    """

    def __init__(self, initial_fund: float, initial_risk_percent: float, pair: str):
        self.initial_fund = initial_fund
        self.current_fund = initial_fund
        self.initial_risk_percent = initial_risk_percent
        self.current_risk_percent = initial_risk_percent
        self.pair = pair

        self.trades: List[Dict] = []
        self.max_drawdown = 0.0
        self.equity_high = initial_fund

        # Session windows (IST)
        self.sessions = [
            {
                "name": "Session 1",
                "mark_start": time(5, 30),
                "mark_end": time(11, 0),
                "trade_end": time(11, 0),
            },
            {
                "name": "Session 2",
                "mark_start": time(13, 0),
                "mark_end": time(18, 0),
                "trade_end": time(18, 0),
            },
            {
                "name": "Session 3",
                "mark_start": time(19, 0),
                "mark_end": time(0, 30),
                "trade_end": time(0, 30),
            },
        ]

        self.total_trades = 0
        self.win_rate = 0.0

    # ------------------ SESSION & MARKING ------------------

    def _get_session_df(self, df: pd.DataFrame, session: Dict, day: datetime) -> pd.DataFrame:
        """
        Filter candles for a given day + session window (IST)
        """
        start_dt = datetime.combine(day.date(), session["mark_start"])
        end_dt = datetime.combine(day.date(), session["mark_end"])

        # Special case: session passing midnight (e.g., 19:00 - 00:30)
        if session["mark_end"] < session["mark_start"]:
            end_dt += timedelta(days=1)

        mask = (df["time"] >= start_dt) & (df["time"] <= end_dt)
        return df.loc[mask].copy()

    def _find_marking_candles(self, df: pd.DataFrame, session: Dict) -> Optional[Dict]:
        """
        Marking using IST candles from CSV (datetime already in IST):

        Session 1:
        - Use two exact 15m candles: 05:30 and 05:45
        - 30-min range = max(high of both), min(low of both)

        Session 2:
        - Use exact 13:00 15m candle

        Session 3:
        - Use exact 19:00 15m candle
        """
        if df.empty:
            return None

        df = df.sort_values("time").reset_index(drop=True)
        day_date = df["time"].dt.date.iloc[0]

        if session["name"] == "Session 1":
            t1 = datetime.combine(day_date, time(5, 30))
            t2 = datetime.combine(day_date, time(5, 45))

            c1 = df[df["time"] == t1]
            c2 = df[df["time"] == t2]

            if c1.empty or c2.empty:
                print(f"  -> Session 1: missing 05:30 or 05:45 IST candle")
                return None

            period_df = pd.concat([c1, c2])

        elif session["name"] == "Session 2":
            t = datetime.combine(day_date, time(13, 0))
            period_df = df[df["time"] == t]
            if period_df.empty:
                print(f"  -> Session 2: missing 13:00 IST candle")
                return None

        else:  # Session 3
            t = datetime.combine(day_date, time(19, 0))
            period_df = df[df["time"] == t]
            if period_df.empty:
                print(f"  -> Session 3: missing 19:00 IST candle")
                return None

        marked_high = period_df["high"].max()
        marked_low = period_df["low"].min()
        start_idx = period_df.index.min()
        end_idx = period_df.index.max()

        print(
            f"  -> {session['name']} IST: H={marked_high:.5f}, "
            f"L={marked_low:.5f} (range {marked_high - marked_low:.5f})"
        )

        return {
            "high": marked_high,
            "low": marked_low,
            "high_idx": start_idx,
            "low_idx": end_idx,
            "start_idx": start_idx,
            "end_idx": end_idx,
        }

    # ------------------ BREAKOUT / ENTRY / TRADE ------------------

    def detect_breakout(
        self,
        df: pd.DataFrame,
        marked: Dict,
        start_idx: int,
        session: Dict,
    ) -> Optional[Dict]:
        """
        Detect breakout AFTER marking candles within this session df.
        Breakout rule (close-based):
          - BUY BO  : candle close > marked_high  -> input = candle high
          - SELL BO : candle close < marked_low   -> input = candle low
        """
        if df.empty:
            return None

        high_level = marked["high"]
        low_level = marked["low"]

        idx = start_idx
        while idx < len(df):
            row = df.iloc[idx]
            close = row["close"]
            high = row["high"]
            low = row["low"]

            # Breakout upwards (close above marked high)
            if close > high_level:
                return {
                    "side": "B",
                    "breakout_time": row["time"],
                    "input_price": high,
                    "index": idx,
                }

            # Breakout downwards (close below marked low)
            if close < low_level:
                return {
                    "side": "S",
                    "breakout_time": row["time"],
                    "input_price": low,
                    "index": idx,
                }

            idx += 1

        return None

    def wait_for_entry(
        self,
        df: pd.DataFrame,
        setup: Dict,
        breakout_time: datetime,
        session: Dict,
    ) -> Optional[Dict]:
        """
        Wait for price to touch entry level AFTER breakout (within this session).
        Entry rule:
          BUY  -> candle high >= entry, fill = max(entry, open)
          SELL -> candle low  <= entry, fill = min(entry, open)
        """
        entry_price = setup["entry"]
        side = setup["side"]

        trade_end = session["trade_end"]

        # Start from first candle strictly after breakout_time
        idx = 0
        while idx < len(df) and df.iloc[idx]["time"] <= breakout_time:
            idx += 1

        while idx < len(df):
            row = df.iloc[idx]
            row_time: datetime = row["time"]

            end_dt = datetime.combine(row_time.date(), trade_end)
            if trade_end < session["mark_start"]:
                end_dt += timedelta(days=1)

            if row_time > end_dt:
                break

            high = row["high"]
            low = row["low"]
            open_price = row["open"]

            if side == "B":
                if high >= entry_price:
                    actual_entry = max(entry_price, open_price)
                    return {
                        "entry_idx": idx,
                        "entry_time": row_time,
                        "actual_entry": actual_entry,
                    }
            else:
                if low <= entry_price:
                    actual_entry = min(entry_price, open_price)
                    return {
                        "entry_idx": idx,
                        "entry_time": row_time,
                        "actual_entry": actual_entry,
                    }

            idx += 1

        # Never touched entry AFTER breakout
        return None

    def simulate_trade(
        self,
        df: pd.DataFrame,
        setup: Dict,
        entry_idx: int,
        session: Dict,
        actual_entry: float,
    ) -> Dict:
        """
        Simulate trade from entry until SL/TP/session end (within this session df)
        """
        side = setup["side"]
        sl = setup["sl"]
        tp = setup["tp"]
        lot_size = setup["lot_size"]

        entry_row = df.iloc[entry_idx]
        entry_time = entry_row["time"]

        trade_end = session["trade_end"]
        idx = entry_idx + 1

        exit_price = actual_entry
        exit_time = entry_time
        result = "session_exit"

        while idx < len(df):
            row = df.iloc[idx]
            row_time: datetime = row["time"]

            end_dt = datetime.combine(entry_time.date(), trade_end)
            if trade_end < session["mark_start"]:
                end_dt += timedelta(days=1)

            if row_time > end_dt:
                exit_price = row["close"]
                exit_time = row_time
                result = "session_exit"
                break

            high = row["high"]
            low = row["low"]

            if side == "B":
                if high >= tp:
                    exit_price = tp
                    exit_time = row_time
                    result = "tp"
                    break
                if low <= sl:
                    exit_price = sl
                    exit_time = row_time
                    result = "sl"
                    break
            else:
                if low <= tp:
                    exit_price = tp
                    exit_time = row_time
                    result = "tp"
                    break
                if high >= sl:
                    exit_price = sl
                    exit_time = row_time
                    result = "sl"
                    break

            idx += 1

        # PNL
        pip_value = StrategyCalculator.get_pip_value(self.pair, actual_entry)

        if self.pair.endswith("JPY"):
            pip_multiplier = 100.0
        else:
            pip_multiplier = 10000.0

        if side == "B":
            pnl_pips = (exit_price - actual_entry) * pip_multiplier
        else:
            pnl_pips = (actual_entry - exit_price) * pip_multiplier

        pnl_amount = pnl_pips * pip_value * lot_size

        self.current_fund += pnl_amount
        self.equity_high = max(self.equity_high, self.current_fund)
        drawdown = self.equity_high - self.current_fund
        self.max_drawdown = max(self.max_drawdown, drawdown)

        trade_record = {
            "date": entry_time.date(),
            "session": session["name"],
            "side": side,
            "entry_time": entry_time,
            "entry_price": actual_entry,
            "sl": sl,
            "tp": tp,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "result": result,
            "pnl_pips": round(pnl_pips, 1),
            "pnl_amount": round(pnl_amount, 2),
            "fund_after": round(self.current_fund, 2),
        }
        self.trades.append(trade_record)
        self.total_trades += 1

        return trade_record

    # ------------------ MOCK GANN ------------------

    def _mock_gann_levels(self, price: float) -> Dict:
        offset = 0.004
        return {
            "input_price": price,
            "buy_at": price + offset,
            "buy_t1": price + offset * 0.5,
            "buy_t2": price + offset * 1.0,
            "buy_t3": price + offset * 1.5,
            "buy_t4": price + offset * 2.0,
            "sell_at": price - offset,
            "sell_t1": price - offset * 0.5,
            "sell_t2": price - offset * 1.0,
            "sell_t3": price - offset * 1.5,
            "sell_t4": price - offset * 2.0,
        }

        # ------------------ MAIN BACKTEST LOOP ------------------

    def run_backtest(self, csv_path: str, use_mock_gann: bool = False) -> None:
        # Load candles from CSV
        df = pd.read_csv(csv_path)
        df["time"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("time").reset_index(drop=True)

        print(f"Loaded {len(df)} candles from {csv_path}")

        # Group by day (IST)
        grouped = df.groupby(df["time"].dt.date)

        for day, day_df in grouped:
            print("\n" + "=" * 60)
            print(f"Processing: {day}")
            print(
                f"Current Fund: ${self.current_fund:.2f} | "
                f"Risk: {self.current_risk_percent}%"
            )
            print("=" * 60)

            for session in self.sessions:
                # Session-wise subset
                session_df = self._get_session_df(
                    day_df, session, datetime.combine(day, time(0, 0))
                )
                if session_df.empty:
                    print(f"\n{session['name']}: No candles in session window")
                    continue

                # Marking
                marked = self._find_marking_candles(session_df, session)
                if not marked:
                    print(f"\n{session['name']}: No marking candles found")
                    continue

                print(
                    f"\n{session['name']}: Marked High={marked['high']:.5f}, "
                    f"Low={marked['low']:.5f}"
                )

                # Breakout after marking candles
                start_idx = marked["end_idx"] + 1
                breakout = self.detect_breakout(
                    session_df, marked, start_idx, session
                )
                if not breakout:
                    print("  -> No breakout detected")
                    continue

                print(
                    f"  -> {breakout['side']} BO at {breakout['breakout_time']}, "
                    f"Input: {breakout['input_price']:.5f}"
                )

                # Gann levels
                if use_mock_gann:
                    gann_levels = self._mock_gann_levels(
                        breakout["input_price"])
                else:
                    fetcher = GannFetcher(headless=True)
                    gann_levels = fetcher.get_levels(breakout["input_price"])
                    fetcher.close()

                fund = self.current_fund
                risk_percent = self.current_risk_percent

                # Strategy setup
                if breakout["side"] == "B":
                    setup = StrategyCalculator.get_buy_bo_setup(
                        gann_levels, fund, risk_percent, pair=self.pair
                    )
                else:
                    setup = StrategyCalculator.get_sell_bo_setup(
                        gann_levels, fund, risk_percent, pair=self.pair
                    )

                print(
                    f"  -> Entry: {setup['entry']:.5f}, SL: {setup['sl']:.5f}, "
                    f"TP: {setup['tp']:.5f}, Lot: {setup['lot_size']:.2f}"
                )

                # Wait for entry fill
                entry_result = self.wait_for_entry(
                    session_df, setup, breakout["breakout_time"], session
                )
                if not entry_result:
                    print(
                        f"  -> Entry level {setup['entry']:.5f} never touched, no trade"
                    )
                    continue

                print(
                    f"  -> Entry filled at {entry_result['entry_time']}, "
                    f"price: {entry_result['actual_entry']:.5f}"
                )

                # Simulate trade
                result = self.simulate_trade(
                    session_df,
                    setup,
                    entry_result["entry_idx"],
                    session,
                    entry_result["actual_entry"],
                )
                print(
                    f"  -> Exit {result['result']} at {result['exit_time']}, "
                    f"price: {result['exit_price']:.5f}, "
                    f"PNL: ${result['pnl_amount']:.2f}, "
                    f"Fund: ${result['fund_after']:.2f}"
                )

        # Final stats
        if self.trades:
            wins = len([t for t in self.trades if t["pnl_amount"] > 0])
            self.total_trades = len(self.trades)
            self.win_rate = wins / self.total_trades * 100
        else:
            self.total_trades = 0
            self.win_rate = 0.0

        print("\n" + "=" * 60)
        print("BACKTEST COMPLETE")
        print(f"Initial Fund: ${self.initial_fund:.2f}")
        print(f"Final Fund:   ${self.current_fund:.2f}")
        print(f"Total Trades: {self.total_trades}")
        print(f"Win Rate:     {self.win_rate:.2f}%")
        print(f"Max DD:       ${self.max_drawdown:.2f}")
        print("=" * 60)

    # ------------------ EXCEL EXPORT ------------------

    def export_to_excel(self, output_path: str) -> None:
        import pandas as pd

        folder = "backtests"
        os.makedirs(folder, exist_ok=True)
        full_path = os.path.join(folder, os.path.basename(output_path))

        total_trades = len(self.trades)
        net_pnl = self.current_fund - self.initial_fund

        summary = {
            "Metric": [
                "Initial Fund",
                "Final Fund",
                "Net PNL",
                "Total Trades",
                "Win Rate",
                "Max Drawdown",
            ],
            "Value": [
                self.initial_fund,
                self.current_fund,
                net_pnl,
                total_trades,
                f"{self.win_rate:.2f}%" if total_trades > 0 else "N/A",
                self.max_drawdown,
            ],
        }

        with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
            if self.trades:
                trades_df = pd.DataFrame(self.trades)
                trades_df.to_excel(writer, sheet_name="Trades", index=False)

            summary_df = pd.DataFrame(summary)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

        print(f"\nBacktest results exported to: {full_path}")
