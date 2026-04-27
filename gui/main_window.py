import sys
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QWidget, QSizePolicy,
    QMessageBox, QVBoxLayout
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QTimer, Qt

from gui.tabs.exchanges_tab import ExchangesTab
from gui.tabs.monitoring_tab import MonitoringTab
from gui.tabs.global_registry_tab import GlobalRegistryTab
from gui.tabs.validation_tab import ValidationTab
from gui.dialogs.api_keys_dialog import ApiKeysDialog

from core.live_updater import LiveUpdater


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arbitra1")
        self.resize(1400, 800)

        # Главный таб-виджет
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Создаём вкладки
        self.exchanges_tab = ExchangesTab()
        self.monitoring_tab = MonitoringTab()
        self.global_registry_tab = GlobalRegistryTab()
        self.validation_tab = ValidationTab()

        self.tabs.addTab(self.exchanges_tab, "Биржи")
        self.tabs.addTab(self.monitoring_tab, "Мониторинг")
        self.tabs.addTab(self.global_registry_tab, "Глобальный реестр")
        self.tabs.addTab(self.validation_tab, "Валидация")

        # Подключаем сигнал смены вкладки
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Верхний ToolBar
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        # Кнопка API Keys
        self.action_api_keys = QAction("🔑 API Keys", self)
        self.action_api_keys.triggered.connect(self.open_api_keys_dialog)
        self.toolbar.addAction(self.action_api_keys)

        # LiveUpdater
        self.live_updater = LiveUpdater(["Binance", "Bybit", "OKX"])
        self.live_updater.data_ready.connect(self._on_live_data)
        self.updater_started = False

        QTimer.singleShot(2500, self._start_updater_with_retry)

    def _start_updater_with_retry(self):
        if not self.updater_started:
            self.live_updater.start()
            self.updater_started = True
            print("LiveUpdater запущен")

    def _on_live_data(self, data):
        try:
            current_tab = self.tabs.currentWidget()
            if hasattr(current_tab, 'binance_tab'):
                current_tab.binance_tab.update_spot_table(data.get("spot", {}))
                current_tab.binance_tab.update_futures_table(data.get("futures", {}))
        except Exception as e:
            print(f"Ошибка обновления UI: {e}")

    def _on_tab_changed(self, index):
        current_widget = self.tabs.widget(index)

        # Если перешли НА вкладку Валидация — загружаем карточки
        if current_widget == self.validation_tab:
            self.validation_tab.load_cards()   # ← только здесь!
            return

        # Если уходим С вкладки Валидация
        if hasattr(self, 'validation_tab') and self.validation_tab.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Несохранённые изменения",
                "Настройки карточек были изменены.\nСохранить перед переходом?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.validation_tab.save_all_dirty()

    def open_api_keys_dialog(self):
        dialog = ApiKeysDialog(self)
        dialog.exec()

    def closeEvent(self, event):
        """При закрытии программы спрашиваем сохранение"""
        if hasattr(self, 'validation_tab') and self.validation_tab.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Несохранённые изменения",
                "Есть несохранённые настройки в Валидации.\nСохранить перед выходом?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.validation_tab.save_all_dirty()
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        event.accept()


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())