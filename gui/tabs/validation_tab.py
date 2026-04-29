from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QLineEdit, QPushButton, QCheckBox, QMessageBox, 
    QTableWidget, QTableWidgetItem, QHeaderView, QApplication, QSplitter
)
from PySide6.QtCore import Qt, QTimer
from collections import defaultdict
from core.token_registry import token_registry


class ValidationTab(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = token_registry
        self.cards = []
        self._loaded = False
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

        # ====================== СВОДНАЯ ТАБЛИЦА ======================
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(7)
        self.summary_table.setHorizontalHeaderLabels(["Токен", "Binance", "Bybit", "OKX", "Совпадение", "Выбрано", "Перейти"])

        header = self.summary_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.sectionClicked.connect(self._sort_table)
        self.summary_table.sortItems(4, Qt.DescendingOrder)   # сортировка по умолчанию
        self.summary_table.resizeColumnsToContents()

        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.cellDoubleClicked.connect(self._on_table_row_double_click)

        # ====================== QSplitter (пункт 4) ======================
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.scroll)          # карточки сверху
        self.splitter.addWidget(self.summary_table)   # таблица снизу
        self.splitter.setSizes([int(self.height() * 0.75), int(self.height() * 0.25)])  # 75% / 25%

        layout.addWidget(self.splitter)

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

        data = self.registry.get_all_tokens()
        grouped = defaultdict(list)
        for entry in data:
            if entry.get("mode") in ("Spot", "Futures"):
                grouped[entry.get("token", "")].append(entry)

        sorted_tokens = sorted(grouped.keys())
        total = len(sorted_tokens)
        to_show = sorted_tokens                    # ← теперь грузим ВСЕ токены

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

        # === НОВОЕ: если настроек нет — создаём дефолтную запись (все галочки выключены) ===
        if not saved_config:
            default_config = {
                "Binance": {"enabled": False, "spot_pairs": [], "futures_pairs": []},
                "Bybit":   {"enabled": False, "spot_pairs": [], "futures_pairs": []},
                "OKX":     {"enabled": False, "spot_pairs": [], "futures_pairs": []}
            }
            self.registry.save_monitoring_config(token_name, default_config)
            saved_config = self.registry.get_monitoring_config(token_name)
        # =================================================================================

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

            spot_pairs = []
            for e in ex_entries:
                if e.get("mode") == "Spot":
                    spot_pairs.extend(e.get("spot_pairs", []))
            spot_pairs = list(dict.fromkeys(spot_pairs))  # убираем дубли
            # ================================================

            if spot_pairs:
                box_layout.addWidget(QLabel("<b>Spot:</b>"))
                h = QHBoxLayout()
                h.setSpacing(8)
                h.setAlignment(Qt.AlignLeft)
                saved_spot = saved_config.get(exchange, {}).get("spot_pairs", spot_pairs)
                for pair in spot_pairs:
                    cb = QCheckBox(pair)
                    cb.stateChanged.connect(lambda: save_btn.setEnabled(True))
                    cb.setChecked(pair in saved_spot)
                    cb.setProperty("pair", pair)
                    cb.setProperty("type", "spot")
                    cb.setProperty("token_name", token_name)
                    cb.setProperty("exchange", exchange)
                    h.addWidget(cb)
                box_layout.addLayout(h)

            futures_pairs = []
            for e in ex_entries:
                if e.get("mode") == "Futures":
                    symbol = e.get("futures_symbol")
                    if symbol:
                        futures_pairs.append(symbol)
            futures_pairs = list(dict.fromkeys(futures_pairs))
            # ===================================================

            if futures_pairs:
                box_layout.addWidget(QLabel("<b>Futures:</b>"))
                h = QHBoxLayout()
                h.setSpacing(8)
                h.setAlignment(Qt.AlignLeft)
                saved_fut = saved_config.get(exchange, {}).get("futures_pairs", futures_pairs)
                for pair in futures_pairs:
                    cb = QCheckBox(pair)
                    cb.stateChanged.connect(lambda: save_btn.setEnabled(True))
                    cb.setChecked(pair in saved_fut)
                    cb.setProperty("pair", pair)
                    cb.setProperty("type", "futures")
                    cb.setProperty("token_name", token_name)
                    cb.setProperty("exchange", exchange)
                    h.addWidget(cb)
                box_layout.addLayout(h)

            enable_cb = QCheckBox(f"Включить {exchange} в мониторинг")
            enable_cb.stateChanged.connect(lambda: save_btn.setEnabled(True))
            enable_cb.setChecked(saved_config.get(exchange, {}).get("enabled", False))  # False по умолчанию
            enable_cb.setProperty("token_name", token_name)
            enable_cb.setProperty("exchange", exchange)
            box_layout.addWidget(enable_cb)

            main_layout.addWidget(box)

        return card

    def _save_single_card(self, token_name: str):
        """Сохраняет настройки одной карточки"""
        if not token_name:
            return

        # Ищем карточку по имени токена
        card = None
        for c in self.cards:
            if c.property("token_name") == token_name:
                card = c
                break

        if not card:
            return

        # Собираем актуальные настройки из всех чекбоксов
        config = {}
        for cb in card.findChildren(QCheckBox):
            ex = cb.property("exchange")
            if not ex:
                continue

            if cb.property("type") == "enable":
                config.setdefault(ex, {})["enabled"] = cb.isChecked()
            elif cb.property("type") == "spot":
                config.setdefault(ex, {}).setdefault("spot_pairs", [])
                if cb.isChecked() and cb.property("pair"):
                    config[ex]["spot_pairs"].append(cb.property("pair"))
            elif cb.property("type") == "futures":
                config.setdefault(ex, {}).setdefault("futures_pairs", [])
                if cb.isChecked() and cb.property("pair"):
                    config[ex]["futures_pairs"].append(cb.property("pair"))

        # Сохраняем в реестр
        self.registry.save_monitoring_config(token_name, config)

        # Деактивируем кнопку "Сохранить"
        for btn in card.findChildren(QPushButton):
            if btn.text() == "Сохранить":
                btn.setEnabled(False)
                break

        # Обновляем таблицу
        self.update_summary_table()

        QMessageBox.information(self, "Сохранено", f"Настройки для {token_name} сохранены.")

    def update_summary_table(self):
        self.summary_table.setRowCount(0)

        for card in self.cards:
            token_name = card.property("token_name")
            if not token_name:
                continue

            spot_entries = [e for e in self.registry.get_all_tokens() 
                            if e.get("token", "").upper() == token_name and e.get("mode") == "Spot"]

            exchange_spots = defaultdict(list)
            for e in spot_entries:
                ex = e.get("exchange")
                if ex in ["Binance", "Bybit", "OKX"]:
                    exchange_spots[ex].append(e)

            y = len(exchange_spots)

            if y == 0:
                x = 0
            else:
                address_to_exchanges = defaultdict(set)
                for ex, entries in exchange_spots.items():
                    for entry in entries:
                        net = str(entry.get("network", "")).strip().lower()
                        addr = str(entry.get("contract_address", "")).strip().lower()
                        if net and addr:
                            key = (net, addr)
                            address_to_exchanges[key].add(ex)

                parent = {ex: ex for ex in exchange_spots.keys()}

                def find(z):
                    if parent[z] != z:
                        parent[z] = find(parent[z])
                    return parent[z]

                def union(a, b):
                    pa, pb = find(a), find(b)
                    if pa != pb:
                        parent[pa] = pb

                for exchanges_set in address_to_exchanges.values():
                    if len(exchanges_set) >= 2:
                        ex_list = list(exchanges_set)
                        for i in range(1, len(ex_list)):
                            union(ex_list[0], ex_list[i])

                from collections import Counter
                components = Counter(find(ex) for ex in exchange_spots.keys())
                x = max(components.values()) if components else 0

            # Подсчёт "Выбрано" — только галочки "Включить биржу"
            config = self.registry.get_monitoring_config(token_name)
            chosen = sum(1 for ex in ["Binance", "Bybit", "OKX"] if config.get(ex, {}).get("enabled", False))

            row = self.summary_table.rowCount()
            self.summary_table.insertRow(row)
            self.summary_table.setItem(row, 0, QTableWidgetItem(token_name))
            self.summary_table.setItem(row, 1, QTableWidgetItem("●" if exchange_spots.get("Binance") else "○"))
            self.summary_table.setItem(row, 2, QTableWidgetItem("●" if exchange_spots.get("Bybit") else "○"))
            self.summary_table.setItem(row, 3, QTableWidgetItem("●" if exchange_spots.get("OKX") else "○"))
            self.summary_table.setItem(row, 4, QTableWidgetItem(f"{x}/{y}"))
            self.summary_table.setItem(row, 5, QTableWidgetItem(str(chosen)))   # ← исправлено
            self.summary_table.setItem(row, 6, QTableWidgetItem("Перейти"))

        self.summary_table.sortItems(4, Qt.DescendingOrder)

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
    
    def _sort_table(self, column: int):
        """Сортировка по клику на заголовок колонки"""
        if not hasattr(self, '_sort_order'):
            self._sort_order = Qt.DescendingOrder

        self.summary_table.sortItems(column, self._sort_order)
        # Переключаем порядок при повторном клике
        self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder

    def filter_cards(self):
        text = self.search_edit.text().strip().lower()
        for card in self.cards:
            token = card.property("token_name") or ""
            card.setVisible(text in token.lower())
        self.update_summary_table()