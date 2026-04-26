import sys
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QApplication, QWidget, QSizePolicy
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QTimer, Signal, Slot

from gui.tabs.exchanges_tab import ExchangesTab
from gui.tabs.monitoring_tab import MonitoringTab
from gui.tabs.global_registry_tab import GlobalRegistryTab
from gui.dialogs.api_keys_dialog import ApiKeysDialog

from core.live_updater import LiveUpdater
from loguru import logger


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arbitra1")
        self.resize(1400, 800)

        # Главный QTabWidget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tabs.addTab(ExchangesTab(), "Биржи")
        self.tabs.addTab(MonitoringTab(), "Мониторинг")
        self.tabs.addTab(GlobalRegistryTab(), "Глобальный реестр")

        # Вкладка Валидация
        from gui.tabs.validation_tab import ValidationTab
        self.validation_tab = ValidationTab()
        self.tabs.addTab(self.validation_tab, "Валидация")

        # Подключаем сигнал смены вкладки
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Верхний ToolBar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        self.action_api_keys = QAction("🔑 API Keys", self)
        self.action_api_keys.triggered.connect(self.open_api_keys_dialog)
        self.toolbar.addAction(self.action_api_keys)

        # LiveUpdater
        self.live_updater = LiveUpdater(["Binance", "Bybit", "OKX"])
        self.live_updater.data_ready.connect(self._on_live_data)
        self.updater_started = False

        QTimer.singleShot(2500, self._start_updater_with_retry)

    def on_tab_changed(self, index):
        """Вызывается при переключении вкладок"""
        if self.tabs.tabText(index) == "Валидация":
            # Загружаем карточки только при переходе на вкладку
            if hasattr(self.validation_tab, 'load_cards'):
                self.validation_tab.load_cards()

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
            logger.info("LiveUpdater запущен")

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

    def open_api_keys_dialog(self):
        """Открывает окно управления API-ключами"""
        dialog = ApiKeysDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        if hasattr(self, 'live_updater') and self.live_updater.running:
            self.live_updater.stop()
        event.accept()