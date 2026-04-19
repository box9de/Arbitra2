import time
import threading
import requests
from PySide6.QtCore import QThread, Signal, QObject
from binance.spot import Spot
from binance.um_futures import UMFutures
from pybit.unified_trading import HTTP
from okx import MarketData
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiveUpdater(QObject):
    data_ready = Signal(str, object)  # exchange_name, data_dict

    def __init__(self, exchanges):
        super().__init__()
        self.exchanges = exchanges
        self.running = False
        self.thread = QThread()
        self.moveToThread(self.thread)

    def start(self):
        self.running = True
        self.thread.started.connect(self.run)
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.quit()
        self.thread.wait()

    def run(self):
        while self.running:
            for exchange_name in self.exchanges:
                try:
                    data = self._fetch_live_data(exchange_name)
                    self.data_ready.emit(exchange_name, data)
                except Exception as e:
                    logger.error(f"[LiveUpdater] {exchange_name} error: {e}")
            time.sleep(1)

    def _fetch_live_data(self, exchange_name):
        if exchange_name == "Binance":
            spot_client = Spot()
            futures_client = UMFutures()
            tickers_spot = spot_client.ticker_24hr()
            tickers_fut = futures_client.ticker_24hr_price_change()
            funding_rates = self._get_binance_funding_rates()
            return {"spot": tickers_spot, "futures": tickers_fut, "funding": funding_rates}

        elif exchange_name == "Bybit":
            session = HTTP(testnet=False, api_key="", api_secret="")
            tickers = session.get_tickers(category="spot", symbol="*")
            funding = session.get_funding_rate(symbol="*")
            return {"spot": tickers, "funding": funding}

        elif exchange_name == "OKX":
            market = MarketData()
            tickers = market.get_tickers(instType="SPOT")
            funding = market.get_funding_rate(instType="SWAP")
            return {"spot": tickers, "funding": funding}

    def _get_binance_funding_rates(self):
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        response = requests.get(url, timeout=5)
        return response.json()