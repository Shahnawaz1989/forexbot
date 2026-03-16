import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from backtest_engine import BacktestEngine
from config_backtest import *

def fetch_data_from_mt5():
    """Fetch data from MT5 for configured date range"""
    if not mt5.initialize():
        print("MT5 initialization failed")
        return None
    
    print(f"\nFetching {MT5_SYMBOL} data from MT5...")
    
    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)
    
    rates = mt5.copy_rates_range(MT5_SYMBOL, mt5.TIMEFRAME_M15, start, end)
    
    if rates is None or len(rates) == 0:
        print("No data fetched")
        mt5.shutdown()
        return None
    
    df = pd.DataFrame(rates)
    df['datetime'] = pd.to_datetime(df['time'], unit='s')
    df['datetime'] = df['datetime'] + timedelta(hours=5, minutes=30)  # IST
    
    df_clean = df[['datetime', 'open', 'high', 'low', 'close']].copy()
    
    # Filter by date range
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d") + timedelta(days=1)
    
    df_clean = df_clean[
        (df_clean['datetime'] >= start_dt) & 
        (df_clean['datetime'] < end_dt)
    ].reset_index(drop=True)
    
    csv_file = "eurusd_feb6_correct.csv"  # Use corrected data
    df_clean.to_csv(csv_file, index=False)
    
    print(f"✓ Fetched {len(df_clean)} candles")
    print(f"✓ Date range: {df_clean['datetime'].min()} to {df_clean['datetime'].max()}")
    print(f"✓ Saved as: {csv_file}")
    
    mt5.shutdown()
    return csv_file

def run_backtest():
    """Run backtest with configured settings"""
    print("\n" + "="*60)
    print("FOREX GANN 15MIN BACKTEST")
    print("="*60)
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Initial Fund: ${INITIAL_FUND}")
    print(f"Risk: {INITIAL_RISK}% per trade")
    print(f"Pair: {PAIR}")
    print(f"Real Gann: {'Yes (slow)' if USE_REAL_GANN else 'No (mock - fast)'}")
    print("="*60)
    
    # Fetch data
    csv_file = fetch_data_from_mt5()
    if not csv_file:
        print("\nERROR: Failed to fetch data from MT5")
        return
    
    # Create backtest engine
    engine = BacktestEngine(
        initial_fund=INITIAL_FUND,
        initial_risk_percent=INITIAL_RISK,
        pair=PAIR
    )
    
    # Run backtest
    try:
        print("\nStarting backtest...\n")
        engine.run_backtest(
            csv_path=csv_file,
            use_mock_gann=not USE_REAL_GANN
        )
        
        # Export to Excel
        output_file = f"{EXCEL_FILENAME.replace('.xlsx', '')}_{START_DATE}_to_{END_DATE}.xlsx"
        engine.export_to_excel(output_file)
        
        print(f"\n{'='*60}")
        print(f"Backtest completed!")
        print(f"Excel file: {output_file}")
        print("="*60)
        
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_backtest()
