from backtest_engine import BacktestEngine
from datetime import datetime

PAIRS = [
    "AUDCAD", "AUDCHF", "AUDUSD", "AUDJPY",
    "CADCHF", "CADJPY",
    "EURAUD", "EURCAD", "EURCHF", "EURUSD", "EURGBP", "EURJPY",
    "GBPAUD", "GBPCAD", "GBPCHF", "GBPUSD", "GBPJPY",
    "NZDCAD", "NZDCHF", "NZDUSD", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]

print("="*60)
print("FOREX GANN 15MIN BACKTEST - MULTI PAIR")
print("="*60)
print("Period: 01 Feb 2026 - 06 Feb 2026")
print("Initial Fund: $30 per pair (independent)")
print("Risk: 8% per trade")
print("="*60)

for pair in PAIRS:
    csv_file = f"{pair.lower()}_feb1_6_15min.csv"
    print("\n" + "-"*60)
    print(f"PAIR: {pair}")
    print(f"CSV : {csv_file}")
    print("-"*60)

    engine = BacktestEngine(
        initial_fund=30,
        initial_risk_percent=8,
        pair=pair
    )

    try:
        print("Starting backtest...")
        engine.run_backtest(
            csv_path=csv_file,
            use_mock_gann=False
        )

        out_file = f"backtest_{pair.lower()}_feb1_6_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        engine.export_to_excel(out_file)

        print(f"Backtest completed for {pair}, Excel: {out_file}")

    except FileNotFoundError:
        print(f"ERROR: CSV not found for {pair}: {csv_file}")
    except Exception as e:
        print(f"ERROR running backtest for {pair}: {e}")
        import traceback
        traceback.print_exc()
