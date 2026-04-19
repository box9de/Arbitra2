import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar, QPushButton
from PySide6.QtCore import QTimer, Signal, Slot
from gui.tabs.exchanges_tab import ExchangesTab
from gui.tabs.monitoring_tab import MonitoringTab
from core.live_updater import LiveUpdater
from loguru import logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arbitra1")
        self.resize(1400, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tabs.addTab(ExchangesTab(), "Биржи")
        self.tabs.addTab(MonitoringTab(), "Мониторинг")

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов")

        self.auto_update_btn = QPushButton("Автообновление")
        self.auto_update_btn.clicked.connect(self.toggle_auto_update)
        self.status_bar.addPermanentWidget(self.auto_update_btn)

        self.live_updater = LiveUpdater(["Binance", "Bybit", "OKX"])
        self.live_updater.data_ready.connect(self._on_live_data)
        self.updater_started = False

        # Задержка запуска LiveUpdater (точно как в оригинале)
        QTimer.singleShot(2500, self._start_updater_with_retry)

    def _start_updater_with_retry(self):
        if self._are_tabs_ready():
            self._start_live_updater()
        else:
            QTimer.singleShot(500, self._start_updater_with_retry)

    def _are_tabs_ready(self):
        current = self.tabs.currentWidget()
        return (hasattr(current, 'binance_tab') and
                hasattr(current, 'bybit_tab') and
                hasattr(current, 'okx_tab'))

    def _start_live_updater(self):
        if not self.updater_started:
            self.live_updater.start()
            self.updater_started = True
            self.status_bar.showMessage("LiveUpdater запущен")
            logger.info("LiveUpdater запущен")

    def toggle_auto_update(self):
        if self.live_updater.isRunning():
            self.live_updater.stop()
            self.updater_started = False
            self.status_bar.showMessage("Автообновление остановлено")
        else:
            self._start_live_updater()

    @Slot(str, object)
    def _on_live_data(self, exchange_name, data):
        if not self._are_tabs_ready():
            return
        tab_widget = self.tabs.currentWidget()
        if exchange_name == "Binance":
            tab_widget.binance_tab.update_spot_table(data.get("spot", {}))
            tab_widget.binance_tab.update_futures_table(data.get("futures", {}))
        elif exchange_name == "Bybit":
            tab_widget.bybit_tab.update_spot_table(data.get("spot", {}))
            tab_widget.bybit_tab.update_futures_table(data.get("futures", {}))
        elif exchange_name == "OKX":
            tab_widget.okx_tab.update_spot_table(data.get("spot", {}))
            tab_widget.okx_tab.update_futures_table(data.get("futures", {}))

    def closeEvent(self, event):
        if hasattr(self, 'live_updater') and self.live_updater.isRunning():
            self.live_updater.stop()
        event.accept()