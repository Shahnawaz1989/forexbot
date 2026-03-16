import MetaTrader5 as mt5
from datetime import datetime

# Initialize MT5
if not mt5.initialize():
    print("MT5 initialization failed")
    print(mt5.last_error())
    quit()

print("MT5 connected successfully!")
print(f"MT5 version: {mt5.version()}")

# Account info
account_info = mt5.account_info()
if account_info:
    print(f"\nAccount Balance: ${account_info.balance:.2f}")
    print(f"Account Equity: ${account_info.equity:.2f}")
    print(f"Account Currency: {account_info.currency}")
    print(f"Leverage: 1:{account_info.leverage}")

# Symbol info (EURUSD)
symbol = "EURUSD"
symbol_info = mt5.symbol_info(symbol)
if symbol_info:
    print(f"\n{symbol} Info:")
    print(f"  Bid: {symbol_info.bid}")
    print(f"  Ask: {symbol_info.ask}")
    print(f"  Spread: {symbol_info.spread} points")
    print(f"  Digits: {symbol_info.digits}")
    print(f"  Min Lot: {symbol_info.volume_min}")
    print(f"  Max Lot: {symbol_info.volume_max}")
    print(f"  Lot Step: {symbol_info.volume_step}")
else:
    print(f"\n{symbol} not found. Available symbols:")
    symbols = mt5.symbols_get()
    for s in symbols[:10]:  # First 10
        print(f"  - {s.name}")

# Shutdown
mt5.shutdown()
print("\nMT5 disconnected")
