"""
BACKTEST CONFIGURATION
Edit only this file to run backtest with different settings
"""

# Date Range
START_DATE = "2026-03-10"  # Format: YYYY-MM-DD
END_DATE = "2026-03-15"    # Same date for single day, different for range

# Trading Parameters
INITIAL_FUND = 30          # Starting capital in dollars
INITIAL_RISK = 8           # Risk percentage per trade
PAIR = "EURUSD"            # Trading pair

# Gann Settings
USE_REAL_GANN = True      # True = fetch from site (slow), False = mock (fast)

# Output
EXCEL_FILENAME = "backtest_results.xlsx"  # Output Excel file name

# MT5 Symbol (broker specific)
MT5_SYMBOL = "EURUSD.raw"  # Your broker's symbol format

# ============================================
# NO NEED TO EDIT BELOW THIS LINE
# ============================================

if __name__ == "__main__":
    print("="*60)
    print("BACKTEST CONFIGURATION LOADED")
    print("="*60)
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Initial Fund: ${INITIAL_FUND}")
    print(f"Risk: {INITIAL_RISK}%")
    print(f"Pair: {PAIR}")
    print(f"Real Gann: {USE_REAL_GANN}")
    print(f"Output: {EXCEL_FILENAME}")
    print("="*60)
    print("\nTo run backtest: python run_single_backtest.py")
