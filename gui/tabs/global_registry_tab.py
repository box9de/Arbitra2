from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel, QLineEdit,
    QProgressDialog, QMessageBox, QCheckBox, QDialog, QInputDialog
)
from PySide6.QtCore import Qt

from core.token_registry import TokenRegistry


class GlobalRegistryTab(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = TokenRegistry()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Заголовок + статистика
        self.header_label = QLabel("Глобальный реестр токенов (0)")
        self.header_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.header_label)

        # Поиск
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по токену, бирже или сети...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Таблица (РАСШИРЕНА)
        self.table = QTableWidget()
        self.table.setColumnCount(8)  # было 6, теперь 8
        self.table.setHorizontalHeaderLabels([
            "Токен", "Биржа", "Режим", "Сеть", 
            "Адрес контракта", "Полный фьючерсный тикер", 
            "Тип контракта", "Ресурс"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_import_coingecko = QPushButton("Импорт топ-5000 с CoinGecko")
        self.btn_import_coingecko.clicked.connect(self.import_coingecko)

        self.btn_enrich_spot = QPushButton("Обогатить Spot-контрактами с бирж")
        self.btn_enrich_spot.clicked.connect(self.enrich_spot_from_exchanges)

        # ← НОВАЯ КНОПКА
        self.btn_enrich_futures = QPushButton("Обогатить Futures")
        self.btn_enrich_futures.clicked.connect(self.enrich_futures_from_exchanges)

        self.btn_clear = QPushButton("Сбросить весь реестр")
        self.btn_clear.clicked.connect(self.confirm_clear_registry)

        btn_layout.addWidget(self.btn_import_coingecko)
        btn_layout.addWidget(self.btn_enrich_spot)
        btn_layout.addWidget(self.btn_enrich_futures)   # ← новая
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        self.load_registry()

    def load_registry(self):
        """Загружает все данные в таблицу + обновляет заголовок"""
        self.table.setRowCount(0)
        data = self.registry.get_all_tokens()

        spot_count = sum(1 for x in data if x.get("mode") == "Spot")
        futures_count = len(data) - spot_count

        # Обновляем заголовок вкладки
        stat_text = f"Глобальный реестр токенов ({len(data)}) — Binance: {spot_count} | Bybit: {spot_count} | OKX: {spot_count} | Futures: {futures_count}"
        self.header_label.setText(stat_text)   # ← исправлено на header_label

        for row_data in data:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(row_data.get("token", "")))
            self.table.setItem(row, 1, QTableWidgetItem(row_data.get("exchange", "")))
            self.table.setItem(row, 2, QTableWidgetItem(row_data.get("mode", "")))
            self.table.setItem(row, 3, QTableWidgetItem(row_data.get("network", "")))
            self.table.setItem(row, 4, QTableWidgetItem(row_data.get("contract_address", "")))
            self.table.setItem(row, 5, QTableWidgetItem(row_data.get("futures_symbol", "") or ""))
            self.table.setItem(row, 6, QTableWidgetItem(row_data.get("contract_type", "") or ""))
            self.table.setItem(row, 7, QTableWidgetItem(row_data.get("source", "")))

        self.table.resizeColumnsToContents()

    def filter_table(self):
        self.load_registry()

    # (остальные методы без изменений — import_from_coingecko, enrich_spot_from_exchanges, confirm_clear_registry)
    def import_from_coingecko(self):
        self.progress = QProgressDialog("Импорт топ-5000 токенов с CoinGecko...", "Отмена", 0, 20, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        real_count = self.registry.import_top_coins_from_coingecko()
        self.progress.close()

        QMessageBox.information(self, "Готово", f"Импортировано/обновлено.\n\nСейчас в реестре: {real_count} токенов")
        self.load_registry()

    def enrich_spot_from_exchanges(self):
        """Кнопка: Обогащение Spot-контрактами с бирж"""
        password, ok = QInputDialog.getText(
            self, 
            "Мастер-пароль", 
            "Введите мастер-пароль для доступа к API-ключам:", 
            QLineEdit.Password
        )
        if not ok or not password:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Обогащение Spot-контрактами")
        dialog.resize(300, 180)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Выберите биржи для обогащения:"))

        cb_binance = QCheckBox("Binance")
        cb_bybit = QCheckBox("Bybit")
        cb_okx = QCheckBox("OKX")

        cb_binance.setChecked(True)
        cb_bybit.setChecked(True)
        cb_okx.setChecked(True)

        layout.addWidget(cb_binance)
        layout.addWidget(cb_bybit)
        layout.addWidget(cb_okx)

        btn_layout = QHBoxLayout()
        btn_start = QPushButton("Начать обогащение")
        btn_cancel = QPushButton("Отмена")
        btn_start.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        if dialog.exec() != QDialog.Accepted:
            return

        self.progress = QProgressDialog("Обогащение Spot-контрактами с бирж...\n(может занять несколько минут)", 
                                        "Отмена", 0, 100, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        total = self.registry.enrich_spot_from_exchanges(
            binance=cb_binance.isChecked(),
            bybit=cb_bybit.isChecked(),
            okx=cb_okx.isChecked(),
            master_password=password
        )

        self.progress.close()

        QMessageBox.information(self, "Готово", 
                                f"Обогащение завершено.\n\nДобавлено/обновлено {total} записей.")
        self.load_registry()

    def confirm_clear_registry(self):
        reply = QMessageBox.question(
            self,
            "ВНИМАНИЕ!",
            "Вы действительно хотите полностью очистить глобальный реестр?\n\n"
            "Все данные будут удалены без возможности восстановления!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.registry.clear_registry()
            QMessageBox.information(self, "Готово", "Реестр полностью очищен.")
            self.load_registry()

    def enrich_futures_from_exchanges(self):
        """Запуск обогащения фьючерсами"""
        password, ok = QInputDialog.getText(
            self, "Мастер-пароль", 
            "Введите мастер-пароль для доступа к API-ключам:", 
            QLineEdit.Password
        )
        if not ok or not password:
            return

        reply = QMessageBox.question(
            self, "Обогащение Futures", 
            "Запустить импорт фьючерсов со всех бирж?\n\n"
            "Это добавит записи с mode = Futures.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        total = self.registry.enrich_futures_from_exchanges(
            binance=True, bybit=True, okx=True, 
            master_password=password
        )

        QMessageBox.information(
            self, "Готово", 
            f"Обогащение Futures завершено.\nДобавлено/обновлено {total} записей."
        )
        self.load_registry()

    def import_coingecko(self):
        """Запуск импорта топ-5000 токенов с CoinGecko"""
        reply = QMessageBox.question(
            self, "CoinGecko Import", 
            "Запустить импорт топ-5000 токенов с CoinGecko?\nЭто может занять несколько минут.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        total = self.registry.import_top_coins_from_coingecko()
        QMessageBox.information(
            self, "Готово", 
            f"Импорт CoinGecko завершён.\nВсего токенов в реестре: {total}"
        )
        self.load_registry()