from abc import ABC, abstractmethod

class BaseExchangeClient(ABC):
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key

    @abstractmethod
    def get_balance(self):
        pass

    @abstractmethod
    async def start_stream(self, symbols, callback):
        """Accepts a LIST of symbols to track simultaneously."""
        pass

    @abstractmethod
    async def place_order(self, symbol, side, order_type, qty, price=None):
        """Executes trade. order_type: 'limit', 'market', 'fok'"""
        pass

    def normalize_symbol(self, symbol):
        clean = symbol.replace("-", "").replace("_", "").upper()
        if clean == "BTCUSDT": return "BTC/USDT"
        if clean == "ETHUSDT": return "ETH/USDT"
        if clean == "SOLUSDT": return "SOL/USDT"
        #if clean == "XRPUSDT": return "XRP/USDT"
        return clean