
import asyncio
import os
import time
from dotenv import load_dotenv


from delta_client import DeltaClient
from coindcx_client import CoinDCXClient
from coinswitch_client import CoinSwitchClient 

# --- THE SHARED BRAIN ---
class MarketState:
    def __init__(self):
        self.prices = {
            "Delta": 0.0,
            "CoinDCX": 0.0,
            "CoinSwitch": 0.0
        }
        self.last_print = 0

    def update_price(self, exchange, price):
        self.prices[exchange] = float(price)
        self.check_opportunity()

    def check_opportunity(self):
        # Filter out exchanges with 0.0 price (not connected yet)
        valid_prices = {k: v for k, v in self.prices.items() if v > 0}
        
        if len(valid_prices) < 2:
            return

        # Find Lowest and Highest prices
        min_exch = min(valid_prices, key=valid_prices.get)
        max_exch = max(valid_prices, key=valid_prices.get)
        
        min_price = valid_prices[min_exch]
        max_price = valid_prices[max_exch]

        # Calculate Gap
        diff = max_price - min_price
        percent = (diff / min_price) * 100

        # Create Status String
        status = " | ".join([f"{k}: {v:,.0f}" for k, v in valid_prices.items()])

        # LOGIC: If Profit > 0.5%, TRIGGER ALERT
        if percent > 0.5:
            print(f"\n [ARBITRAGE FOUND] Buy {min_exch} -> Sell {max_exch}")
            print(f"   Profit: {percent:.3f}% (Gap: ${diff:,.2f})")
            print(f"   Prices: {status}\n")
        
        # Else, print heartbeat every 2 seconds
        elif time.time() - self.last_print > 2:
            print(f"[Monitor] Gap: {percent:.2f}% || {status}")
            self.last_print = time.time()

# --- MAIN EXECUTION ---
async def main():
    load_dotenv()
    
    # 1. Initialize Clients
    delta = DeltaClient(os.getenv('DELTA_KEY'), os.getenv('DELTA_SECRET'))
    dcx = CoinDCXClient(os.getenv('COINDCX_KEY'), os.getenv('COINDCX_SECRET'))
    switch = CoinSwitchClient(os.getenv('CS_KEY'), os.getenv('CS_SECRET')) # New Keys
    
    state = MarketState()

    print("---  Starting 3-Way Arbitrage Engine ---")
    
    # 2. Check Balances (Optional, good for verifying keys)
    # print(f"CoinSwitch Balance: {switch.get_balance()}")

    # 3. Define Callback Wrappers
    # These functions connect the Clients to the Brain
    def update_delta(price): state.update_price("Delta", price)
    def update_dcx(price):   state.update_price("CoinDCX", price)
    def update_cs(price):    state.update_price("CoinSwitch", price)

    # 4. Start All Streams
    await asyncio.gather(
        delta.start_stream(update_delta),
        dcx.start_stream(update_dcx),
        switch.start_stream(update_cs)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Bot stopped.")