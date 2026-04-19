import time
import requests
from PySide6.QtCore import QThread, Signal, QObject
from binance.spot import Spot
from pybit.unified_trading import HTTP
import okx.MarketData as MarketData
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ← Добавлено: полностью убираем спам httpx в консоль
logging.getLogger("httpx").setLevel(logging.WARNING)

class LiveUpdater(QObject):
    data_ready = Signal(str, object)

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
            tickers_spot = spot_client.ticker_24hr()
            spot_dict = {t['symbol']: t for t in tickers_spot}

            tickers_fut = self._get_binance_futures_tickers()
            fut_dict = {t['symbol']: t for t in tickers_fut}

            funding_rates = self._get_binance_funding_rates()

            return {"spot": spot_dict, "futures": fut_dict, "funding": funding_rates}

        elif exchange_name == "Bybit":
            session = HTTP(testnet=False, api_key="", api_secret="")
            
            # Spot (уже работал)
            tickers_spot = session.get_tickers(category="spot")
            spot_dict = {t['symbol']: t for t in tickers_spot['result']['list']}
            
            # Futures (новое — линейные USDT perpetual)
            tickers_fut = session.get_tickers(category="linear")
            fut_dict = {t['symbol']: t for t in tickers_fut['result']['list']}

            return {"spot": spot_dict, "futures": fut_dict, "funding": {}}

        elif exchange_name == "OKX":
            market = MarketData.MarketAPI(flag="0")
            
            # Spot (уже работал)
            tickers_spot = market.get_tickers(instType="SPOT")
            spot_dict = {t['instId']: t for t in tickers_spot['data']}
            
            # Futures (новое — perpetual SWAP)
            tickers_fut = market.get_tickers(instType="SWAP")
            fut_dict = {t['instId']: t for t in tickers_fut['data']}

            return {"spot": spot_dict, "futures": fut_dict, "funding": {}}
                
    def _get_binance_futures_tickers(self):
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        response = requests.get(url, timeout=5)
        return response.json()

    def _get_binance_funding_rates(self):
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        response = requests.get(url, timeout=5)
        return response.json()