from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QHBoxLayout, QLabel, QLineEdit,
    QProgressDialog, QMessageBox
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

        # Динамический заголовок с количеством токенов
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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.btn_import_cg = QPushButton("Импорт топ-5000 с CoinGecko")
        self.btn_import_cg.clicked.connect(self.import_from_coingecko)
        btn_layout.addWidget(self.btn_import_cg)

        self.btn_enrich = QPushButton("Обогатить адресами контрактов")
        self.btn_enrich.clicked.connect(self.enrich_contracts)
        btn_layout.addWidget(self.btn_enrich)

        self.btn_clear = QPushButton("Сбросить весь реестр")
        self.btn_clear.clicked.connect(self.confirm_clear_registry)
        btn_layout.addWidget(self.btn_clear)

        layout.addLayout(btn_layout)

        # Первая загрузка
        self.load_registry()

    def load_registry(self):
        """Загрузка данных + обновление заголовка"""
        data = self.registry.get_all_tokens()
        count = len(data)

        # Обновляем заголовок вкладки
        self.title_label.setText(f"Глобальный реестр токенов ({count})")

        self.table.setRowCount(count)

        for row, entry in enumerate(data):
            self.table.setItem(row, 0, QTableWidgetItem(entry.get("token", "")))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("exchange", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("mode", "")))
            self.table.setItem(row, 3, QTableWidgetItem(entry.get("network", "")))
            self.table.setItem(row, 4, QTableWidgetItem(entry.get("contract_address", "—")))
            self.table.setItem(row, 5, QTableWidgetItem(entry.get("source", "")))

    def filter_table(self):
        """Простая перезагрузка при поиске"""
        self.load_registry()

    def import_from_coingecko(self):
        self.progress = QProgressDialog("Импорт топ-5000 токенов с CoinGecko...\n(это может занять 20–40 секунд)", 
                                        "Отмена", 0, 20, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        real_count = self.registry.import_top_coins_from_coingecko()
        self.progress.close()

        QMessageBox.information(self, "Готово", 
                                f"Импортировано/обновлено.\n\nСейчас в реестре: {real_count} токенов")
        self.load_registry()

    def enrich_contracts(self):
        self.progress = QProgressDialog("Обогащение адресами контрактов...\n(это может занять несколько минут)", 
                                        "Отмена", 0, 5000, self)
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        updated = self.registry.enrich_contract_addresses()
        self.progress.close()

        QMessageBox.information(self, "Готово", 
                                f"Добавлено {updated} новых записей с адресами контрактов.")
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