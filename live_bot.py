import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
import time as time_module
import schedule
import json
from typing import Dict, Optional, List

from gann_fetcher import GannFetcher
from strategy_calculator import StrategyCalculator


class LiveBot:
    """
    Live trading bot for MT5 with Gann 15min scalping strategy
    """
    
    def __init__(self, symbol: str, initial_fund: float, initial_risk: float):
        self.symbol = symbol
        self.initial_fund = initial_fund
        self.current_fund = initial_fund
        self.initial_risk = initial_risk
        self.current_risk = initial_risk
        
        # Trading state
        self.active_trade = None
        self.session_state = {}
        self.week_start_fund = initial_fund
        self.last_week_number = None
        
        # Session definitions (IST times)
        self.sessions = [
            {
                'name': 'Session 1',
                'mark_start': time(5, 30),
                'mark_end': time(5, 45),
                'trade_end': time(11, 0),
                'candles_to_mark': 2,
                'marked_levels': None,
                'trade_taken': False
            },
            {
                'name': 'Session 2',
                'mark_start': time(13, 0),
                'mark_end': time(13, 15),
                'trade_end': time(18, 0),
                'candles_to_mark': 1,
                'marked_levels': None,
                'trade_taken': False
            },
            {
                'name': 'Session 3',
                'mark_start': time(19, 0),
                'mark_end': time(19, 15),
                'trade_end': time(0, 30),
                'candles_to_mark': 1,
                'marked_levels': None,
                'trade_taken': False
            }
        ]
        
        self.trade_log = []
        self.gann_fetcher = GannFetcher(headless=True)
    
    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection"""
        if not mt5.initialize():
            print(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        # Check symbol availability
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f"Symbol {self.symbol} not found")
            mt5.shutdown()
            return False
        
        # Enable symbol if not visible
        if not symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                print(f"Failed to select {self.symbol}")
                mt5.shutdown()
                return False
        
        print(f"MT5 initialized successfully")
        print(f"Trading symbol: {self.symbol}")
        return True
    
    def get_current_price(self) -> Optional[float]:
        """Get current bid price"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick:
            return tick.bid
        return None
    
    def get_candles(self, timeframe: int, count: int) -> Optional[pd.DataFrame]:
        """
        Fetch recent candles from MT5
        timeframe: mt5.TIMEFRAME_M15 (15min)
        """
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['datetime'] = pd.to_datetime(df['time'], unit='s')
        df['datetime'] = df['datetime'] + timedelta(hours=5, minutes=30)  # Convert to IST
        return df[['datetime', 'open', 'high', 'low', 'close']]
    
    def check_new_week(self):
        """Check if new week started (Monday) and update risk"""
        now = datetime.now()
        current_week = now.isocalendar()[1]
        
        if self.last_week_number is None:
            self.last_week_number = current_week
            return
        
        if current_week != self.last_week_number and now.weekday() == 0:
            # New week (Monday)
            self.current_risk += 1
            self.week_start_fund = self.current_fund
            self.last_week_number = current_week
            
            print(f"\n{'='*60}")
            print(f"*** NEW WEEK STARTED ***")
            print(f"Risk increased to: {self.current_risk}%")
            print(f"Week start fund: ${self.current_fund:.2f}")
            print('='*60)
    
    def mark_session_levels(self, session: Dict):
        """Mark high/low for session"""
        candles = self.get_candles(mt5.TIMEFRAME_M15, 10)
        if candles is None:
            return
        
        now_time = datetime.now().time()
        
        # Check if we're in marking window
        if not (session['mark_start'] <= now_time <= session['mark_end']):
            return
        
        # Get candles in marking window
        marking_candles = candles[
            (candles['datetime'].dt.time >= session['mark_start']) &
            (candles['datetime'].dt.time <= session['mark_end'])
        ]
        
        if len(marking_candles) >= session['candles_to_mark']:
            session['marked_levels'] = {
                'high': marking_candles['high'].max(),
                'low': marking_candles['low'].min()
            }
            print(f"\n{session['name']}: Marked High={session['marked_levels']['high']:.5f}, Low={session['marked_levels']['low']:.5f}")
    
    def check_breakout(self, session: Dict) -> Optional[Dict]:
        """Check if breakout happened"""
        if session['marked_levels'] is None:
            return None
        
        if session['trade_taken']:
            return None
        
        now_time = datetime.now().time()
        if now_time > session['trade_end']:
            return None
        
        # Get latest candle
        candles = self.get_candles(mt5.TIMEFRAME_M15, 2)
        if candles is None or len(candles) < 1:
            return None
        
        latest = candles.iloc[-1]
        close = latest['close']
        
        # High breakout
        if close > session['marked_levels']['high']:
            return {
                'side': 'BUY',
                'input_price': latest['high'],
                'breakout_time': latest['datetime']
            }
        
        # Low breakout
        if close < session['marked_levels']['low']:
            return {
                'side': 'SELL',
                'input_price': latest['low'],
                'breakout_time': latest['datetime']
            }
        
        return None
    
    def place_order(self, setup: Dict, session: Dict) -> bool:
        """Execute market order with SL/TP"""
        try:
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                print(f"Symbol info not available")
                return False
            
            # Prepare request
            point = symbol_info.point
            price = setup['entry']
            lot = setup['lot_size']
            sl = setup['sl']
            tp = setup['tp']
            
            # Order type
            order_type = mt5.ORDER_TYPE_BUY if setup['side'] == 'BUY' else mt5.ORDER_TYPE_SELL
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 123456,
                "comment": f"Gann {setup['side']} BO",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Order failed: {result.comment}")
                return False
            
            print(f"\n{'='*60}")
            print(f"ORDER EXECUTED: {setup['side']}")
            print(f"Entry: {setup['entry']:.5f} | SL: {sl:.5f} | TP: {tp:.5f}")
            print(f"Lot: {lot} | Ticket: {result.order}")
            print('='*60)
            
            # Store active trade
            self.active_trade = {
                'ticket': result.order,
                'session': session['name'],
                'side': setup['side'],
                'entry': price,
                'sl': sl,
                'tp': tp,
                'lot': lot,
                'entry_time': datetime.now(),
                'setup': setup
            }
            
            session['trade_taken'] = True
            return True
            
        except Exception as e:
            print(f"Order placement error: {e}")
            return False
    
    def monitor_active_trade(self):
        """Check if active trade is closed"""
        if self.active_trade is None:
            return
        
        # Check if position still open
        positions = mt5.positions_get(ticket=self.active_trade['ticket'])
        
        if positions is None or len(positions) == 0:
            # Position closed
            history = mt5.history_deals_get(ticket=self.active_trade['ticket'])
            if history and len(history) > 0:
                pnl = sum([deal.profit for deal in history])
                
                print(f"\n{'='*60}")
                print(f"TRADE CLOSED")
                print(f"PNL: ${pnl:.2f}")
                print('='*60)
                
                # Update fund
                self.current_fund += pnl
                
                # Log trade
                self.trade_log.append({
                    'date': datetime.now().date(),
                    'session': self.active_trade['session'],
                    'side': self.active_trade['side'],
                    'entry': self.active_trade['entry'],
                    'sl': self.active_trade['sl'],
                    'tp': self.active_trade['tp'],
                    'lot': self.active_trade['lot'],
                    'pnl': pnl,
                    'fund_after': self.current_fund
                })
                
                self.active_trade = None
    
    def run_strategy_cycle(self):
        """Main strategy loop - runs every 1 minute"""
        try:
            now = datetime.now()
            now_time = now.time()
            
            print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] Checking... Fund: ${self.current_fund:.2f}")
            
            # Check new week
            self.check_new_week()
            
            # Monitor active trade
            self.monitor_active_trade()
            
            # If trade active, skip new entries
            if self.active_trade is not None:
                return
            
            # Check each session
            for session in self.sessions:
                # Mark levels if in marking window
                if session['marked_levels'] is None:
                    self.mark_session_levels(session)
                
                # Check breakout
                breakout = self.check_breakout(session)
                if breakout:
                    print(f"\n{session['name']}: {breakout['side']} BREAKOUT detected!")
                    print(f"Input price for Gann: {breakout['input_price']:.5f}")
                    
                    # Fetch Gann levels
                    gann_levels = self.gann_fetcher.get_levels(breakout['input_price'])
                    if not gann_levels:
                        print("Failed to fetch Gann levels")
                        continue
                    
                    # Calculate setup
                    pair_clean = self.symbol.replace('.raw', '')
                    if breakout['side'] == 'BUY':
                        setup = StrategyCalculator.get_buy_bo_setup(
                            gann_levels, self.current_fund, self.current_risk, pair_clean
                        )
                    else:
                        setup = StrategyCalculator.get_sell_bo_setup(
                            gann_levels, self.current_fund, self.current_risk, pair_clean
                        )
                    
                    print(f"Entry: {setup['entry']:.5f}, SL: {setup['sl']:.5f}, TP: {setup['tp']:.5f}, Lot: {setup['lot_size']}")
                    
                    # Execute trade
                    self.place_order(setup, session)
            
            # Reset sessions at midnight
            if now_time < time(0, 5):
                for session in self.sessions:
                    session['marked_levels'] = None
                    session['trade_taken'] = False
                    
        except Exception as e:
            print(f"Strategy cycle error: {e}")
            import traceback
            traceback.print_exc()
    
    def start(self):
        """Start the live bot"""
        if not self.initialize_mt5():
            return
        
        print(f"\n{'='*60}")
        print(f"LIVE BOT STARTED")
        print(f"Symbol: {self.symbol}")
        print(f"Initial Fund: ${self.initial_fund:.2f}")
        print(f"Risk: {self.current_risk}%")
        print('='*60)
        
        # Schedule strategy to run every 1 minute
        schedule.every(1).minutes.do(self.run_strategy_cycle)
        
        # Run immediately once
        self.run_strategy_cycle()
        
        try:
            while True:
                schedule.run_pending()
                time_module.sleep(10)
        except KeyboardInterrupt:
            print("\nBot stopped by user")
        finally:
            self.gann_fetcher.close()
            mt5.shutdown()
            print("MT5 disconnected")
    
    def stop(self):
        """Stop the bot"""
        self.gann_fetcher.close()
        mt5.shutdown()


# Run bot
if __name__ == "__main__":
    bot = LiveBot(
        symbol="EURUSD.raw",  # Your broker's symbol format
        initial_fund=5000,  # Starting with your demo balance
        initial_risk=8  # 8% risk per trade
    )
    
    bot.start()
