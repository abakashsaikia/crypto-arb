import asyncio
import os
from dotenv import load_dotenv
from binance_client import BinanceClient
from coindcx_client import CoinDCXClient

async def test_execution():
    load_dotenv()
    
    print("--- 🚀 STARTING LIVE API TEST ---")
    
    # Load your new trading keys
    binance = BinanceClient(os.getenv('BINANCE_KEY'), os.getenv('BINANCE_SECRET'))
    dcx = CoinDCXClient(os.getenv('COINDCX_KEY'), os.getenv('COINDCX_SECRET'))
    
    # 1. Test Balances First
    print("\n🔍 Checking Balances...")
    binance_bal = await binance.get_balance()
    dcx_bal = await dcx.get_balance()
    
    print(f"Binance USDT: {binance_bal.get('USDT', 0)}")
    print(f"CoinDCX USDT: {dcx_bal.get('USDT', 0)}")
    
    # 2. Test Small Order (Buying 15 TRX is roughly $2.00)
    # WARNING: This will execute a real trade!
    print("\n⚡ Attempting simultaneous test orders (FOK/IOC)...")
    
    # We set an artificially low price so it gets instantly rejected/cancelled (to keep your money safe)
    test_price = 0.01 
    
    results = await asyncio.gather(
        binance.place_order("TRX/USDT", "BUY", "limit", qty=15, price=test_price),
        dcx.place_order("TRX/USDT", "BUY", "limit", qty=15, price=test_price),
        return_exceptions=True
    )
    
    print("\n✅ [BINANCE RESULT]:", results[0])
    print("✅ [COINDCX RESULT]:", results[1])

if __name__ == "__main__":
    asyncio.run(test_execution())