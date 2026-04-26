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
        """Инициализация интерфейса вкладки Глобальный реестр"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Заголовок
        self.header_label = QLabel("Глобальный реестр токенов (0)")
        self.header_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(self.header_label)

        # Поиск
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по токену, бирже или сети...")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSortingEnabled(True)

        # Порядок столбцов
        headers = [
            "Токен",
            "Тикер (фьючерсы)",
            "Тип контракта",
            "Биржа",
            "Режим",
            "Сеть",
            "Адрес контракта",
            "Ресурс"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # Настройка заголовка
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(QHeaderView.Interactive)     # ручная регулировка ширины
        header.setStretchLastSection(True)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._sort_table)

        layout.addWidget(self.table)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_import_coingecko = QPushButton("Импорт топ-5000 с CoinGecko")
        self.btn_enrich_spot = QPushButton("Обогатить Spot-контрактами с бирж")
        self.btn_enrich_futures = QPushButton("Обогатить Futures")
        self.btn_clear = QPushButton("Сбросить весь реестр")

        btn_layout.addWidget(self.btn_import_coingecko)
        btn_layout.addWidget(self.btn_enrich_spot)
        btn_layout.addWidget(self.btn_enrich_futures)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        # Сигналы
        self.search_edit.textChanged.connect(self._apply_search_filter)
        self.btn_import_coingecko.clicked.connect(self.import_coingecko)
        self.btn_enrich_spot.clicked.connect(self.enrich_spot_from_exchanges)
        self.btn_enrich_futures.clicked.connect(self.enrich_futures_from_exchanges)
        self.btn_clear.clicked.connect(self.confirm_clear_registry)

        self.load_registry()

    def load_registry(self):
        """Загрузка данных + подсчёт + начальная разумная ширина (можно тянуть вручную)"""
        self.table.setRowCount(0)
        data = self.registry.get_all_tokens()

        # Подсчёт
        binance_spot = bybit_spot = okx_spot = 0
        binance_fut = bybit_fut = okx_fut = 0

        for token in data:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(token.get("token", "")))
            self.table.setItem(row, 1, QTableWidgetItem(token.get("futures_symbol", "")))
            self.table.setItem(row, 2, QTableWidgetItem(token.get("contract_type", "")))
            self.table.setItem(row, 3, QTableWidgetItem(token.get("exchange", "")))
            self.table.setItem(row, 4, QTableWidgetItem(token.get("mode", "")))
            self.table.setItem(row, 5, QTableWidgetItem(token.get("network", "")))
            self.table.setItem(row, 6, QTableWidgetItem(token.get("contract_address", "")))
            self.table.setItem(row, 7, QTableWidgetItem(token.get("source", "")))

            exchange = token.get("exchange", "")
            mode = token.get("mode", "")
            if mode == "Futures":
                if exchange == "Binance": binance_fut += 1
                elif exchange == "Bybit": bybit_fut += 1
                elif exchange == "OKX": okx_fut += 1
            else:
                if exchange == "Binance": binance_spot += 1
                elif exchange == "Bybit": bybit_spot += 1
                elif exchange == "OKX": okx_spot += 1

        # Начальная авто-подгонка
        self.table.resizeColumnsToContents()

        # Фиксированные ширины для проблемных колонок
        self.table.setColumnWidth(5, 220)   # Сеть
        self.table.setColumnWidth(6, 520)   # Адрес контракта

        # Обновление заголовка
        total = len(data)
        stat_text = (
            f"Глобальный реестр токенов ({total}) — "
            f"Binance Spot: {binance_spot} | Bybit Spot: {bybit_spot} | OKX Spot: {okx_spot} | "
            f"Futures: Binance {binance_fut} | Bybit {bybit_fut} | OKX {okx_fut}"
        )
        self.header_label.setText(stat_text)

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

        total = self.registry.enrich_spot_from_exchanges(master_password=password)

        QMessageBox.information(self, "Готово", 
                                f"Обогащение Spot завершено.\n\nДобавлено/обновлено {total} записей.")
        self.load_registry()

    def enrich_futures_from_exchanges(self):
        """Кнопка: Обогащение Futures"""
        password, ok = QInputDialog.getText(
            self, 
            "Мастер-пароль", 
            "Введите мастер-пароль для доступа к API-ключам:", 
            QLineEdit.Password
        )
        if not ok or not password:
            return

        total = self.registry.enrich_futures_from_exchanges(master_password=password)

        QMessageBox.information(self, "Готово", 
                                f"Обогащение Futures завершено.\n\nДобавлено/обновлено {total} записей.")
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

    # ====================== Сортировка и фильтрация ======================
    def _sort_table(self, column: int):
        """Сортировка с переключением Asc/Desc"""
        if not hasattr(self, '_sort_column'):
            self._sort_column = -1
            self._sort_order = Qt.AscendingOrder

        if self._sort_column == column:
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_column = column
            self._sort_order = Qt.AscendingOrder

        self.table.sortItems(column, self._sort_order)

    def _apply_search_filter(self):
        """Фильтрация по всем колонкам без учёта регистра"""
        filter_text = self.search_edit.text().strip().lower()
        if not filter_text:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return

        for row in range(self.table.rowCount()):
            show = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and filter_text in item.text().lower():
                    show = True
                    break
            self.table.setRowHidden(row, not show)