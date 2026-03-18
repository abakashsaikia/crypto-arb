import hmac
import hashlib
import time
import json
import aiohttp
import asyncio
from base_client import BaseExchangeClient

class CoinDCXClient(BaseExchangeClient):
    def __init__(self, api_key="", secret_key=""):
        super().__init__(api_key, secret_key)
        self.base_url = "https://api.coindcx.com"

    async def get_balance(self):
        """Fetches live wallet balances asynchronously to prevent blocking the engine."""
        if not self.api_key or not self.secret_key:
            return {}
            
        endpoint = "/exchange/v1/users/balances"
        body = {"timestamp": int(time.time() * 1000)}
        json_body = json.dumps(body, separators=(',', ':'))
        
        signature = hmac.new(self.secret_key.encode(), json_body.encode(), hashlib.sha256).hexdigest()
        headers = {
            'X-AUTH-APIKEY': self.api_key, 
            'X-AUTH-SIGNATURE': signature, 
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url + endpoint, data=json_body, headers=headers) as response:
                data = await response.json()
                balances = {}
                # CoinDCX returns a list of dictionaries for balances
                if isinstance(data, list):
                    for b in data:
                        free = float(b.get('balance', 0))
                        if free > 0:
                            balances[b['currency']] = free
                return balances

    async def place_order(self, symbol, side, order_type, qty, price=None):
        """Executes the trade instantly. Uses IOC to prevent getting stuck."""
        endpoint = "/exchange/v1/orders/create"
        
        native_symbol = symbol.replace("/", "").replace("_", "").upper()
        
        # 🚨 Force IOC (Immediate-Or-Cancel) to protect against leg risk
        dcx_order_type = "ioc" if order_type in ['limit', 'fok', 'ioc'] else "market_order"

        body = {
            "side": side.lower(),
            "order_type": dcx_order_type,
            "market": native_symbol,
            "total_quantity": round(qty, 5),
            "timestamp": int(time.time() * 1000)
        }
        
        if price: 
            body["price_per_unit"] = round(price, 5)

        json_body = json.dumps(body, separators=(',', ':'))
        signature = hmac.new(self.secret_key.encode(), json_body.encode(), hashlib.sha256).hexdigest()
        
        headers = {
            'X-AUTH-APIKEY': self.api_key, 
            'X-AUTH-SIGNATURE': signature, 
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url + endpoint, data=json_body, headers=headers) as response:
                result = await response.json()
                print(f"⚡ [CoinDCX Execution] {side} {qty} {symbol} @ {price} | Status: {result.get('status', 'FAILED')}")
                return result

    async def start_stream(self, symbols, callback):
        print(f"[CoinDCX] 🔌 Starting Market Scanner for {len(symbols)} pairs...")
        target_symbols = [s.replace("/", "").upper() for s in symbols] 
        ticker_url = "https://api.coindcx.com/exchange/ticker"
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(ticker_url, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            for ticker in data:
                                market = ticker.get('market', '').upper()
                                clean_market = market.replace("-", "").replace("_", "")
                                
                                match_sym = None
                                if clean_market in target_symbols:
                                    match_sym = clean_market
                                elif clean_market.startswith("B") and clean_market[1:] in target_symbols:
                                    match_sym = clean_market[1:]
                                    
                                if match_sym:
                                    bid = float(ticker.get('bid', 0))
                                    ask = float(ticker.get('ask', 0))
                                    if bid > 0 and ask > 0:
                                        callback(self.normalize_symbol(match_sym), {"bid": bid, "ask": ask})
                except Exception: 
                    pass
                await asyncio.sleep(2.0)