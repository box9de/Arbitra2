from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from collections import defaultdict
from core.token_registry import token_registry


class ValidationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = token_registry
        self.cards = []
        self.max_cards = 80
        self._dirty_cards = set()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        self.header = QLabel("Валидация сопоставления токенов")
        self.header.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.header)

        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по токену...")
        self.search_edit.textChanged.connect(self.filter_cards)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Обновить карточки")
        self.btn_refresh.clicked.connect(self.load_cards)
        self.btn_save_all = QPushButton("Сохранить всё в мониторинг")
        self.btn_save_all.clicked.connect(self.save_all_dirty)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_save_all)
        layout.addLayout(btn_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)

        self.scroll.setWidget(self.cards_widget)
        layout.addWidget(self.scroll)

        QTimer.singleShot(100, self.load_cards)

    def load_cards(self):
        print("[ValidationTab] Очистка и загрузка карточек...")

        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)

        self.cards.clear()
        self._dirty_cards.clear()

        data = self.registry.get_all_tokens()
        grouped = defaultdict(list)
        for entry in data:
            if entry.get("mode") in ("Spot", "Futures"):
                grouped[entry.get("token", "")].append(entry)

        sorted_tokens = sorted(grouped.keys())
        to_show = sorted_tokens[:self.max_cards]

        for token_name in to_show:
            card = self.create_card(token_name, grouped[token_name])
            self.cards_layout.addWidget(card)
            self.cards.append(card)

        print(f"[ValidationTab] Создано карточек: {len(to_show)} из {len(sorted_tokens)}")

    def create_card(self, token_name: str, entries: list):
        card = QFrame()
        card.setProperty("token_name", token_name)
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; }")

        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Заголовок + кнопка Сохранить
        header = QHBoxLayout()
        title = QLabel(f"<b>{token_name}</b>")
        title.setStyleSheet("font-size: 14px;")
        header.addWidget(title)

        save_btn = QPushButton("Сохранить")
        save_btn.setFixedWidth(90)
        save_btn.setEnabled(False)
        save_btn.setProperty("token_name", token_name)
        save_btn.clicked.connect(lambda: self._save_single_card(token_name))
        header.addStretch()
        header.addWidget(save_btn)

        main_layout.addLayout(header)

        by_exchange = defaultdict(list)
        for e in entries:
            by_exchange[e.get("exchange", "Unknown")].append(e)

        saved_config = self.registry.get_monitoring_config(token_name)

        for exchange, ex_entries in by_exchange.items():
            box = QFrame()
            box.setStyleSheet("QFrame { background-color: white; border: 1px solid #e0e0e0; border-radius: 6px; padding: 6px; }")
            box_layout = QVBoxLayout(box)
            box_layout.setSpacing(4)
            box_layout.setContentsMargins(8, 6, 8, 6)

            box_layout.addWidget(QLabel(f"<b>{exchange}</b>"))

            # Сети и адреса
            net_text = "Сети и адреса:\n"
            for e in ex_entries:
                if e.get("mode") == "Spot":
                    net = e.get("network", "-")
                    addr = e.get("contract_address", "-")
                    net_text += f"• {net} → {addr}\n"
            net_label = QLabel(net_text.strip())
            net_label.setWordWrap(True)
            net_label.setStyleSheet("font-family: Consolas; font-size: 12px;")
            box_layout.addWidget(net_label)

            # Spot pairs
            spot_pairs = list(dict.fromkeys([e.get("futures_symbol", "") for e in ex_entries if e.get("mode") == "Spot" and e.get("futures_symbol")]))
            if spot_pairs:
                box_layout.addWidget(QLabel("<b>Spot:</b>"))
                h = QHBoxLayout()
                h.setSpacing(8)
                h.setAlignment(Qt.AlignLeft)
                saved_spot = saved_config.get(exchange, {}).get("spot_pairs", spot_pairs)
                for pair in spot_pairs:
                    cb = QCheckBox(pair)
                    cb.setChecked(pair in saved_spot)
                    cb.setProperty("pair", pair)
                    cb.setProperty("type", "spot")
                    cb.setProperty("token_name", token_name)
                    cb.setProperty("exchange", exchange)
                    cb.stateChanged.connect(lambda: self._on_change(token_name))
                    h.addWidget(cb)
                box_layout.addLayout(h)

            # Futures pairs
            futures_pairs = list(dict.fromkeys([e.get("futures_symbol", "") for e in ex_entries if e.get("mode") == "Futures"]))
            if futures_pairs:
                box_layout.addWidget(QLabel("<b>Futures:</b>"))
                h = QHBoxLayout()
                h.setSpacing(8)
                h.setAlignment(Qt.AlignLeft)
                saved_fut = saved_config.get(exchange, {}).get("futures_pairs", futures_pairs)
                for pair in futures_pairs:
                    cb = QCheckBox(pair)
                    cb.setChecked(pair in saved_fut)
                    cb.setProperty("pair", pair)
                    cb.setProperty("type", "futures")
                    cb.setProperty("token_name", token_name)
                    cb.setProperty("exchange", exchange)
                    cb.stateChanged.connect(lambda: self._on_change(token_name))
                    h.addWidget(cb)
                box_layout.addLayout(h)

            # Включить биржу
            enable_cb = QCheckBox(f"Включить {exchange} в мониторинг")
            enable_cb.setChecked(saved_config.get(exchange, {}).get("enabled", True))
            enable_cb.setProperty("token_name", token_name)
            enable_cb.setProperty("exchange", exchange)
            enable_cb.stateChanged.connect(lambda: self._on_change(token_name))
            box_layout.addWidget(enable_cb)

            main_layout.addWidget(box)

        return card

    def _on_change(self, token_name: str):
        if token_name not in self._dirty_cards:
            self._dirty_cards.add(token_name)
            for card in self.cards:
                if card.property("token_name") == token_name:
                    for btn in card.findChildren(QPushButton):
                        if btn.text() == "Сохранить":
                            btn.setEnabled(True)
                            break
                    break

    def _save_single_card(self, token_name: str):
        """Сохраняем по биржам"""
        config = {}

        for card in self.cards:
            if card.property("token_name") == token_name:
                for cb in card.findChildren(QCheckBox):
                    exchange = cb.property("exchange")
                    if not exchange:
                        continue
                    if exchange not in config:
                        config[exchange] = {"enabled": False, "spot_pairs": [], "futures_pairs": []}

                    if "Включить" in cb.text() and "в мониторинг" in cb.text():
                        config[exchange]["enabled"] = cb.isChecked()
                    elif cb.property("type") == "spot" and cb.isChecked():
                        config[exchange]["spot_pairs"].append(cb.property("pair"))
                    elif cb.property("type") == "futures" and cb.isChecked():
                        config[exchange]["futures_pairs"].append(cb.property("pair"))
                break

        self.registry.save_monitoring_config(token_name, config)
        self._dirty_cards.discard(token_name)

        # Обновляем визуал
        new_config = self.registry.get_monitoring_config(token_name)
        for card in self.cards:
            if card.property("token_name") == token_name:
                for btn in card.findChildren(QPushButton):
                    if btn.text() == "Сохранить":
                        btn.setEnabled(False)
                        break
                for cb in card.findChildren(QCheckBox):
                    exchange = cb.property("exchange")
                    if not exchange:
                        continue
                    ex_config = new_config.get(exchange, {})
                    if "Включить" in cb.text() and "в мониторинг" in cb.text():
                        cb.setChecked(ex_config.get("enabled", True))
                    elif cb.property("type") == "spot":
                        cb.setChecked(cb.property("pair") in ex_config.get("spot_pairs", []))
                    elif cb.property("type") == "futures":
                        cb.setChecked(cb.property("pair") in ex_config.get("futures_pairs", []))
                break

        QMessageBox.information(self, "Сохранено", f"Настройки для {token_name} успешно сохранены.")

    def save_all_dirty(self):
        for token in list(self._dirty_cards):
            self._save_single_card(token)

    def has_unsaved_changes(self) -> bool:
        return len(self._dirty_cards) > 0

    def filter_cards(self):
        text = self.search_edit.text().strip().lower()
        for card in self.cards:
            token = card.property("token_name") or ""
            card.setVisible(text in token.lower())