import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QBrush


class MonitoringTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.start_auto_update()

    def init_ui(self):
        # Основной layout
        main_layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("Мониторинг спредов")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Биржа 1", "Пара", "Спред", "Биржа 2", "Пара", "Спред"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setRowCount(0)
        main_layout.addWidget(self.table)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh_data)
        btn_layout.addWidget(self.btn_refresh)

        self.btn_start = QPushButton("Старт автообновления")
        self.btn_start.clicked.connect(self.start_auto_update)
        btn_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Стоп автообновления")
        self.btn_stop.clicked.connect(self.stop_auto_update)
        btn_layout.addWidget(self.btn_stop)

        main_layout.addLayout(btn_layout)

        # Статус
        self.status_label = QLabel("Автообновление: ВЫКЛ")
        main_layout.addWidget(self.status_label)

    def refresh_data(self):
        # Заполнение таблицы (заглушка)
        rows = [
            ["Binance", "BTC/USDT", "0.12%", "OKX", "BTC/USDT", "0.15%"],
            ["Bybit", "ETH/USDT", "0.08%", "Binance", "ETH/USDT", "0.10%"]
        ]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                item = QTableWidgetItem(text)
                if "0." in text:
                    item.setForeground(QBrush(QColor("green")))
                self.table.setItem(r, c, item)

    def start_auto_update(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(3000)  # каждые 3 сек
        self.status_label.setText("Автообновление: ВКЛ (3 сек)")

    def stop_auto_update(self):
        if hasattr(self, "timer"):
            self.timer.stop()
        self.status_label.setText("Автообновление: ВЫКЛ")