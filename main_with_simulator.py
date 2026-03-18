import asyncio
import os
import time
import csv
from datetime import datetime
from dotenv import load_dotenv

from binance_client import BinanceClient
from coindcx_client import CoinDCXClient

# 🎮 MASTER SWITCH: Set to False ONLY when you have real, funded API keys
SIMULATION_MODE = True 
TEST_TRADE_SIZE_USDT = 15.0  # Pretend to trade $15 worth of crypto per trade

# --- 1. THE FOOLPROOF MASTER LIST --- 
SYMBOLS_TO_TRADE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "SHIBUSDT", 
    "MATICUSDT", "DOTUSDT", "LINKUSDT", "UNIUSDT", "LTCUSDT", "NEARUSDT", "ATOMUSDT", 
    "XLMUSDT", "BCHUSDT", "ALGOUSDT", "AVAXUSDT", "VETUSDT", "FILUSDT", "SANDUSDT", 
    "MANAUSDT", "AXSUSDT", "AAVEUSDT", "THETAUSDT", "EOSUSDT", "STXUSDT", "RNDRUSDT", 
    "INJUSDT", "FETUSDT", "OPUSDT", "ARBUSDT", "SUIUSDT", "APTUSDT", "LDOUSDT", 
    "GRTUSDT", "MKRUSDT", "SNXUSDT", "CRVUSDT", "GALAUSDT", "PEPEUSDT", "WLDUSDT", 
    "TIAUSDT", "SEIUSDT", "BLURUSDT", "FLOKIUSDT", "GMXUSDT", "COMPUSDT", "RUNEUSDT", 
    "FTMUSDT", "TRXUSDT", "BNBUSDT", "ETCUSDT", "ICPUSDT", "HBARUSDT", "QNTUSDT",
    "MNTUSDT"
]

# --- 2. CSV REPORTING ENGINE ---
# --- 2. CSV REPORTING ENGINE ---
def log_arbitrage_to_csv(symbol, ex1, b1, ex2, b2, gross_gap, actual_net_profit):
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"arbitrage_report_{date_str}.csv"
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        
        if not file_exists:
            writer.writerow([
                "Time", "Coin", "Exchange 1", "Ex1 Bid", "Ex1 Ask", 
                "Exchange 2", "Ex2 Bid", "Ex2 Ask", 
                "Gross Gap %", "Actual Net Profit % (After 0.3% Fees)"
            ])

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([
            timestamp, symbol, ex1, b1['bid'], b1['ask'], ex2, b2['bid'], b2['ask'],
            f"{gross_gap:.4f}%", f"{actual_net_profit:.4f}%"
        ])


# --- 3. THE SHARED BRAIN ---
class MarketState:
    def __init__(self, exch1_client, exch2_client):
        self.books = {}
        self.last_print = 0
        self.clients = {"Binance": exch1_client, "CoinDCX": exch2_client}
        self.last_logged_time = {} 

        # Risk Management & Simulation Tracking
        self.is_killed = False                 
        self.loss_time_window = 300            
        self.trade_history = []                
        self.last_update = {"Binance": 0, "CoinDCX": 0} 
        self._is_executing = False  
        
        # 💰 VIRTUAL WALLET
        self.sim_start_balance = 1000.00
        self.sim_balance = 1000.00
        self.sim_total_trades = 0

    def update_book(self, exchange, symbol, book_data):
        self.last_update[exchange] = time.time() 
        if symbol not in self.books: 
            self.books[symbol] = {}
        self.books[symbol][exchange] = book_data
        
        self.check_cross_exchange(symbol)
        self.display_metrics()

    def check_connectivity(self, ex1, ex2):
        now = time.time()
        if (now - self.last_update.get(ex1, 0)) > 0.5 or (now - self.last_update.get(ex2, 0)) > 0.5:
            return False
        return True

    async def execute_arbitrage(self, symbol, buy_exchange_name, buy_price, sell_exchange_name, sell_price):
        if self._is_executing: return
        self._is_executing = True

        qty = TEST_TRADE_SIZE_USDT / buy_price

        # --- FAKE EXECUTION (PAPER TRADING) ---
        if SIMULATION_MODE:
            profit_usdt = (sell_price - buy_price) * qty
            self.sim_balance += profit_usdt  # Add profit to virtual wallet
            self.sim_total_trades += 1       # Track total trades

            print("\n" + "═"*60)
            print(f"🎮 [SIMULATION MODE] PAPER TRADE EXECUTED: {symbol}")
            print(f"🟢 BUY  {qty:.4f} on {buy_exchange_name:<8} @ ${buy_price:.5f}")
            print(f"🔴 SELL {qty:.4f} on {sell_exchange_name:<8} @ ${sell_price:.5f}")
            print(f"💵 Net Profit from Trade: ${profit_usdt:.4f} USDT")
            print("═"*60 + "\n")
            
            await asyncio.sleep(1) # Cooldown
            self._is_executing = False
            return

        # --- REAL EXECUTION ---
        print(f"\n🚀 [ATOMIC EXECUTION TRIGGERED] {symbol} | Firing real orders...")
        buy_client = self.clients[buy_exchange_name]
        sell_client = self.clients[sell_exchange_name]

        results = await asyncio.gather(
            buy_client.place_order(symbol, side="BUY", order_type="ioc", qty=qty, price=buy_price),
            sell_client.place_order(symbol, side="SELL", order_type="ioc", qty=qty, price=sell_price),
            return_exceptions=True
        )

        print(f"✅ [EXECUTION COMPLETE] Buy Leg: {results[0]} | Sell Leg: {results[1]}")
        await asyncio.sleep(2)
        self._is_executing = False

    def check_cross_exchange(self, symbol):
        if self.is_killed: return
        if symbol not in self.books: return
        exchs = list(self.books[symbol].keys())
        if len(exchs) < 2: return

        ex1, ex2 = exchs[0], exchs[1]
        if not self.check_connectivity(ex1, ex2): return
        b1, b2 = self.books[symbol][ex1], self.books[symbol][ex2]
        
        def handle_opportunity(buy_ex, buy_b, sell_ex, sell_b, gross_gap):
            # 🚨 REALITY CHECK: Binance charges 0.1%, CoinDCX charges 0.2%. Total = 0.3%
            TOTAL_FEE_PCT = 0.30
            
            # The gap must be larger than the fees for the trade to be profitable
            if gross_gap > TOTAL_FEE_PCT:
                now = time.time()
                # Cooldown set to 15 seconds for testing
                if now - self.last_logged_time.get(symbol, 0) > 15:
                    
                    # Calculate EXACT take-home profit
                    actual_net_profit = gross_gap - TOTAL_FEE_PCT
                    
                    log_arbitrage_to_csv(symbol, buy_ex, buy_b, sell_ex, sell_b, gross_gap, actual_net_profit)
                    self.last_logged_time[symbol] = now

                    asyncio.create_task(
                        self.execute_arbitrage(symbol, buy_ex, buy_b['ask'], sell_ex, sell_b['bid'])
                    )
        if b2['bid'] > b1['ask']:
            gross_gap_pct = (((b2['bid'] - b1['ask']) / b1['ask']) * 100)
            handle_opportunity(ex1, b1, ex2, b2, gross_gap_pct)

        if b1['bid'] > b2['ask']:
            gross_gap_pct = (((b1['bid'] - b2['ask']) / b2['ask']) * 100)
            handle_opportunity(ex2, b2, ex1, b1, gross_gap_pct)

    def display_metrics(self):
        now = time.time()
        if now - self.last_print > 5:
            print("\n" + "="*80)
            if SIMULATION_MODE:
                total_pnl = self.sim_balance - self.sim_start_balance
                print(f"💰 VIRTUAL WALLET: ${self.sim_balance:.4f} | Total PnL: ${total_pnl:+.4f} | Trades: {self.sim_total_trades}")
            else:
                print(f"📊 LIVE EXECUTION ENGINE - Tracking {len(self.books)} Pairs")
            print("="*80)
            
            gaps = []
            for symbol, exch_data in self.books.items():
                if len(exch_data) >= 2:
                    exchs = list(exch_data.keys())
                    b1, b2 = exch_data[exchs[0]], exch_data[exchs[1]]
                    gap1 = ((b2['bid'] - b1['ask']) / b1['ask']) * 100
                    gap2 = ((b1['bid'] - b2['ask']) / b2['ask']) * 100
                    gaps.append((symbol, max(gap1, gap2), exchs[0], b1, exchs[1], b2))
            
            gaps.sort(key=lambda x: x[1], reverse=True)
            for g in gaps[:8]:
                print(f"🔹 {g[0]:<10} | Max Gap: {g[1]:+.4f}% | {g[2]}: {g[3]['bid']}/{g[3]['ask']} | {g[4]}: {g[5]['bid']}/{g[5]['ask']}")
            
            self.last_print = now


# --- 4. MAIN EXECUTION ---
async def main():
    load_dotenv()
    
    binance = BinanceClient(os.getenv('BINANCE_KEY', ''), os.getenv('BINANCE_SECRET', ''))
    dcx = CoinDCXClient(os.getenv('COINDCX_KEY', ''), os.getenv('COINDCX_SECRET', ''))
    
    state = MarketState(binance, dcx)

    print(f"--- 🚀 Starting Full Market Scanner for {len(SYMBOLS_TO_TRADE)} pairs ---")
    
    await asyncio.gather(
        binance.start_stream(SYMBOLS_TO_TRADE, lambda s, p: state.update_book("Binance", s, p)),
        dcx.start_stream(SYMBOLS_TO_TRADE, lambda s, p: state.update_book("CoinDCX", s, p))
    )

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("\n🛑 Monitor stopped.")