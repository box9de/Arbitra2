from PySide6.QtWidgets import (
    QWidget, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QProgressDialog, QFileDialog, QMessageBox,
    QHeaderView   # ← добавлено сюда
)
from PySide6.QtCore import Qt
import os
import json
import time

from core.exchanges import get_exchange_class
from core.token_map import token_map
from core.token_registry import token_registry
from data.exchanges.binance_cache import load_markets as load_binance_markets
from data.exchanges.bybit_cache import load_bybit_markets
from data.exchanges.okx_cache import load_okx_markets


class SingleExchangeTab(QWidget):
    def __init__(self, exchange_name, parent=None):
        super().__init__(parent)
        self.exchange_name = exchange_name

        self.inner_tab_widget = QTabWidget()
        self.inner_tab_widget.setTabPosition(QTabWidget.North)
        self.inner_tab_widget.setTabShape(QTabWidget.Rounded)

        self.spot_table = QTableWidget()
        self.futures_table = QTableWidget()

        self.api_key_input = QLineEdit()
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)

        self.save_button = QPushButton("Сохранить ключи")
        self.import_button = QPushButton("Импортировать токены")

        # ← Убрали полностью QProgressDialog (окно загрузки больше не появляется)
        self._setup_tables()
        self._setup_layouts()
        self._load_saved_keys()

    def _setup_tables(self):
        self.spot_table.setColumnCount(8)
        self.spot_table.setHorizontalHeaderLabels([
            "Пара", "Цена", "Объём", "Изменение %", "High", "Low", "Open", "Quote Volume"
        ])
        self.spot_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.spot_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.spot_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.futures_table.setColumnCount(9)
        self.futures_table.setHorizontalHeaderLabels([
            "Пара", "Цена", "Объём", "Funding", "Mark Price", "Index Price", "Change %", "High", "Low"
        ])
        self.futures_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.futures_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.futures_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.inner_tab_widget.addTab(self.spot_table, f"{self.exchange_name} Spot")
        self.inner_tab_widget.addTab(self.futures_table, f"{self.exchange_name} Futures")

    def _setup_layouts(self):
        keys_layout = QHBoxLayout()
        keys_layout.addWidget(QLabel("API Key:"))
        keys_layout.addWidget(self.api_key_input)
        keys_layout.addWidget(QLabel("Secret:"))
        keys_layout.addWidget(self.api_secret_input)
        keys_layout.addWidget(self.save_button)
        keys_layout.addWidget(self.import_button)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(keys_layout)
        main_layout.addWidget(self.inner_tab_widget)

        self.save_button.clicked.connect(self.save_keys)
        self.import_button.clicked.connect(self.import_tokens)

    def _load_saved_keys(self):
        config_file = f"config/{self.exchange_name}_config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.api_key_input.setText(config.get('api_key', ''))
                self.api_secret_input.setText(config.get('api_secret', ''))

    def save_keys(self):
        config = {
            'api_key': self.api_key_input.text(),
            'api_secret': self.api_secret_input.text()
        }
        config_dir = "config"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        with open(f"config/{self.exchange_name}_config.json", 'w') as f:
            json.dump(config, f)
        QMessageBox.information(self, "Успех", "Ключи сохранены.")

    def import_tokens(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Импортировать токены", "", "JSON Files (*.json)")
        if not file_name:
            return

        try:
            with open(file_name, 'r') as f:
                tokens = json.load(f)

            exchange_class = get_exchange_class(self.exchange_name)
            if self.exchange_name == "Binance":
                markets = load_binance_markets()
            elif self.exchange_name == "Bybit":
                markets = load_bybit_markets()
            elif self.exchange_name == "OKX":
                markets = load_okx_markets()
            else:
                markets = {}

            imported_count = 0
            total = len(tokens)
            for i, token in enumerate(tokens):
                # ← Убрали progress.setValue и progress.show/close
                if token in markets:
                    token_registry.add_token(token, self.exchange_name)
                    imported_count += 1

            QMessageBox.information(self, "Успех", f"Импортировано {imported_count} токенов.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать: {str(e)}")
            
    def refresh_data(self):
        try:
            exchange_class = get_exchange_class(self.exchange_name)
            if not exchange_class:
                return

            exchange = exchange_class(
                api_key=self.api_key_input.text(),
                api_secret=self.api_secret_input.text(),
                enable_rate_limit=True
            )

            spot_data = exchange.fetch_tickers()
            futures_data = exchange.fetch_funding_rates()

            self.update_spot_table(spot_data)
            self.update_futures_table(futures_data)

        except Exception as e:
            print(f"Error refreshing {self.exchange_name}: {e}")

    def update_spot_table(self, data):
        self.spot_table.blockSignals(True)
        self.spot_table.setUpdatesEnabled(False)

        # Сняли ограничение 200 строк (теперь грузим ВСЁ)
        sorted_data = sorted(
            data.items(),
            key=lambda x: float(x[1].get('quoteVolume', 0) or 0),
            reverse=True
        )

        needed_rows = len(sorted_data)
        current_rows = self.spot_table.rowCount()

        if needed_rows != current_rows:
            self.spot_table.setRowCount(needed_rows)

        for row, (symbol, ticker) in enumerate(sorted_data):
            price = float(ticker.get('last', 0) or 0)
            volume = float(ticker.get('baseVolume', 0) or 0)
            change = float(ticker.get('percentage', 0) or 0)
            high = float(ticker.get('high', 0) or 0)
            low = float(ticker.get('low', 0) or 0)
            open_price = float(ticker.get('open', 0) or 0)
            quote_volume = float(ticker.get('quoteVolume', 0) or 0)

            self.spot_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.spot_table.setItem(row, 1, QTableWidgetItem(f"{price:.8f}"))
            self.spot_table.setItem(row, 2, QTableWidgetItem(f"{volume:.2f}"))
            self.spot_table.setItem(row, 3, QTableWidgetItem(f"{change:.2f}%"))
            self.spot_table.setItem(row, 4, QTableWidgetItem(f"{high:.8f}"))
            self.spot_table.setItem(row, 5, QTableWidgetItem(f"{low:.8f}"))
            self.spot_table.setItem(row, 6, QTableWidgetItem(f"{open_price:.8f}"))
            self.spot_table.setItem(row, 7, QTableWidgetItem(f"{quote_volume:.2f}"))

        self.spot_table.setUpdatesEnabled(True)
        self.spot_table.blockSignals(False)

    def update_futures_table(self, data):
        self.futures_table.blockSignals(True)
        self.futures_table.setUpdatesEnabled(False)

        # Сняли ограничение 200 строк (по твоей просьбе)
        # + безопасное приведение строк к float (Binance возвращает строки)
        sorted_data = sorted(
            data.items(),
            key=lambda x: float(x[1].get('volume', 0) or x[1].get('quoteVolume', 0) or 0),
            reverse=True
        )

        needed_rows = len(sorted_data)
        current_rows = self.futures_table.rowCount()

        if needed_rows != current_rows:
            self.futures_table.setRowCount(needed_rows)

        for row, (symbol, info) in enumerate(sorted_data):
            price = float(info.get('last', info.get('markPrice', 0) or 0))
            volume = float(info.get('volume', info.get('baseVolume', 0) or 0))
            funding = float(info.get('fundingRate', 0) or 0)
            mark_price = float(info.get('markPrice', 0) or 0)
            index_price = float(info.get('indexPrice', 0) or 0)
            change = float(info.get('percentage', 0) or 0)
            high = float(info.get('high', 0) or 0)
            low = float(info.get('low', 0) or 0)

            self.futures_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.futures_table.setItem(row, 1, QTableWidgetItem(f"{price:.8f}"))
            self.futures_table.setItem(row, 2, QTableWidgetItem(f"{volume:.2f}"))
            self.futures_table.setItem(row, 3, QTableWidgetItem(f"{funding:.6f}"))
            self.futures_table.setItem(row, 4, QTableWidgetItem(f"{mark_price:.8f}"))
            self.futures_table.setItem(row, 5, QTableWidgetItem(f"{index_price:.8f}"))
            self.futures_table.setItem(row, 6, QTableWidgetItem(f"{change:.2f}%"))
            self.futures_table.setItem(row, 7, QTableWidgetItem(f"{high:.8f}"))
            self.futures_table.setItem(row, 8, QTableWidgetItem(f"{low:.8f}"))

        self.futures_table.setUpdatesEnabled(True)
        self.futures_table.blockSignals(False)

    def update_live_data(self, data: dict):
        """Вызывается из MainWindow по сигналу LiveUpdater (точно как в оригинальной версии Arbitra1)."""
        try:
            self.spot_table.setUpdatesEnabled(False)
            self.futures_table.setUpdatesEnabled(False)

            if "spot" in data:
                self.update_spot_table(data["spot"])
            if "futures" in data:
                self.update_futures_table(data["futures"])

            self.spot_table.setUpdatesEnabled(True)
            self.futures_table.setUpdatesEnabled(True)
        except Exception as e:
            print(f"Error in update_live_data for {self.exchange_name}: {e}")