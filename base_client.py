from abc import ABC, abstractmethod

class BaseExchangeClient(ABC):
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key

    @abstractmethod
    def get_balance(self):
        """Standardize balance into a simple dict: {'BTC': 1.0, 'USDT': 100}"""
        pass

    @abstractmethod
    async def start_stream(self, callback):
        """Standardize incoming price data and pass it to the callback"""
        pass

    def normalize_symbol(self, symbol):
        """
        Forces all symbols into the 'BTC/USDT' format.
        Each exchange has a different native format.
        """
        # Remove any common separators used by exchanges
        clean = symbol.replace("-", "").replace("_", "").upper()
        
        # Standardize known variations
        if clean == "BTCUSDT": return "BTC/USDT"
        if clean == "ETHUSDT": return "ETH/USDT"
        return clean # Fallback