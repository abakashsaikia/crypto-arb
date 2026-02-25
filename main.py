import asyncio
import os
import time
from dotenv import load_dotenv

# Import your custom normalized clients
from delta_client import DeltaClient
from coindcx_client import CoinDCXClient
from coinswitch_client import CoinSwitchClient # ADDED THIS IMPORT

# --- THE SHARED BRAIN ---
class MarketState:
    def __init__(self):
        self.books = {}
        self.last_print = 0
        self.fee = 0.001 

    def update_book(self, exchange, symbol, book_data):
        if symbol not in self.books:
            self.books[symbol] = {}
        self.books[symbol][exchange] = book_data
        
        # Run detection engines
        self.check_cross_exchange(symbol)
        self.check_triangular(exchange)
        # Call the single, logic-filled display function
        self.display_metrics()

    def check_cross_exchange(self, symbol):
        if symbol not in self.books: return
        exchs = list(self.books[symbol].keys())
        # We need at least 2 exchanges to compare
        if len(exchs) < 2: return

        # We will just compare the first two exchanges that report in
        ex1, ex2 = exchs[0], exchs[1]
        b1, b2 = self.books[symbol][ex1], self.books[symbol][ex2]

        # --- SETTINGS ---
        total_fees_pct = 0.3 
        slippage_pct = 0.02 
        transfer_pct = 0.2 

        # --- CALCULATION ---
        gross_spread = ((b2['bid'] - b1['ask']) / b1['ask']) * 100
        net_profit = gross_spread - total_fees_pct - slippage_pct - transfer_pct

        if net_profit > 0:
            print(f" [REAL PROFIT] {symbol}: {net_profit:.3f}%")
            print(f"   Details: Gross({gross_spread:.3f}%) - Costs({total_fees_pct + slippage_pct + transfer_pct}%)")
        
        return net_profit
        
    def check_triangular(self, exchange):
        try:
            rate1 = 1 / self.books['BTC/USDT'][exchange]['ask']
            rate2 = 1 / self.books['ETH/BTC'][exchange]['ask']
            rate3 = self.books['ETH/USDT'][exchange]['bid']

            final_amount = (1 * rate1 * rate2 * rate3) - (self.fee * 3)
            if final_amount > 1.0:
                profit = (final_amount - 1) * 100
                print(f" [TRI] {exchange} PROFIT: {profit:.3f}%")
        except KeyError:
            pass 

    def display_metrics(self):
        now = time.time()
        if now - self.last_print > 2:
            print("\n" + "="*70)
            print(f" 3-WAY MONITORING - {time.strftime('%H:%M:%S')}")
            print("="*70)
            
            for symbol, exch_data in self.books.items():
                if len(exch_data) >= 2:
                    exchs = list(exch_data.keys())
                    # Display the first two exchanges
                    b1, b2 = exch_data[exchs[0]], exch_data[exchs[1]]
                    gap = ((b2['bid'] - b1['ask']) / b1['ask']) * 100
                    print(f" {symbol:<10} | Gap: {gap:.4f}% | {exchs[0]} Ask: {b1['ask']:.2f} | {exchs[1]} Bid: {b2['bid']:.2f}")
                    
                    # If CoinSwitch (or a 3rd) is present, print it too
                    if len(exchs) >= 3:
                        b3 = exch_data[exchs[2]]
                        print(f"   {exchs[2]} is currently reporting Bid: {b3['bid']:.2f} | Ask: {b3['ask']:.2f}")

                else:
                    print(f" {symbol:<10} | Waiting for data from all exchanges...")

            self.last_print = now

# --- MAIN EXECUTION ---
async def main():
    load_dotenv()
    
    # 1. Initialize Clients 
    delta = DeltaClient(os.getenv('DELTA_KEY'), os.getenv('DELTA_SECRET'))
    dcx = CoinDCXClient(os.getenv('COINDCX_KEY'), os.getenv('COINDCX_SECRET'))
    # Using dummy keys for CS since the public ticker doesn't need them
    cs = CoinSwitchClient("dummy_key", "dummy_secret") 
    
    state = MarketState()

    print("---  Starting Normalized 3-Way Price Monitor ---")

    # 2. Define Callbacks 
    def cb_delta(sym, p): state.update_book("Delta", sym, p)
    def cb_dcx(sym, p):   state.update_book("CoinDCX", sym, p)
    def cb_cs(sym, p):    state.update_book("CoinSwitch", sym, p) # ADDED

    # 3. Start Streams
    await asyncio.gather(
        delta.start_stream(cb_delta),
        dcx.start_stream(cb_dcx),
        cs.start_stream(cb_cs) # ADDED
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Monitor stopped by user.")