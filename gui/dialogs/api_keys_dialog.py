from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal   # ← Signal добавлен

import os
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class MasterPasswordDialog(QDialog):
    """Кастомное окно ввода мастер-пароля"""
    forgot_clicked = Signal()   # теперь работает

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Мастер-пароль")
        self.resize(420, 190)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 15)

        info = QLabel("Вы направляетесь в зону защищённой информации.")
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 13px; color: #444;")
        layout.addWidget(info)

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText("Введите мастер-пароль")
        layout.addWidget(self.edit)

        forgot = QLabel('<a href="#">Забыли пароль?</a>')
        forgot.setAlignment(Qt.AlignCenter)
        forgot.setOpenExternalLinks(False)
        forgot.linkActivated.connect(self.forgot_password)
        layout.addWidget(forgot)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Отмена")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def forgot_password(self):
        self.forgot_clicked.emit()
        self.reject()

    def get_password(self):
        if self.exec() == QDialog.Accepted:
            return self.edit.text().strip()
        return None


class ApiKeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка API Keys")
        self.resize(830, 210)
        self.master_key = None
        self.encrypted_file = "config/api_keys.enc"

        self.init_ui()

        if not os.path.exists(self.encrypted_file):
            self.show_first_time_welcome()
        else:
            self.load_keys()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 8, 12, 12)

        top = QHBoxLayout()
        title = QLabel("Управление API-ключами")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()

        self.btn_change_master = QPushButton("Изменить мастер-пароль")
        self.btn_change_master.clicked.connect(self.change_master_password)
        top.addWidget(self.btn_change_master)

        self.btn_reset = QPushButton("Сбросить все ключи")
        self.btn_reset.clicked.connect(self.reset_all_keys)
        top.addWidget(self.btn_reset)

        layout.addLayout(top)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        grid.addWidget(QLabel("<b>Биржа</b>"), 0, 0)
        grid.addWidget(QLabel("<b>API Key</b>"), 0, 1)
        grid.addWidget(QLabel("<b>API Secret</b>"), 0, 2)
        grid.addWidget(QLabel("<b>Действия</b>"), 0, 3)

        self.rows = {}
        exchanges = ["Binance", "Bybit", "OKX"]

        for i, ex in enumerate(exchanges, start=1):
            lbl = QLabel(ex)
            lbl.setStyleSheet("font-weight: bold;")

            key_edit = QLineEdit()
            key_edit.setEchoMode(QLineEdit.Password)
            secret_edit = QLineEdit()
            secret_edit.setEchoMode(QLineEdit.Password)

            btn_save = QPushButton("Сохранить")
            btn_test = QPushButton("Проверить")
            status = QLabel("Не настроено")
            status.setStyleSheet("color: gray;")

            btn_save.clicked.connect(lambda _, e=ex, k=key_edit, s=secret_edit: self.save_key(e, k, s))
            btn_test.clicked.connect(lambda _, e=ex: self.test_connection(e))

            grid.addWidget(lbl, i, 0)
            grid.addWidget(key_edit, i, 1)
            grid.addWidget(secret_edit, i, 2)
            grid.addWidget(btn_save, i, 3)
            grid.addWidget(btn_test, i, 4)
            grid.addWidget(status, i, 5)

            self.rows[ex] = {"key_edit": key_edit, "secret_edit": secret_edit, "status": status}

        layout.addLayout(grid)

    def show_first_time_welcome(self):
        QMessageBox.information(
            self,
            "Добро пожаловать!",
            "Вы направляетесь в зону защищённой информации.\n\n"
            "Для безопасного хранения API-ключей создайте мастер-пароль."
        )

        while True:
            password, ok = QInputDialog.getText(self, "Создание мастер-пароля", "Введите мастер-пароль:", QLineEdit.Password)
            if not ok or not password:
                self.reject()
                return

            confirm, ok2 = QInputDialog.getText(self, "Подтверждение пароля", "Повторите мастер-пароль:", QLineEdit.Password)
            if not ok2 or password != confirm:
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают.")
                continue

            self.master_key = password
            self.save_empty_keys()
            break

        self.load_keys()

    def save_empty_keys(self):
        data = {}
        fernet = self.get_fernet(self.master_key)
        encrypted = fernet.encrypt(json.dumps(data).encode())
        os.makedirs("config", exist_ok=True)
        with open(self.encrypted_file, "wb") as f:
            f.write(encrypted)

    def load_keys(self):
        dlg = MasterPasswordDialog(self)
        dlg.forgot_clicked.connect(self.reset_all_keys)
        password = dlg.get_password()

        if not password:
            self.reject()
            return

        self.master_key = password

        if not os.path.exists(self.encrypted_file):
            return

        try:
            with open(self.encrypted_file, "rb") as f:
                encrypted_data = f.read()
            fernet = self.get_fernet(self.master_key)
            data = json.loads(fernet.decrypt(encrypted_data).decode())

            for ex, creds in data.items():
                if ex in self.rows:
                    self.rows[ex]["key_edit"].setText(creds.get("api_key", ""))
                    self.rows[ex]["secret_edit"].setText(creds.get("api_secret", ""))
                    self.update_status(ex, bool(creds.get("api_key")))
        except Exception:
            QMessageBox.critical(self, "Ошибка", "Неверный мастер-пароль или файл повреждён.")
            self.reject()

    def get_fernet(self, master_password: str):
        salt = b'ArbitraSalt2026'
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return Fernet(key)

    def save_key(self, exchange: str, key_edit: QLineEdit, secret_edit: QLineEdit):
        if not self.master_key:
            return
        api_key = key_edit.text().strip()
        api_secret = secret_edit.text().strip()

        if not api_key or not api_secret:
            QMessageBox.warning(self, "Ошибка", "Оба поля (API Key и API Secret) должны быть заполнены.")
            return

        data = {}
        if os.path.exists(self.encrypted_file):
            try:
                with open(self.encrypted_file, "rb") as f:
                    enc = f.read()
                fernet = self.get_fernet(self.master_key)
                data = json.loads(fernet.decrypt(enc).decode())
            except:
                data = {}

        data[exchange] = {"api_key": api_key, "api_secret": api_secret}

        fernet = self.get_fernet(self.master_key)
        encrypted = fernet.encrypt(json.dumps(data).encode())

        os.makedirs("config", exist_ok=True)
        with open(self.encrypted_file, "wb") as f:
            f.write(encrypted)

        self.update_status(exchange, True)
        QMessageBox.information(self, "Успех", f"Ключи для {exchange} сохранены.")

    def update_status(self, exchange: str, connected: bool):
        if exchange in self.rows:
            status = self.rows[exchange]["status"]
            status.setText("✓ Подключено" if connected else "Не настроено")
            status.setStyleSheet("color: #4caf50; font-weight: bold;" if connected else "color: gray;")

    def test_connection(self, exchange: str):
        QMessageBox.information(self, "Проверка", f"Проверка соединения {exchange} будет добавлена позже.")

    def reset_all_keys(self):
        reply = QMessageBox.question(self, "Сброс ключей", 
                                     "Удалить ВСЕ API-ключи и сбросить мастер-пароль?\n\n"
                                     "Это действие необратимо!", 
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if os.path.exists(self.encrypted_file):
                os.remove(self.encrypted_file)
            for ex in self.rows:
                self.rows[ex]["key_edit"].clear()
                self.rows[ex]["secret_edit"].clear()
                self.update_status(ex, False)
            QMessageBox.information(self, "Готово", "Все ключи сброшены.\nТеперь вы можете создать новый мастер-пароль.")
            self.close()

    def change_master_password(self):
        QMessageBox.information(self, "Смена мастер-пароля", 
                                "Функция смены мастер-пароля будет добавлена в следующем обновлении.")