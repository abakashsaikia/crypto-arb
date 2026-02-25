import asyncio
import websockets
import json
import ssl
import certifi

# Fixes the SSL Certificate issue on Windows
ssl_context = ssl.create_default_context(cafile=certifi.where())

async def stream_market_data(uri, subscribe_payload):
    # the ssl=ssl_context argument added here
    async with websockets.connect(uri, ssl=ssl_context) as websocket:
        await websocket.send(json.dumps(subscribe_payload))
        print(f"Subscribed to {uri}")

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Check for L2 order book updates
                if 'asks' in data and data['asks']:
                    process_order_book(data)
                
            except websockets.ConnectionClosed:
                print("Connection lost. Reconnecting...")
                break

def process_order_book(data):
    symbol = data.get('symbol', 'BTCUSDT')
    
    # Initialize with a placeholder in case the list is empty
    best_bid = "N/A"
    best_ask = "N/A"

    # Safety Check: Does 'bids' exist AND is it not empty?
    if 'bids' in data and len(data['bids']) > 0:
        best_bid = data['bids'][0][0]

    # Safety Check: Does 'asks' exist AND is it not empty?
    if 'asks' in data and len(data['asks']) > 0:
        best_ask = data['asks'][0][0]

    # Only print if we actually got a price update
    if best_bid != "N/A" or best_ask != "N/A":
        print(f"Exch: {symbol} | Bid: {best_bid} | Ask: {best_ask}")