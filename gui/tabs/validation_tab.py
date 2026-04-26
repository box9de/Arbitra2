from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Qt

from core.token_registry import token_registry


class ValidationTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.registry = token_registry
        self.cards_loaded = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Заголовок
        title = QLabel("Валидация сопоставления токенов")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Поиск
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по токену...")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Область с карточками
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(12)
        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll)

        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить сравнение")
        self.btn_add_selected = QPushButton("Добавить выбранное в мониторинг")
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_add_selected)
        layout.addLayout(btn_layout)

        # Сигналы
        self.search_edit.textChanged.connect(self.filter_cards)
        self.btn_refresh.clicked.connect(self.load_cards)

        # Загружаем карточки только при первом переходе на вкладку
        # (вызов происходит из main_window.py при смене вкладки)

    def load_cards(self):
        """Загружаем карточки (вызывается при переходе на вкладку)"""
        if self.cards_loaded:
            return
        self.cards_loaded = True

        # Очистка предыдущих карточек
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        data = self.registry.get_all_tokens()

        # Группируем записи по токену (одна карточка = один токен)
        tokens = {}
        for entry in data:
            token_name = entry.get("token", "").upper()
            if token_name not in tokens:
                tokens[token_name] = []
            tokens[token_name].append(entry)

        for token_name, entries in tokens.items():
            card = self.create_card(token_name, entries)
            self.cards_layout.addWidget(card)

    def create_card(self, token_name: str, entries: list):
        """Создаёт одну подробную карточку на токен"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; padding: 10px;")

        layout = QVBoxLayout(frame)
        layout.setSpacing(10)

        # Заголовок карточки
        header = QHBoxLayout()
        title = QLabel(token_name)
        title.setStyleSheet("font-weight: bold; font-size: 15px;")
        status = QLabel("Статус: Частичное совпадение")
        status.setStyleSheet("color: orange; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(status)
        layout.addLayout(header)

        # ==================== БЛОКИ БИРЖ ====================
        for exchange_name in ["Binance", "Bybit", "OKX"]:
            exchange_entries = [e for e in entries if e.get("exchange") == exchange_name]
            if not exchange_entries:
                continue

            box = QFrame()
            box.setStyleSheet("background-color: #f0f0f0; border-radius: 6px; padding: 8px;")
            box_layout = QVBoxLayout(box)

            box_layout.addWidget(QLabel(f"<b>{exchange_name}</b>"))

            # Сети и адреса
            net_text = "Сети и адреса:\n"
            for e in exchange_entries:
                if e.get("mode") == "Spot":
                    network = e.get("network", "")
                    address = e.get("contract_address", "")
                    addr_short = address[:12] + "..." if address else "—"
                    net_text += f"   • {network} → {addr_short}\n"
            box_layout.addWidget(QLabel(net_text.strip()))

            # Spot-пары
            spot_pairs = []
            for e in exchange_entries:
                if e.get("mode") == "Spot":
                    spot_pairs = e.get("spot_pairs", [])
                    break
            if spot_pairs:
                box_layout.addWidget(QLabel("<b>Spot-пары:</b>"))
                for pair in spot_pairs:
                    cb = QCheckBox(pair)
                    cb.setChecked(True)
                    box_layout.addWidget(cb)

            # Futures
            futures_pairs = []
            for e in exchange_entries:
                if e.get("mode") == "Futures":
                    futures_pairs.extend(e.get("futures_pairs", []))
            futures_pairs = list(dict.fromkeys(futures_pairs))  # убираем дубликаты

            if futures_pairs:
                box_layout.addWidget(QLabel("<b>Futures:</b>"))
                for pair in futures_pairs:
                    cb = QCheckBox(pair)
                    cb.setChecked(True)
                    box_layout.addWidget(cb)

            # Галочка всей биржи
            exchange_cb = QCheckBox(f"[✓] Включить {exchange_name} в мониторинг")
            exchange_cb.setChecked(True)
            box_layout.addWidget(exchange_cb)

            layout.addWidget(box)

        return frame

    def filter_cards(self):
        """Фильтрация карточек по поиску"""
        text = self.search_edit.text().strip().lower()
        for i in range(self.cards_layout.count()):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                visible = not text or text in widget.findChild(QLabel).text().lower()
                widget.setVisible(visible)