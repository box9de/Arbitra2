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

        # Заголовок с подробной статистикой
        self.title_label = QLabel("Глобальный реестр токенов (0)")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.title_label)

        # Поиск
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по токену, бирже или сети...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(QLabel("Поиск:"))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Токен", "Биржа", "Режим", "Сеть", "Адрес контракта", "Ресурс"
        ])

        # Настройка ширины столбцов
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # Токен
        header.setSectionResizeMode(1, QHeaderView.Fixed)              # Биржа
        header.setSectionResizeMode(2, QHeaderView.Fixed)              # Режим
        header.setSectionResizeMode(3, QHeaderView.Fixed)              # Сеть
        header.setSectionResizeMode(4, QHeaderView.Stretch)            # Адрес контракта — максимально широкий
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)   # Ресурс

        self.table.setColumnWidth(1, 90)   # Биржа
        self.table.setColumnWidth(2, 70)   # Режим
        self.table.setColumnWidth(3, 90)   # Сеть
        self.table.setColumnWidth(5, 180)  # Ресурс

        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.btn_import_cg = QPushButton("Импорт топ-5000 с CoinGecko")
        self.btn_import_cg.clicked.connect(self.import_from_coingecko)
        btn_layout.addWidget(self.btn_import_cg)

        self.btn_enrich_exchanges = QPushButton("Обогатить Spot-контрактами с бирж")
        self.btn_enrich_exchanges.clicked.connect(self.enrich_spot_from_exchanges)
        btn_layout.addWidget(self.btn_enrich_exchanges)

        self.btn_clear = QPushButton("Сбросить весь реестр")
        self.btn_clear.clicked.connect(self.confirm_clear_registry)
        btn_layout.addWidget(self.btn_clear)

        layout.addLayout(btn_layout)

        self.load_registry()

    def load_registry(self):
        data = self.registry.get_all_tokens()
        count = len(data)

        # Подсчёт по биржам
        stats = {"Binance": 0, "Bybit": 0, "OKX": 0, "CoinGecko": 0}
        for entry in data:
            ex = entry.get("exchange", "Unknown")
            if ex in stats:
                stats[ex] += 1
            else:
                stats["CoinGecko"] += 1  # всё остальное считаем CoinGecko

        # Красивый заголовок
        stat_text = (f"Глобальный реестр токенов ({count}) — "
                     f"Binance: {stats['Binance']} | "
                     f"Bybit: {stats['Bybit']} | "
                     f"OKX: {stats['OKX']} | "
                     f"CoinGecko: {stats['CoinGecko']}")
        self.title_label.setText(stat_text)

        self.table.setRowCount(count)

        for row, entry in enumerate(data):
            self.table.setItem(row, 0, QTableWidgetItem(entry.get("token", "")))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("exchange", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("mode", "")))
            self.table.setItem(row, 3, QTableWidgetItem(entry.get("network", "")))
            self.table.setItem(row, 4, QTableWidgetItem(entry.get("contract_address", "—")))
            self.table.setItem(row, 5, QTableWidgetItem(entry.get("source", "")))

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