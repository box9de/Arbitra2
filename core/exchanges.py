from binance.spot import Spot
from pybit.unified_trading import HTTP
from okx import MarketData


def get_exchange_class(exchange_name: str):
    """Возвращает класс клиента биржи (точно как в оригинальной версии Arbitra1)."""
    if exchange_name == "Binance":
        return Spot
    elif exchange_name == "Bybit":
        return HTTP
    elif exchange_name == "OKX":
        return MarketData
    else:
        raise ValueError(f"Неизвестная биржа: {exchange_name}")