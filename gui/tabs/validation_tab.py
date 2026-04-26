from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QCheckBox, QGridLayout
)
from PySide6.QtCore import Qt, Signal

from core.token_registry import token_registry


class ValidationTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.registry = token_registry
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
        self.search_edit.setPlaceholderText("Поиск по токену или сети...")
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

        self.load_cards()

    def load_cards(self):
        """Загрузка всех карточек"""
        # Очистка предыдущих карточек
        for i in reversed(range(self.cards_layout.count())):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        data = self.registry.get_all_tokens()

        for token in data:
            if token.get("mode") != "Spot":
                continue  # пока показываем только Spot как основу

            card = self.create_card(token)
            self.cards_layout.addWidget(card)

    def create_card(self, token: dict):
        """Создаёт одну подробную карточку"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 8px; padding: 10px;")

        layout = QVBoxLayout(frame)
        layout.setSpacing(8)

        # Заголовок карточки
        header = QHBoxLayout()
        title = QLabel(f"{token.get('token')} ({token.get('network', '')})")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        status = QLabel("Статус: Частичное совпадение")
        status.setStyleSheet("color: orange; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(status)
        layout.addLayout(header)

        # Здесь будут блоки бирж (Binance, Bybit, OKX) — пока заглушка
        # Полную реализацию блоков бирж сделаем в следующем шаге

        return frame

    def filter_cards(self):
        """Фильтрация карточек по поиску"""
        text = self.search_edit.text().strip().lower()
        for i in range(self.cards_layout.count()):
            widget = self.cards_layout.itemAt(i).widget()
            if widget:
                # Простая фильтрация по заголовку (расширим позже)
                visible = not text or text in widget.findChild(QLabel).text().lower()
                widget.setVisible(visible)