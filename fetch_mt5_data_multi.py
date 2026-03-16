import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

PAIRS = [
    "AUDCAD", "AUDCHF", "AUDUSD", "AUDJPY",
    "CADCHF", "CADJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURUSD", "EURGBP", "EURJPY",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPUSD", "GBPJPY",
    "NZDCAD", "NZDCHF", "NZDUSD", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]

# Agar broker ke symbols different hon (e.g. EURUSD.raw), yahan mapping daalna
SYMBOL_MAP = {p: f"{p}.raw" for p in PAIRS}  # agar sab .raw hain
# Example: agar sirf EURUSD.raw hai, baaki plain:
# SYMBOL_MAP = {p: p for p in PAIRS}
# SYMBOL_MAP["EURUSD"] = "EURUSD.raw"

if not mt5.initialize():
    print("MT5 init failed")
    quit()

print("Fetching 15min data for 01–06 Feb 2026 (IST corrected)...")

start = datetime(2026, 1, 31, 20, 30)  # broker time (GMT+2)
end   = datetime(2026, 2, 6, 20, 30)

for pair in PAIRS:
    symbol = SYMBOL_MAP.get(pair, pair)
    print(f"\n--- {pair} ({symbol}) ---")

    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start, end)
    if rates is None or len(rates) == 0:
        print("No data, skipping.")
        continue

    df = pd.DataFrame(rates)
    df["broker_time"] = pd.to_datetime(df["time"], unit="s")

    # Broker GMT+2 → IST (+3.5h)
    df["datetime"] = df["broker_time"] + timedelta(hours=3, minutes=30)

    start_ist = pd.to_datetime("2026-02-01")
    end_ist   = pd.to_datetime("2026-02-06")
    mask = (df["datetime"].dt.date >= start_ist.date()) & \
           (df["datetime"].dt.date <= end_ist.date())
    df = df.loc[mask].reset_index(drop=True)

    if df.empty:
        print("No IST candles in 1–6 Feb, skipping.")
        continue

    df_clean = df[["datetime", "open", "high", "low", "close"]].copy()
    out_file = f"{pair.lower()}_feb1_6_15min.csv"
    df_clean.to_csv(out_file, index=False)

    print(f"Saved {len(df_clean)} candles to {out_file}")

mt5.shutdown()
print("\nDone fetching all pairs.")
