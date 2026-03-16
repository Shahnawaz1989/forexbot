from backtest_engine import BacktestEngine
from datetime import datetime

print("="*60)
print("FOREX GANN 15MIN BACKTEST")
print("="*60)
print("Period: 01 Feb 2026 - 06 Feb 2026")
print("Initial Fund: $30")
print("Risk: 8% per trade")
print("Pair: EURUSD")
print("="*60)

# Create backtest engine
engine = BacktestEngine(
    initial_fund=30,
    initial_risk_percent=8,
    pair="EURUSD"
)

# Run backtest
try:
    print("\nStarting backtest...")
    engine.run_backtest(
        csv_path="eurusd_feb1_6_15min.csv",  # 1–6 Feb week file
        use_mock_gann=False                  # real Gann (slow)
    )

    # Export to Excel
    output_file = f"backtest_feb1_6_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    engine.export_to_excel(output_file)

    print("\n" + "="*60)
    print("Backtest completed!")
    print(f"Excel file: {output_file}")
    print("="*60)

except FileNotFoundError:
    print("\nERROR: eurusd_feb1_6_15min.csv not found!")
    print("Run: python fetch_mt5_data.py first")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
