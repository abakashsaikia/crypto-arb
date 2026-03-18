import json
import websockets
import asyncio
import ssl
import certifi
import time
import hmac
import hashlib
import aiohttp
from urllib.parse import urlencode
from base_client import BaseExchangeClient

class BinanceClient(BaseExchangeClient):
    def __init__(self, api_key="", secret_key=""):
        super().__init__(api_key, secret_key)
        self.ws_uri = "wss://stream.binance.com:9443/ws"
        self.rest_url = "https://api.binance.com"
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def _get_signature(self, params):
        """Generates the cryptographic signature required by Binance for trading."""
        query_string = urlencode(params)
        signature = hmac.new(
            self.secret_key.encode('utf-8'), 
            query_string.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    async def get_balance(self):
        """Fetches live wallet balances to ensure we have enough capital before executing."""
        if not self.api_key or not self.secret_key:
            return {}
            
        endpoint = "/api/v3/account"
        params = {"timestamp": int(time.time() * 1000)}
        query_with_sig = self._get_signature(params)
        headers = {"X-MBX-APIKEY": self.api_key}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.rest_url}{endpoint}?{query_with_sig}", headers=headers) as response:
                data = await response.json()
                balances = {}
                if 'balances' in data:
                    for b in data['balances']:
                        free = float(b['free'])
                        if free > 0:
                            balances[b['asset']] = free
                return balances

    async def place_order(self, symbol, side, order_type, qty, price=None):
        """Executes the trade instantly. Uses FOK to prevent partial fills."""
        endpoint = "/api/v3/order"
        
        # Binance expects symbols without slashes (e.g., 'BTCUSDT')
        native_symbol = symbol.replace("/", "").replace("_", "").upper()
        
        params = {
            "symbol": native_symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": "FOK",  # 🚨 Fill-Or-Kill: If it can't fill instantly, it cancels!
            "quantity": f"{qty:.5f}",
            "price": f"{price:.5f}",
            "timestamp": int(time.time() * 1000)
        }
        
        query_with_sig = self._get_signature(params)
        headers = {"X-MBX-APIKEY": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.rest_url}{endpoint}?{query_with_sig}", headers=headers) as response:
                result = await response.json()
                print(f"⚡ [Binance Execution] {side} {qty} {symbol} @ {price} | Status: {result.get('status', 'FAILED')}")
                return result

    async def start_stream(self, symbols, callback):
        print(f"[Binance] 🔌 Connecting to WebSocket for {len(symbols)} pairs...")
        stream_params = [f"{s.replace('/', '').lower()}@bookTicker" for s in symbols]

        while True:
            try:
                async with websockets.connect(self.ws_uri, ssl=self.ssl_context, ping_interval=20, ping_timeout=20) as ws:
                    print("[Binance] ✅ WebSocket Connected!")
                    payload = {"method": "SUBSCRIBE", "params": stream_params, "id": 1}
                    await ws.send(json.dumps(payload))
                    
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if 's' in data and 'b' in data and 'a' in data:
                            sym = data['s']
                            bid, ask = float(data['b']), float(data['a'])
                            if bid > 0 and ask > 0:
                                callback(self.normalize_symbol(sym), {"bid": bid, "ask": ask})
            except Exception as e:
                print(f"🚨 [Binance] Reconnecting in 5s... ({e})")
                await asyncio.sleep(5)