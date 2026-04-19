from PySide6.QtWidgets import QTabWidget

from gui.tabs.single_exchange_tab import SingleExchangeTab


class ExchangesTab(QTabWidget):
    def __init__(self):
        super().__init__()
        self.binance_tab = SingleExchangeTab("Binance")
        self.bybit_tab = SingleExchangeTab("Bybit")
        self.okx_tab = SingleExchangeTab("OKX")

        self.addTab(self.binance_tab, "Binance")
        self.addTab(self.bybit_tab, "Bybit")
        self.addTab(self.okx_tab, "OKX")