import hmac
import hashlib
import time
import json
import asyncio
import aiohttp
from base_client import BaseExchangeClient

class CoinSwitchClient(BaseExchangeClient):
    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key)
        self.market_url = "https://coinswitch.co/trade/api/v2/24hr/ticker"

    def get_balance(self):
        return {}

    async def start_stream(self, callback):
        print("[CoinSwitch]  Starting API Cracker...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # A list of combinations to brute-force the correct API requirement
        test_payloads = [
            # 1. Standard GET with different keys
            {"method": "GET", "params": {"symbol": "BTC/USDT"}, "json": None},
            {"method": "GET", "params": {"market": "BTC/USDT"}, "json": None},
            {"method": "GET", "params": {"pair": "BTC/USDT"}, "json": None},
            {"method": "GET", "params": {"symbol": "BTCUSDT"}, "json": None},
            # 2. POST requests with JSON bodies (Very common for strict APIs)
            {"method": "POST", "params": None, "json": {"symbol": "BTC/USDT"}},
            {"method": "POST", "params": None, "json": {"market": "BTC/USDT"}},
            {"method": "POST", "params": None, "json": {"symbol": "BTCUSDT"}},
        ]
        
        success_config = None # This will save the working configuration once found

        async with aiohttp.ClientSession(headers=headers) as session:
            while True:
                try:
                    # --- PHASE 1: FIND THE RIGHT FORMAT ---
                    if not success_config:
                        for config in test_payloads:
                            print(f"[CoinSwitch] Testing: {config['method']} with {config['params'] or config['json']}")
                            
                            if config['method'] == "GET":
                                response = await session.get(self.market_url, params=config['params'], timeout=5)
                            else:
                                response = await session.post(self.market_url, json=config['json'], timeout=5)

                            if response.status == 200:
                                print(f" [CoinSwitch] SUCCESS! Found correct format: {config}")
                                success_config = config
                                break # Stop testing, we found it!
                            else:
                                error_msg = await response.text()
                                print(f" [CoinSwitch] Failed: {response.status} - {error_msg[:60]}")
                            
                            await asyncio.sleep(1) # Small delay between tests
                            
                    # --- PHASE 2: STREAM DATA (Once format is found) ---
                    if success_config:
                        if success_config['method'] == "GET":
                            response = await session.get(self.market_url, params=success_config['params'], timeout=5)
                        else:
                            response = await session.post(self.market_url, json=success_config['json'], timeout=5)

                        if response.status == 200:
                            data = await response.json()
                            ticker = data.get('data', data)

                            # Parse Bid and Ask
                            bid = float(ticker.get('b') or ticker.get('bid') or ticker.get('c') or 0)
                            ask = float(ticker.get('a') or ticker.get('ask') or ticker.get('c') or 0)

                            if bid > 0 and ask > 0:
                                symbol = self.normalize_symbol("BTCUSDT")
                                callback(symbol, {"bid": bid, "ask": ask})
                                
                except Exception as e:
                    pass 
                
                await asyncio.sleep(2.0)