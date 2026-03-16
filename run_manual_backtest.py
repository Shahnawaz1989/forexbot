# run_manual_backtest.py

from datetime import datetime, timedelta
import pandas as pd
import MetaTrader5 as mt5

from backtest_engine import BacktestEngine
import backtest_engine
print("BACKTEST_ENGINE FILE:", backtest_engine.__file__)


# =======================
#  MANUAL SETTINGS (EDIT ONLY THESE)
# =======================

PAIR = "EURAUD"          # <-- yahan pair name
BROKER_SYMBOL = "EURAUD.raw"  # <-- agar broker me .raw hai, warna "EURUSD"

FROM_DATE = "2026-02-03"  # <-- start date (IST)  YYYY-MM-DD
TO_DATE   = "2026-02-03"  # <-- end date   (IST)  YYYY-MM-DD

INITIAL_FUND = 30
RISK_PERCENT = 8
USE_MOCK_GANN = False     # True = mock fast, False = real Gann (slow)


# =======================
#  HELPER: FETCH MT5 DATA FOR GIVEN DATE RANGE (IST CORRECTED)
# =======================

def fetch_ist_data(symbol: str, from_date: str, to_date: str, outfile: str) -> None:
    if not mt5.initialize():
        print("MT5 init failed")
        quit()

    print(f"\nFetching {symbol} 15min data for {from_date} to {to_date} (IST) ...")

    # Date range (IST)
    start_ist = datetime.strptime(from_date, "%Y-%m-%d")
    end_ist   = datetime.strptime(to_date, "%Y-%m-%d")

    # Broker GMT+2 window: start_ist 00:00 IST = previous day 20:30 broker
    start_broker = start_ist - timedelta(hours=3, minutes=30)
    end_broker   = end_ist + timedelta(days=1) - timedelta(seconds=1)
    end_broker   = end_broker - timedelta(hours=3, minutes=30)

    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start_broker, end_broker)

    if rates is None or len(rates) == 0:
        print("No data fetched from MT5")
        mt5.shutdown()
        quit()

    df = pd.DataFrame(rates)
    df["broker_time"] = pd.to_datetime(df["time"], unit="s")

    # Broker GMT+2 → IST (+3.5h)
    df["datetime"] = df["broker_time"] + timedelta(hours=3, minutes=30)

    # Filter exact IST date range
    mask = (df["datetime"].dt.date >= start_ist.date()) & \
           (df["datetime"].dt.date <= end_ist.date())
    df = df.loc[mask].reset_index(drop=True)

    if df.empty:
        print("No IST candles in this date range")
        mt5.shutdown()
        quit()

    df_clean = df[["datetime", "open", "high", "low", "close"]].copy()
    df_clean.to_csv(outfile, index=False)

    mt5.shutdown()

    print(f"✓ Saved {len(df_clean)} candles to {outfile}")


# =======================
#  MAIN
# =======================

if __name__ == "__main__":
    print("="*60)
    print("FOREX GANN 15MIN BACKTEST - MANUAL RANGE")
    print("="*60)
    print(f"Pair   : {PAIR}")
    print(f"Broker : {BROKER_SYMBOL}")
    print(f"Period : {FROM_DATE} to {TO_DATE} (IST)")
    print(f"Fund   : ${INITIAL_FUND}")
    print(f"Risk   : {RISK_PERCENT}% per trade")
    print("="*60)

    csv_file = f"{PAIR.lower()}_{FROM_DATE}_to_{TO_DATE}_15min.csv"

    # 1) Fetch data for this pair + date range
    fetch_ist_data(BROKER_SYMBOL, FROM_DATE, TO_DATE, csv_file)

    # 2) Run backtest
    engine = BacktestEngine(
        initial_fund=INITIAL_FUND,
        initial_risk_percent=RISK_PERCENT,
        pair=PAIR,
    )

    try:
        print("\nStarting backtest...")
        engine.run_backtest(
            csv_path=csv_file,
            use_mock_gann=USE_MOCK_GANN
        )

        # 3) Export Excel
        out_file = f"backtest_{PAIR.lower()}_{FROM_DATE}_to_{TO_DATE}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        engine.export_to_excel(out_file)

        print("\n" + "="*60)
        print("Backtest completed!")
        print(f"Excel file: {out_file}")
        print("="*60)

    except Exception as e:
        print("\nERROR during backtest:")
        print(e)
        import traceback
        traceback.print_exc()
