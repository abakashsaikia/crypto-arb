import websockets
import json
import ssl
import certifi
import hmac
import hashlib
import time
import requests
import aiohttp
import asyncio
from base_client import BaseExchangeClient

class DeltaClient(BaseExchangeClient):
    def __init__(self, api_key, secret_key):
        super().__init__(api_key, secret_key)
        self.rest_url = "https://api.india.delta.exchange"
        self.ws_uri = "wss://socket.delta.exchange"
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def get_balance(self):
        timestamp = str(int(time.time()))
        signature_data = f"GET{timestamp}/v2/wallet/balances"
        signature = hmac.new(self.secret_key.encode(), signature_data.encode(), hashlib.sha256).hexdigest()
        headers = {'api-key': self.api_key, 'signature': signature, 'timestamp': timestamp, 'Content-Type': 'application/json'}
        try:
            return requests.get(self.rest_url + "/v2/wallet/balances", headers=headers).json()
        except Exception: return {}

    async def place_order(self, symbol, side, order_type, qty, price=None):
        path = "/v2/orders"
        timestamp = str(int(time.time()))
        native_symbol = symbol.replace("/", "")
        
        payload = {
            "symbol": native_symbol,
            "side": side.lower(),
            "order_type": "limit_order" if order_type in ['limit', 'fok'] else "market_order",
            "size": int(qty),
            "time_in_force": "fok" if order_type == 'fok' else "gtc"
        }
        if price: payload["limit_price"] = str(price)

        json_body = json.dumps(payload)
        signature_data = f"POST{timestamp}{path}{json_body}"
        signature = hmac.new(self.secret_key.encode(), signature_data.encode(), hashlib.sha256).hexdigest()
        
        headers = {'api-key': self.api_key, 'signature': signature, 'timestamp': timestamp, 'Content-Type': 'application/json'}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.rest_url + path, data=json_body, headers=headers) as response:
                return await response.json()

    async def start_stream(self, symbols, callback):
        print(f"[Delta]  Connecting to WebSocket for {len(symbols)} pairs...")
        while True:
            try:
                async with websockets.connect(self.ws_uri, ssl=self.ssl_context, ping_interval=20, ping_timeout=20) as ws:
                    print("[Delta]  WebSocket Connected!")
                    payload = {"type": "subscribe", "payload": {"channels": [{"name": "l2_updates", "symbols": symbols}]}}
                    await ws.send(json.dumps(payload))
                    
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get('type') == 'l2_updates':
                            sym = data.get('symbol')
                            bid = float(data['bids'][0][0]) if data.get('bids') else 0
                            ask = float(data['asks'][0][0]) if data.get('asks') else 0
                            
                            if bid > 0 and ask > 0 and sym:
                                callback(self.normalize_symbol(sym), {"bid": bid, "ask": ask})
            except Exception as e:
                print(f" [Delta] Reconnecting in 5s... ({e})")
                await asyncio.sleep(5)