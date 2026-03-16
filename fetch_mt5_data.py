import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

symbol = "EURUSD.raw"

if not mt5.initialize():
    print("MT5 init failed")
    quit()

print("Fetching EURUSD.raw 15min data for 01–06 Feb 2026 (IST corrected)...")

# Broker time range (GMT+2):
# 01 Feb 00:00 IST = 31 Jan 20:30 broker (previous day)
# 06 Feb 23:59 IST ~ 06 Feb 20:30 broker
start = datetime(2026, 1, 31, 20, 30)
end   = datetime(2026, 2, 6, 20, 30)

rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start, end)

if rates is None or len(rates) == 0:
    print("No data")
    mt5.shutdown()
    quit()

df = pd.DataFrame(rates)
df["broker_time"] = pd.to_datetime(df["time"], unit="s")

# Convert broker (GMT+2) → IST (+3.5h)
df["datetime"] = df["broker_time"] + timedelta(hours=3, minutes=30)

# Filter only 01–06 Feb 2026 IST
start_ist = pd.to_datetime("2026-02-01")
end_ist   = pd.to_datetime("2026-02-06")

mask = (df["datetime"].dt.date >= start_ist.date()) & \
       (df["datetime"].dt.date <= end_ist.date())
df = df.loc[mask].reset_index(drop=True)

df_clean = df[["datetime", "open", "high", "low", "close"]].copy()

print(f"\n✓ Fetched {len(df_clean)} candles (IST, 1–6 Feb)")
print("\nFirst 5 candles (IST):")
print(df_clean.head())

output_file = "eurusd_feb1_6_15min.csv"
df_clean.to_csv(output_file, index=False)
print(f"\n✓ Saved as: {output_file}")

mt5.shutdown()
