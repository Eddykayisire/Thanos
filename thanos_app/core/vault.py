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
    def create_vault(db_path: str, master_password: str) -> str:
        with DatabaseManager(db_path) as db:
            db.create_tables()
            hashed_mp = crypto.hash_password(master_password)
            kdf_salt = os.urandom(crypto.ARGON2_SALT_BYTES)
            
            # --- DEVICE BINDING ---
            # Génération de l'empreinte unique de l'appareil
            device_fp = device_binding.get_device_fingerprint()
            
            # --- RECOVERY KEY ---
            recovery_key = crypto.generate_recovery_key()
            recovery_key_hash = crypto.hash_password(recovery_key)
            
            cursor = db.conn.cursor()
            cursor.execute("INSERT INTO vault_config (key, value) VALUES (?, ?)", ("master_password_hash", hashed_mp))
            cursor.execute("INSERT INTO vault_config (key, value) VALUES (?, ?)", ("kdf_salt", kdf_salt))
            # Stockage de l'empreinte pour vérification à l'ouverture
            cursor.execute("INSERT INTO vault_config (key, value) VALUES (?, ?)", ("device_fingerprint", device_fp))
            cursor.execute("INSERT INTO vault_config (key, value) VALUES (?, ?)", ("recovery_key_hash", recovery_key_hash))
            db.conn.commit()
        print(f"Coffre-fort créé : {db_path}")
        return recovery_key

    @staticmethod
    def open_vault(db_path: str, master_password: str, recovery_key: str = None) -> Vault:
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
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("device_fingerprint",))
            device_fp_row = cursor.fetchone()
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("recovery_key_hash",))
            rk_hash_row = cursor.fetchone()

            if not hashed_mp_row or not kdf_salt_row:
                raise FileNotFoundError("Configuration du coffre-fort invalide.")

            if not crypto.verify_password(master_password, hashed_mp_row[0]):
                raise ValueError("Mot de passe principal incorrect.")

            # --- DEVICE BINDING CHECK ---
            if device_fp_row:
                # Nouveau système : Vérification stricte de l'empreinte
                stored_fp = device_fp_row[0]
                current_fp = device_binding.get_device_fingerprint()
                
                if stored_fp != current_fp:
                    # MIGRATION REQUISE
                    if not recovery_key:
                        raise ValueError("DEVICE_MISMATCH")
                    
                    # Vérification de la clé de récupération
                    if not rk_hash_row or not crypto.verify_password(recovery_key, rk_hash_row[0]):
                        raise ValueError("Clé de récupération invalide. Accès refusé.")
                    
                    print("🔄 Migration du coffre vers le nouvel appareil en cours...")
                    
                    # 1. Dériver l'ancienne clé (pour déchiffrer)
                    old_combined = master_password + stored_fp
                    old_key = crypto.derive_key(old_combined, kdf_salt_row[0])
                    
                    # 2. Dériver la nouvelle clé (pour chiffrer)
                    new_combined = master_password + current_fp
                    new_key = crypto.derive_key(new_combined, kdf_salt_row[0])
                    
                    # 3. Re-chiffrer tous les comptes
                    cursor.execute("SELECT id, encrypted_password FROM accounts")
                    accounts = cursor.fetchall()
                    for acc in accounts:
                        plain = crypto.decrypt_data(old_key, acc['encrypted_password'])
                        new_enc = crypto.encrypt_data(new_key, plain)
                        cursor.execute("UPDATE accounts SET encrypted_password = ? WHERE id = ?", (new_enc, acc['id']))
                    
                    # 4. Mettre à jour l'empreinte
                    cursor.execute("UPDATE vault_config SET value = ? WHERE key = 'device_fingerprint'", (current_fp,))
                    db.conn.commit()
                    final_key = new_key
                else:
                    print("✅ Vérification Appareil OK. Dérivation de la clé avec Argon2id...")
                    combined_password = master_password + current_fp
                    final_key = crypto.derive_key(combined_password, kdf_salt_row[0])
            else:
                # Système Legacy (pour compatibilité avec anciens coffres)
                print("⚠️ Mode Legacy (Pas d'empreinte stockée).")
                derived_key = crypto.derive_key(master_password, kdf_salt_row[0])
                device_id = device_binding.get_device_id()
                final_key = device_binding.combine_key_with_device_id(derived_key, device_id)

            return Vault(db, final_key)
        except Exception as e:
            db.close()
            raise e

    @staticmethod
    def backup_vault(db_path: str, backup_path: str, master_password: str, recovery_key: str):
        """Crée une sauvegarde chiffrée (AES-256) du fichier DB complet."""
        # 1. Dérivation de la clé de sauvegarde (MP + RK + Sel aléatoire)
        backup_salt = os.urandom(crypto.ARGON2_SALT_BYTES)
        combined_secret = master_password + recovery_key
        key = crypto.derive_key(combined_secret, backup_salt)
        
        # 2. Lecture du fichier DB
        with open(db_path, 'rb') as f:
            db_bytes = f.read()
            
        # 3. Chiffrement (Salt + Nonce + Ciphertext)
        encrypted_data = crypto.encrypt_binary(key, db_bytes)
        
        # 4. Écriture
        with open(backup_path, 'wb') as f:
            f.write(backup_salt + encrypted_data)

    @staticmethod
    def restore_vault(backup_path: str, db_path: str, master_password: str, recovery_key: str):
        """Restaure une sauvegarde, déchiffre la DB et effectue la migration d'appareil."""
        # 1. Lecture et Déchiffrement
        with open(backup_path, 'rb') as f:
            data = f.read()
            
        salt = data[:crypto.ARGON2_SALT_BYTES]
        encrypted_content = data[crypto.ARGON2_SALT_BYTES:]
        
        combined_secret = master_password + recovery_key
        key = crypto.derive_key(combined_secret, salt)
        
        try:
            db_bytes = crypto.decrypt_binary(key, encrypted_content)
        except Exception:
            raise ValueError("Déchiffrement impossible. Mot de passe ou clé de récupération incorrect.")
            
        # 2. Écriture temporaire pour migration
        with open(db_path, 'wb') as f:
            f.write(db_bytes)
            
        # 3. Migration immédiate (Re-keying pour le nouvel appareil)
        # On utilise open_vault qui contient déjà la logique de migration si on lui fournit la recovery_key
        # Cela va détecter le DEVICE_MISMATCH et migrer automatiquement.
        try:
            # On ouvre juste pour déclencher la migration, puis on ferme
            vault = VaultManager.open_vault(db_path, master_password, recovery_key)
            vault.close()
        except Exception as e:
            # Si open_vault échoue, la restauration est compromise
            if os.path.exists(db_path): os.remove(db_path)
            raise e
