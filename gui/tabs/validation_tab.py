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

        title = QLabel("Валидация сопоставления токенов")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по токену...")
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(12)
        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить сравнение")
        self.btn_add_selected = QPushButton("Добавить выбранное в мониторинг")
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_add_selected)
        layout.addLayout(btn_layout)

        self.search_edit.textChanged.connect(self.filter_cards)
        self.btn_refresh.clicked.connect(self.load_cards)

    def load_cards(self):
        if self.cards_loaded:
            return
        self.cards_loaded = True

        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        data = self.registry.get_all_tokens()

        # Группируем по токену
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
        """Компактная карточка: пары идут строго влево одна за другой."""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 6px; padding: 4px;")

        layout = QVBoxLayout(frame)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 6, 6, 6)

        # Заголовок
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
            box.setStyleSheet("background-color: #f0f0f0; border-radius: 4px; padding: 4px;")
            box_layout = QVBoxLayout(box)
            box_layout.setSpacing(4)

            box_layout.addWidget(QLabel(f"<b>{exchange_name}</b>"))

            # Сети и адреса
            net_text = "Сети и адреса:\n"
            for e in exchange_entries:
                if e.get("mode") == "Spot":
                    network = e.get("network", "")
                    address = e.get("contract_address", "")
                    if address:
                        net_text += f"• {network} → {address}\n"
                    else:
                        net_text += f"• {network} → (нет адреса)\n"
            net_label = QLabel(net_text.strip())
            net_label.setWordWrap(True)
            net_label.setStyleSheet("font-family: monospace; font-size: 13px;")
            box_layout.addWidget(net_label)

            # Spot-пары — строго влево одна за другой
            spot_pairs = []
            for e in exchange_entries:
                if e.get("mode") == "Spot":
                    spot_pairs = e.get("spot_pairs", [])
                    break
            if spot_pairs:
                box_layout.addWidget(QLabel("<b>Spot-пары:</b>"))
                spot_row = QHBoxLayout()
                spot_row.setSpacing(4)           # минимальное расстояние
                spot_row.setAlignment(Qt.AlignLeft)   # ← строго влево
                for pair in spot_pairs:
                    cb = QCheckBox(pair)
                    cb.setChecked(True)
                    spot_row.addWidget(cb)
                box_layout.addLayout(spot_row)

            # Futures — строго влево одна за другой
            futures_pairs = []
            for e in exchange_entries:
                if e.get("mode") == "Futures":
                    symbol = e.get("futures_symbol")
                    if symbol:
                        futures_pairs.append(symbol)
            futures_pairs = list(dict.fromkeys(futures_pairs))

            if futures_pairs:
                box_layout.addWidget(QLabel("<b>Futures:</b>"))
                futures_row = QHBoxLayout()
                futures_row.setSpacing(4)
                futures_row.setAlignment(Qt.AlignLeft)   # ← строго влево
                for pair in futures_pairs:
                    cb = QCheckBox(pair)
                    cb.setChecked(True)
                    futures_row.addWidget(cb)
                box_layout.addLayout(futures_row)

            # Галочка биржи
            exchange_cb = QCheckBox(f"[✓] Включить {exchange_name} в мониторинг")
            exchange_cb.setChecked(True)
            box_layout.addWidget(exchange_cb)

            layout.addWidget(box)

        return frame

    def filter_cards(self):
        text = self.search_edit.text().strip().lower()
        for i in range(self.cards_layout.count()):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                visible = not text or text in widget.findChild(QLabel).text().lower()
                widget.setVisible(visible)