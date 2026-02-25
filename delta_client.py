import websockets
import json
import ssl
import certifi
import hmac
import hashlib
import time
import requests
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

    async def start_stream(self, callback):
        print("[Delta]  Connecting to WebSocket...")
        async with websockets.connect(self.ws_uri, ssl=self.ssl_context) as ws:
            payload = {"type": "subscribe", "payload": {"channels": [{"name": "l2_updates", "symbols": ["BTCUSDT"]}]}}
            await ws.send(json.dumps(payload))
            
            while True:
                try:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get('type') == 'l2_updates':
                        # Extract Best Bid and Best Ask
                        bid = float(data['bids'][0][0]) if data.get('bids') else 0
                        ask = float(data['asks'][0][0]) if data.get('asks') else 0
                        
                        if bid > 0 and ask > 0:
                            callback(self.normalize_symbol("BTCUSDT"), {"bid": bid, "ask": ask})
                except Exception: pass