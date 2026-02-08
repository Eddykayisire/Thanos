import os

# Définition de la structure et du contenu des fichiers
files = {
    "requirements.txt": """PySide6>=6.8.0
cryptography
bcrypt""",

    "config.py": """# config.py
import os

# --- Paths ---
APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".thanos")
VAULT_DB_FILE = os.path.join(APP_DATA_DIR, "vault.db")
SECURITY_LOG_FILE = os.path.join(APP_DATA_DIR, "security.log")
DEVICE_ID_FILE = os.path.join(APP_DATA_DIR, "device.id")

# --- Crypto Settings ---
KDF_SALT_SIZE = 16
KDF_ITERATIONS = 480000
AES_NONCE_SIZE = 12
AES_TAG_SIZE = 16
""",

    "main.py": """# main.py
import sys
import os
from PySide6.QtWidgets import QApplication
from thanos_app.gui.login_window import LoginWindow
from thanos_app.gui.main_window import MainWindow
from config import APP_DATA_DIR

def main():
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    login_win = LoginWindow()

    if login_win.exec():
        main_win = MainWindow(login_win.vault)
        main_win.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
""",

    "thanos_app/__init__.py": "",
    "thanos_app/core/__init__.py": "",
    
    "thanos_app/core/crypto.py": """# thanos_app/core/crypto.py
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import bcrypt
from config import KDF_ITERATIONS

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
        backend=default_backend()
    )
    return kdf.derive(password.encode('utf-8'))

def encrypt_data(key: bytes, plaintext: str) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return nonce + ciphertext

def decrypt_data(key: bytes, encrypted_data: bytes) -> str:
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode('utf-8')
    except Exception as e:
        raise ValueError("Échec du déchiffrement.") from e

def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password: str, hashed_password: bytes) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)
""",

    "thanos_app/core/device_binding.py": """# thanos_app/core/device_binding.py
import uuid
import hashlib

def get_device_id() -> str:
    mac_address = uuid.getnode()
    return hashlib.sha256(str(mac_address).encode()).hexdigest()

def combine_key_with_device_id(derived_key: bytes, device_id: str) -> bytes:
    combined = derived_key + device_id.encode('utf-8')
    final_key = hashlib.sha256(combined).digest()
    return final_key
""",

    "thanos_app/core/database.py": """# thanos_app/core/database.py
import sqlite3
from typing import List, Dict, Any, Optional
from config import VAULT_DB_FILE

class DatabaseManager:
    def __init__(self, db_file=VAULT_DB_FILE):
        self.db_file = db_file
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def create_tables(self):
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS vault_config (
            key TEXT PRIMARY KEY,
            value BLOB NOT NULL
        )
        \"\"\")

        cursor.execute(\"\"\"
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT,
            encrypted_password BLOB NOT NULL,
            url TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        \"\"\")
        self.conn.commit()

    def add_account(self, name: str, username: str, encrypted_password: bytes, url: str, notes: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (name, username, encrypted_password, url, notes) VALUES (?, ?, ?, ?, ?)",
            (name, username, encrypted_password, url, notes)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, username, url, notes, created_at FROM accounts ORDER BY name ASC")
        accounts = [dict(row) for row in cursor.fetchall()]
        return accounts

    def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_account(self, account_id: int, name: str, username: str, encrypted_password: bytes, url: str, notes: str):
        cursor = self.conn.cursor()
        cursor.execute(
            \"\"\"UPDATE accounts 
               SET name = ?, username = ?, encrypted_password = ?, url = ?, notes = ?
               WHERE id = ?\"\"\",
            (name, username, encrypted_password, url, notes, account_id)
        )
        self.conn.commit()

    def delete_account(self, account_id: int):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()
""",

    "thanos_app/core/vault.py": """# thanos_app/core/vault.py
import os
from typing import List, Dict, Any
from . import crypto
from . import device_binding
from .database import DatabaseManager
from config import KDF_SALT_SIZE

class Vault:
    def __init__(self, db_manager: DatabaseManager, final_key: bytes):
        self.db = db_manager
        self.key = final_key

    def add_account(self, name: str, password: str, username: str = "", url: str = "", notes: str = "") -> int:
        if not name or not password:
            raise ValueError("Le nom du compte et le mot de passe ne peuvent pas être vides.")
        
        encrypted_password = crypto.encrypt_data(self.key, password)
        account_id = self.db.add_account(name, username, encrypted_password, url, notes)
        print(f"Compte '{name}' ajouté avec l'ID {account_id}.")
        return account_id

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        return self.db.get_all_accounts()

    def get_decrypted_password(self, account_id: int) -> str:
        account = self.db.get_account(account_id)
        if not account:
            raise ValueError("Aucun compte trouvé avec cet ID.")
        
        encrypted_password = account['encrypted_password']
        return crypto.decrypt_data(self.key, encrypted_password)

    def update_account(self, account_id: int, name: str, password: str, username: str, url: str, notes: str):
        encrypted_password = crypto.encrypt_data(self.key, password)
        self.db.update_account(account_id, name, username, encrypted_password, url, notes)

    def delete_account(self, account_id: int):
        self.db.delete_account(account_id)

    def close(self):
        self.db.close()

class VaultManager:
    @staticmethod
    def create_vault(db_path: str, master_password: str):
        with DatabaseManager(db_path) as db:
            db.create_tables()
            hashed_mp = crypto.hash_password(master_password)
            kdf_salt = os.urandom(KDF_SALT_SIZE)
            cursor = db.conn.cursor()
            cursor.execute("INSERT INTO vault_config (key, value) VALUES (?, ?)", ("master_password_hash", hashed_mp))
            cursor.execute("INSERT INTO vault_config (key, value) VALUES (?, ?)", ("kdf_salt", kdf_salt))
            db.conn.commit()
        print(f"Coffre-fort créé : {db_path}")

    @staticmethod
    def open_vault(db_path: str, master_password: str) -> Vault:
        db = DatabaseManager(db_path)
        db.connect()
        try:
            cursor = db.conn.cursor()
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("master_password_hash",))
            hashed_mp_row = cursor.fetchone()
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("kdf_salt",))
            kdf_salt_row = cursor.fetchone()

            if not hashed_mp_row or not kdf_salt_row:
                raise FileNotFoundError("Configuration du coffre-fort invalide.")

            if not crypto.verify_password(master_password, hashed_mp_row[0]):
                raise ValueError("Mot de passe principal incorrect.")

            derived_key = crypto.derive_key(master_password, kdf_salt_row[0])
            device_id = device_binding.get_device_id()
            final_key = device_binding.combine_key_with_device_id(derived_key, device_id)
            return Vault(db, final_key)
        except Exception as e:
            db.close()
            raise e
""",

    "thanos_app/core/security_log.py": """# thanos_app/core/security_log.py
import logging
from config import SECURITY_LOG_FILE

logger = logging.getLogger('ThanosSecurityLogger')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(SECURITY_LOG_FILE)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(file_handler)

def log_event(message: str): logger.info(message)
def log_warning(message: str): logger.warning(message)
def log_error(message: str): logger.error(message)
""",

    "thanos_app/gui/__init__.py": "",
    
    "thanos_app/gui/account_table_model.py": """# thanos_app/gui/account_table_model.py
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from typing import List, Dict, Any

class AccountTableModel(QAbstractTableModel):
    def __init__(self, data: List[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = ["Nom", "Nom d'utilisateur", "URL", "Date d'ajout"]
        self._column_keys = ["name", "username", "url", "created_at"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid(): return None
        row, col = index.row(), index.column()
        if role == Qt.DisplayRole:
            return self._data[row].get(self._column_keys[col], "")
        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int: return len(self._data)
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int: return len(self._headers)
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal: return self._headers[section]
        return None
    def refresh_data(self, new_data: List[Dict[str, Any]]):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
    def get_account_id_for_row(self, row: int) -> int | None:
        if 0 <= row < self.rowCount(): return self._data[row].get('id')
        return None
""",

    "thanos_app/gui/login_window.py": """# thanos_app/gui/login_window.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from .styles.dark_theme import apply_dark_theme
from thanos_app.core.vault import VaultManager
from thanos_app.core.security_log import log_event, log_warning, log_error
from config import VAULT_DB_FILE
import os

class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thanos - Déverrouiller")
        self.setMinimumWidth(350)
        self.vault = None
        apply_dark_theme(self)
        layout = QVBoxLayout(self)
        if not os.path.exists(VAULT_DB_FILE): self.setup_create_ui(layout)
        else: self.setup_login_ui(layout)

    def setup_login_ui(self, layout):
        self.label = QLabel("Entrez votre mot de passe principal :")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.login_button = QPushButton("Déverrouiller")
        self.login_button.clicked.connect(self.try_login)
        layout.addWidget(self.label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

    def setup_create_ui(self, layout):
        self.label = QLabel("Créez votre mot de passe principal :")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_label = QLabel("Confirmez le mot de passe :")
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.create_button = QPushButton("Créer le coffre-fort")
        self.create_button.clicked.connect(self.try_create)
        layout.addWidget(self.label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.confirm_label)
        layout.addWidget(self.confirm_input)
        layout.addWidget(self.create_button)

    def try_login(self):
        password = self.password_input.text()
        if not password: return
        try:
            self.vault = VaultManager.open_vault(VAULT_DB_FILE, password)
            log_event("Accès au coffre-fort réussi.")
            self.accept()
        except ValueError as e:
            log_warning("Tentative de connexion échouée.")
            QMessageBox.critical(self, "Échec", str(e))
        except Exception as e:
            log_error(f"Erreur: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur: {e}")

    def try_create(self):
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        if password != confirm:
            QMessageBox.warning(self, "Erreur", "Les mots de passe ne correspondent pas.")
            return
        if len(password) < 12:
            QMessageBox.warning(self, "Sécurité", "Le mot de passe doit contenir au moins 12 caractères.")
            return
        try:
            VaultManager.create_vault(VAULT_DB_FILE, password)
            log_event("Nouveau coffre-fort créé.")
            QMessageBox.information(self, "Succès", "Coffre créé. Redémarrez pour vous connecter.")
            self.reject()
        except Exception as e:
            log_error(f"Erreur création: {e}")
            QMessageBox.critical(self, "Erreur", f"Impossible de créer le coffre: {e}")
""",

    "thanos_app/gui/main_window.py": """# thanos_app/gui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTableView,
    QPushButton, QAbstractItemView, QHeaderView
)
from .styles.dark_theme import apply_dark_theme
from thanos_app.core.vault import Vault
from .account_table_model import AccountTableModel

class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle("Thanos - Votre Coffre-fort")
        self.setMinimumSize(800, 600)
        apply_dark_theme(self)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        toolbar_layout = QHBoxLayout()
        self.add_button = QPushButton("➕ Ajouter")
        self.edit_button = QPushButton("✏️ Modifier")
        self.delete_button = QPushButton("🗑️ Supprimer")
        toolbar_layout.addWidget(self.add_button)
        toolbar_layout.addWidget(self.edit_button)
        toolbar_layout.addWidget(self.delete_button)
        toolbar_layout.addStretch()

        self.table_view = QTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)

        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.table_view)

        self.setup_model()
        self.add_test_data_if_empty()
        self.load_accounts()

    def setup_model(self):
        self.model = AccountTableModel()
        self.table_view.setModel(self.model)

    def load_accounts(self):
        all_accounts = self.vault.get_all_accounts()
        self.model.refresh_data(all_accounts)

    def add_test_data_if_empty(self):
        if not self.vault.get_all_accounts():
            try:
                self.vault.add_account("Google", "very-strong-password-123", "test@gmail.com", "https://google.com")
                self.vault.add_account("GitHub", "another-secure-password", "dev", "https://github.com")
            except Exception as e:
                print(f"Erreur test data: {e}")

    def closeEvent(self, event):
        self.vault.close()
        super().closeEvent(event)
""",

    "thanos_app/gui/styles/__init__.py": "",
    "thanos_app/gui/styles/dark_theme.py": """# thanos_app/gui/styles/dark_theme.py
import os
from PySide6.QtWidgets import QApplication

def apply_dark_theme(app_or_widget):
    style_path = os.path.join(os.path.dirname(__file__), "dark_theme.qss")
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            style = f.read()
        app_or_widget.setStyleSheet(style)
""",

    "thanos_app/gui/styles/dark_theme.qss": """/* Dark Theme */
QWidget { background-color: #2b2b2b; color: #f0f0f0; font-family: "Segoe UI", sans-serif; font-size: 10pt; }
QMainWindow, QDialog { background-color: #2b2b2b; }
QLineEdit { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 5px; }
QPushButton { background-color: #7B1FA2; color: white; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }
QPushButton:hover { background-color: #9C27B0; }
QPushButton:pressed { background-color: #6A1B9A; }
QTableView { background-color: #3c3f41; border: 1px solid #555; gridline-color: #555; }
QHeaderView::section { background-color: #45494a; padding: 4px; border: 1px solid #555; font-weight: bold; }
""",

    "thanos_app/utils/__init__.py": "",
    "thanos_app/utils/password_generator.py": """# thanos_app/utils/password_generator.py
import secrets
import string
def generate_password(length: int = 16, use_uppercase: bool = True, use_digits: bool = True, use_symbols: bool = True) -> str:
    alphabet = string.ascii_lowercase
    if use_uppercase: alphabet += string.ascii_uppercase
    if use_digits: alphabet += string.digits
    if use_symbols: alphabet += string.punctuation
    if length < 8: raise ValueError("Min length 8")
    return ''.join(secrets.choice(alphabet) for _ in range(length))
""",
    "thanos_app/utils/security_alerts.py": """# thanos_app/utils/security_alerts.py
def capture_photo_on_failure(): pass
def send_alert_email(recipient_email: str): pass
"""
}

def create_project():
    print("Création des fichiers du projet Thanos...")
    for path, content in files.items():
        # Créer les dossiers nécessaires
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
        
        # Écrire le fichier
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✓ {path}")
    print("\nProjet généré avec succès ! Lancez 'python3 main.py'")

if __name__ == "__main__":
    create_project()
