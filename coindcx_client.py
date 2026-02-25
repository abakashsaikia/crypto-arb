import hmac
import hashlib
import time
import json
import requests
import asyncio
import aiohttp
from base_client import BaseExchangeClient

class CoinDCXClient(BaseExchangeClient):
    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key)
        self.base_url = "https://api.coindcx.com"

    def get_balance(self):
        body = {"timestamp": int(time.time() * 1000)}
        json_body = json.dumps(body, separators=(',', ':'))
        signature = hmac.new(self.secret_key.encode(), json_body.encode(), hashlib.sha256).hexdigest()
        headers = {'X-AUTH-APIKEY': self.api_key, 'X-AUTH-SIGNATURE': signature, 'Content-Type': 'application/json'}
        try:
            return requests.post(self.base_url + "/exchange/v1/users/balances", data=json_body, headers=headers).json()
        except Exception: return {}

    async def start_stream(self, callback):
        print("[CoinDCX]  Starting L2 Order Book Poller...")
        
        # We use the public market data path which is often more stable for L2
        url = "https://public.coindcx.com/market_data/orderbook?pair=B-BTC_USDT"
        
        # Headers to prevent 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-AUTH-APIKEY": self.api_key  # Some L2 endpoints now require the key for rate-limiting
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            while True:
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # CoinDCX L2 Parsing
                            bids_dict = data.get('bids', {})
                            asks_dict = data.get('asks', {})
                            
                            if bids_dict and asks_dict:
                                # Convert string keys to floats and find top levels
                                best_bid = max(float(p) for p in bids_dict.keys())
                                best_ask = min(float(p) for p in asks_dict.keys())
                                
                                symbol = self.normalize_symbol("BTCUSDT")
                                callback(symbol, {"bid": best_bid, "ask": best_ask})
                        
                        elif response.status == 403:
                            print("[CoinDCX Error] 403 Forbidden - Trying fallback headers...")
                            # Fallback: Sometimes the API prefers no trailing slash or a different subdomain
                            url = "https://api.coindcx.com/exchange/v1/market_data/orderbook?pair=B-BTC_USDT"
                            
                        else:
                            print(f"[CoinDCX Error] Status {response.status}")
                            
                except Exception as e:
                    print(f"[CoinDCX Exception] {e}")
                
                # Wait 2 seconds to avoid aggressive rate-limiting
                await asyncio.sleep(2.0)