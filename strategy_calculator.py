import math
from typing import Dict, Tuple

class StrategyCalculator:
    """
    Calculates entry, SL sizing, TP, and lot size based on Gann levels
    """
    
    @staticmethod
    def get_pip_value(pair: str, price: float) -> float:
        """
        Return pip value per 1.00 lot in USD for given pair and current price.
        Assumes account currency = USD.
        """
        pair = pair.upper()
        # Direct USD quote (XXXUSD)
        if pair.endswith("USD"):
            return 10.0  # e.g. EURUSD, GBPUSD, AUDUSD, NZDUSD

        # USD as base (USDXXX), e.g. USDJPY, USDCHF, USDCAD
        if pair.startswith("USD"):
            # For JPY pairs 1 pip = 0.01, others 0.0001
            if pair.endswith("JPY"):
                pip = 0.01
            else:
                pip = 0.0001
            return (pip / price) * 100000  # notional 100k

        # Crosses where quote currency is USD second leg (e.g. EURAUD, EURCAD)
        # Approximate via first leg against USD if needed; for simplicity:
        return 10.0
    
    @staticmethod
    def calculate_t15(t1: float, t2: float) -> float:
        """T1.5 = (T1 + T2) / 2"""
        return (t1 + t2) / 2
    
    @staticmethod
    def calculate_sl_sizing_from_t15(t15: float, t1: float) -> int:
        """
        Entry from T1.5: SL sizing = |T1.5 - T1| / 4
        Returns rounded pips
        """
        diff = abs(t15 - t1)
        sizing_raw = diff / 4
        # Convert to pips (assuming 4-decimal pair like EURUSD: 1 pip = 0.0001)
        pips = sizing_raw / 0.0001
        return StrategyCalculator.roundoff_pips(pips)
    
    @staticmethod
    def calculate_sl_sizing_from_t1(t1: float, at: float) -> int:
        """
        Entry from T1: SL sizing = |T1 - AT| / 5
        Returns rounded pips
        """
        diff = abs(t1 - at)
        sizing_raw = diff / 5
        pips = sizing_raw / 0.0001
        return StrategyCalculator.roundoff_pips(pips)
    
    @staticmethod
    def calculate_tp_pips(sl_sizing_pips: int) -> int:
        """TP = SL sizing × 2"""
        return sl_sizing_pips * 2
    
    @staticmethod
    def get_pip_value_per_lot(pair: str, current_price: float) -> float:
        """
        Calculate pip value per 1 standard lot for common forex pairs
        
        Args:
            pair: e.g., 'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'
            current_price: current market price
        
        Returns:
            Pip value in USD per 1 standard lot
        """
        pair = pair.upper().replace('/', '').replace('_', '')
        
        # USD-quoted pairs (XXXUSD)
        if pair.endswith('USD'):
            return 10.0  # $10 per pip for 1 standard lot
        
        # JPY pairs (XXXJPY) - 2 decimal pairs, pip = 0.01
        elif pair.endswith('JPY'):
            return (0.01 / current_price) * 100000
        
        # USD-base pairs (USDXXX) - need conversion
        elif pair.startswith('USD'):
            return (0.0001 / current_price) * 100000
        
        # Cross pairs (non-USD) - approximate using USD conversion
        else:
            return 10.0
    
    @staticmethod
    def calculate_lot_size(fund: float, risk_percent: float, 
                      sl_pips: int, pair: str, current_price: float) -> float:
        # Don't trade if fund is negative
        if fund <= 0:
            return 0.0
    
        risk_amount = fund * (risk_percent / 100)
        pip_value_per_lot = StrategyCalculator.get_pip_value_per_lot(pair, current_price)
    
        if sl_pips == 0 or pip_value_per_lot == 0:
            return 0.0
    
        lot = risk_amount / (sl_pips * pip_value_per_lot)
    
        # Ensure positive lot, min 0.01, max 100 (broker limits)
        lot = max(0.01, min(abs(lot), 100.0))
    
        return round(lot, 2)
    
    
    @staticmethod
    def roundoff_pips(pips: float) -> float:
        """
        Round pips to a reasonable precision (e.g. 0.1 pip steps).
        """
        return round(pips, 1)


    
    @staticmethod
    def get_buy_bo_setup(gann_levels: Dict, fund: float, 
                        risk_percent: float, pair: str) -> Dict:
        """
        Buy BO setup:
        - Entry: Buy T1.5
        - SL: Sell T1
        - SL sizing: |Buy T1.5 - Buy T1| / 4
        - TP: SL sizing × 2
        """
        buy_t1 = gann_levels['buy_targets'][0]
        buy_t2 = gann_levels['buy_targets'][1]
        sell_t1 = gann_levels['sell_targets'][0]
        
        # Entry
        entry = StrategyCalculator.calculate_t15(buy_t1, buy_t2)
        
        # SL (actual level)
        sl_level = sell_t1
        
        # SL sizing (pips)
        sl_sizing = StrategyCalculator.calculate_sl_sizing_from_t15(entry, buy_t1)
        
        # TP (pips from entry)
        tp_pips = StrategyCalculator.calculate_tp_pips(sl_sizing)
        tp_level = entry + (tp_pips * 0.0001)
        
        # Lot size (using entry as current price)
        lot = StrategyCalculator.calculate_lot_size(
            fund, risk_percent, sl_sizing, pair, entry
        )
        
        return {
            'side': 'BUY',
            'entry': round(entry, 5),
            'sl': round(sl_level, 5),
            'tp': round(tp_level, 5),
            'sl_sizing_pips': sl_sizing,
            'tp_pips': tp_pips,
            'lot_size': lot,
        }
    
    @staticmethod
    def get_sell_bo_setup(gann_levels: Dict, fund: float, 
                         risk_percent: float, pair: str) -> Dict:
        """
        Sell BO setup:
        - Entry: Sell T1.5
        - SL: Buy T1
        - SL sizing: |Sell T1.5 - Sell T1| / 4
        - TP: SL sizing × 2
        """
        sell_t1 = gann_levels['sell_targets'][0]
        sell_t2 = gann_levels['sell_targets'][1]
        buy_t1 = gann_levels['buy_targets'][0]
        
        # Entry
        entry = StrategyCalculator.calculate_t15(sell_t1, sell_t2)
        
        # SL (actual level)
        sl_level = buy_t1
        
        # SL sizing (pips)
        sl_sizing = StrategyCalculator.calculate_sl_sizing_from_t15(entry, sell_t1)
        
        # TP (pips from entry)
        tp_pips = StrategyCalculator.calculate_tp_pips(sl_sizing)
        tp_level = entry - (tp_pips * 0.0001)
        
        # Lot size
        lot = StrategyCalculator.calculate_lot_size(
            fund, risk_percent, sl_sizing, pair, entry
        )
        
        return {
            'side': 'SELL',
            'entry': round(entry, 5),
            'sl': round(sl_level, 5),
            'tp': round(tp_level, 5),
            'sl_sizing_pips': sl_sizing,
            'tp_pips': tp_pips,
            'lot_size': lot,
        }


# Test
if __name__ == "__main__":
    # Example Gann levels
    gann_levels = {
        'input_price': 1.70146,
        'buy_at': 1.7045,
        'buy_targets': [1.7077, 1.7117, 1.7157, 1.7198],
        'buy_sl': 1.7004,
        'sell_at': 1.7004,
        'sell_targets': [1.6973, 1.6933, 1.6892, 1.6852],
        'sell_sl': 1.7045,
    }
    
    # Risk parameters
    fund = 100  # $100
    risk_percent = 8  # 8%
    pair = 'EURUSD'
    
    print("="*60)
    print("BUY BO SETUP (High Breakout)")
    print("="*60)
    buy_setup = StrategyCalculator.get_buy_bo_setup(
        gann_levels, fund, risk_percent, pair
    )
    for key, val in buy_setup.items():
        print(f"{key:20s}: {val}")
    
    print("\n" + "="*60)
    print("SELL BO SETUP (Low Breakout)")
    print("="*60)
    sell_setup = StrategyCalculator.get_sell_bo_setup(
        gann_levels, fund, risk_percent, pair
    )
    for key, val in sell_setup.items():
        print(f"{key:20s}: {val}")
    
    # Test different pairs
    print("\n" + "="*60)
    print("PIP VALUE CALCULATION TEST")
    print("="*60)
    test_pairs = [
        ('EURUSD', 1.0850),
        ('GBPUSD', 1.2650),
        ('USDJPY', 149.50),
        ('AUDUSD', 0.6450),
    ]
    
    for pair_name, price in test_pairs:
        pip_val = StrategyCalculator.get_pip_value_per_lot(pair_name, price)
        print(f"{pair_name:10s} @ {price:8.4f} -> Pip Value: ${pip_val:.2f}/lot")
