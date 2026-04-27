from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication
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
        self._loaded = False
        self._dirty_cards = set()
        self.summary_table = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        self.header = QLabel("Валидация сопоставления токенов (0/0)")
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

        # ====================== СВОДНАЯ ТАБЛИЦА ======================
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(7)
        self.summary_table.setHorizontalHeaderLabels([
            "Токен", "Binance", "Bybit", "OKX", "Совпадение", "Выбрано", "Перейти"
        ])
        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.cellDoubleClicked.connect(self._on_table_row_double_click)
        layout.addWidget(self.summary_table)

        QTimer.singleShot(100, self.load_cards)

    def load_cards(self):
        if self._loaded:
            return
        self._loaded = True

        print("[ValidationTab] Начинаем загрузку карточек...")

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
        total = len(sorted_tokens)
        to_show = sorted_tokens[:self.max_cards]

        created = 0
        for token_name in to_show:
            try:
                card = self.create_card(token_name, grouped[token_name])
                self.cards_layout.addWidget(card)
                self.cards.append(card)
                created += 1

                if created % 20 == 0 or created == len(to_show):
                    self.header.setText(f"Валидация сопоставления токенов ({created}/{total})")
                    QApplication.processEvents()
            except Exception as e:
                print(f"[ERROR create_card] {token_name}: {e}")

        self.header.setText(f"Валидация сопоставления токенов ({created}/{total})")
        print(f"[ValidationTab] Загрузка завершена: {created} карточек из {total}")

        self.update_summary_table()

    def create_card(self, token_name: str, entries: list):
        card = QFrame()
        card.setProperty("token_name", token_name)
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; }")

        main_layout = QVBoxLayout(card)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(10, 10, 10, 10)

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
        self.update_summary_table()

    def _save_single_card(self, token_name: str):
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
                    ex_cfg = new_config.get(exchange, {})
                    if "Включить" in cb.text() and "в мониторинг" in cb.text():
                        cb.setChecked(ex_cfg.get("enabled", True))
                    elif cb.property("type") == "spot":
                        cb.setChecked(cb.property("pair") in ex_cfg.get("spot_pairs", []))
                    elif cb.property("type") == "futures":
                        cb.setChecked(cb.property("pair") in ex_cfg.get("futures_pairs", []))
                break

        QMessageBox.information(self, "Сохранено", f"Настройки для {token_name} успешно сохранены.")
        self.update_summary_table()

    def update_summary_table(self):
        """Обновляет сводную таблицу"""
        if not self.summary_table:
            return
        self.summary_table.setRowCount(0)

        for card in self.cards:
            token_name = card.property("token_name")
            if not token_name:
                continue

            config = self.registry.get_monitoring_config(token_name)

            # Собираем биржи, у которых есть Spot с адресом
            spot_exchanges = []
            for exchange in ["Binance", "Bybit", "OKX"]:
                ex_cfg = config.get(exchange, {})
                if ex_cfg.get("enabled") is not None:  # биржа присутствует
                    spot_exchanges.append(exchange)

            total_spot = len(spot_exchanges)                    # Y
            connected = total_spot                              # X (все связанные, если >1)

            row = self.summary_table.rowCount()
            self.summary_table.insertRow(row)

            self.summary_table.setItem(row, 0, QTableWidgetItem(token_name))

            # Binance
            bin_cfg = config.get("Binance", {})
            self.summary_table.setItem(row, 1, QTableWidgetItem("✓" if bin_cfg.get("enabled") else "—"))

            # Bybit
            byb_cfg = config.get("Bybit", {})
            self.summary_table.setItem(row, 2, QTableWidgetItem("✓" if byb_cfg.get("enabled") else "—"))

            # OKX
            okx_cfg = config.get("OKX", {})
            self.summary_table.setItem(row, 3, QTableWidgetItem("✓" if okx_cfg.get("enabled") else "—"))

            # Совпадение
            self.summary_table.setItem(row, 4, QTableWidgetItem(f"{connected}/{total_spot}"))

            # Выбрано
            selected = sum(1 for cfg in [bin_cfg, byb_cfg, okx_cfg] if cfg.get("enabled"))
            self.summary_table.setItem(row, 5, QTableWidgetItem(str(selected)))

            # Перейти
            btn = QPushButton("Перейти")
            btn.clicked.connect(lambda checked, t=token_name: self._scroll_to_card(t))
            self.summary_table.setCellWidget(row, 6, btn)

    def _scroll_to_card(self, token_name: str):
        for card in self.cards:
            if card.property("token_name") == token_name:
                self.scroll.ensureWidgetVisible(card)
                break

    def _on_table_row_double_click(self, row, col):
        item = self.summary_table.item(row, 0)
        if item:
            self._scroll_to_card(item.text())

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
        self.update_summary_table()