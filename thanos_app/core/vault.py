# thanos_app/core/vault.py
import os
from typing import List, Dict, Any
from . import crypto
from . import device_binding
from .database import DatabaseManager

class Vault:
    def __init__(self, db_manager: DatabaseManager, final_key: bytes):
        self.db = db_manager
        self.key = final_key

    def add_account(self, name: str, password: str, username: str = "", url: str = "", notes: str = "", category: str = "Autre", importance: int = 1, tags: str = "") -> int:
        if not name or not password:
            raise ValueError("Le nom du compte et le mot de passe ne peuvent pas être vides.")
        
        encrypted_password = crypto.encrypt_data(self.key, password)
        account_id = self.db.add_account(name, username, encrypted_password, url, notes, category, importance, tags)
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

    def update_account(self, account_id: int, name: str, password: str, username: str, url: str, notes: str, category: str, importance: int, tags: str):
        encrypted_password = crypto.encrypt_data(self.key, password)
        self.db.update_account(account_id, name, username, encrypted_password, url, notes, category, importance, tags)

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
            kdf_salt = os.urandom(crypto.ARGON2_SALT_BYTES)
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
            # Exécute la migration pour s'assurer que le schéma est à jour
            db.migrate_database()

            cursor = db.conn.cursor()
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("master_password_hash",))
            hashed_mp_row = cursor.fetchone()
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("kdf_salt",))
            kdf_salt_row = cursor.fetchone()

            if not hashed_mp_row or not kdf_salt_row:
                raise FileNotFoundError("Configuration du coffre-fort invalide.")

            if not crypto.verify_password(master_password, hashed_mp_row[0]):
                raise ValueError("Mot de passe principal incorrect.")

            print("✅ Vérification OK. Dérivation de la clé avec Argon2id...")
            derived_key = crypto.derive_key(master_password, kdf_salt_row[0])
            device_id = device_binding.get_device_id()
            final_key = device_binding.combine_key_with_device_id(derived_key, device_id)
            return Vault(db, final_key)
        except Exception as e:
            db.close()
            raise e
