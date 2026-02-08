from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox)
from PySide6.QtCore import Qt
from thanos_app.utils.password_validator import validate_master_password
from thanos_app.core import crypto
from thanos_app.core import device_binding
import os
import config

class ChangePasswordDialog(QDialog):
    def __init__(self, security_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setWindowTitle("Changer le mot de passe principal")
        self.setMinimumWidth(480)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.old_pw = QLineEdit()
        self.old_pw.setEchoMode(QLineEdit.Password)
        form.addRow("Mot de passe actuel:", self.old_pw)

        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.Password)
        form.addRow("Nouveau mot de passe:", self.new_pw)

        self.confirm_pw = QLineEdit()
        self.confirm_pw.setEchoMode(QLineEdit.Password)
        form.addRow("Confirmer le nouveau mot de passe:", self.confirm_pw)

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignLeft)
        layout.addLayout(form)
        layout.addWidget(self.status)

        btn = QPushButton("Changer le mot de passe")
        btn.clicked.connect(self.on_change)
        layout.addWidget(btn)

    def on_change(self):
        old = self.old_pw.text()
        new = self.new_pw.text()
        confirm = self.confirm_pw.text()

        if not old or not new or not confirm:
            QMessageBox.warning(self, "Erreur", "Tous les champs sont requis.")
            return
        if new != confirm:
            QMessageBox.warning(self, "Erreur", "La confirmation ne correspond pas.")
            return

        val = validate_master_password(new)
        if not val.get('valid'):
            QMessageBox.warning(self, "Mot de passe invalide", f"{val.get('label')}: {val.get('feedback')}")
            return

        # Verify old password against stored hash
        try:
            cursor = self.security_manager.db.conn.cursor()
            cursor.execute("SELECT value FROM vault_config WHERE key = ?", ("master_password_hash",))
            row = cursor.fetchone()
            if not row:
                QMessageBox.critical(self, "Erreur", "Configuration du coffre introuvable.")
                return
            stored_hash = row[0]
            if not crypto.verify_password(old, stored_hash):
                QMessageBox.critical(self, "Erreur", "Mot de passe actuel incorrect.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur de vérification: {e}")
            return

        # Proceed with re-encryption
        try:
            # Create DB backup
            db_path = config.VAULT_DB_FILE
            backup_path = f"{db_path}.bak"
            import shutil
            shutil.copyfile(db_path, backup_path)

            # Generate new salt and hashed password
            new_salt = os.urandom(crypto.ARGON2_SALT_BYTES)
            new_hashed = crypto.hash_password(new)

            # Derive new key
            derived_key = crypto.derive_key(new, new_salt)
            device_id = device_binding.get_device_id()
            new_final_key = device_binding.combine_key_with_device_id(derived_key, device_id)

            # Re-encrypt all accounts
            accounts = self.security_manager.db.get_all_accounts()
            for acc in accounts:
                # decrypt with old key
                try:
                    old_plain = crypto.decrypt_data(self.security_manager.vault_key, acc['encrypted_password'])
                except Exception as e:
                    raise Exception(f"Impossible de déchiffrer le compte ID {acc['id']}: {e}")
                new_encrypted = crypto.encrypt_data(new_final_key, old_plain)
                # update
                self.security_manager.db.update_account(acc['id'], acc['name'], acc['username'], new_encrypted, acc.get('url',''), acc.get('notes',''), acc.get('category','Autre'), acc.get('importance',1), acc.get('tags',''))

            # Update vault_config entries
            cur = self.security_manager.db.conn.cursor()
            cur.execute("INSERT OR REPLACE INTO vault_config (key, value) VALUES (?, ?)", ("master_password_hash", new_hashed))
            cur.execute("INSERT OR REPLACE INTO vault_config (key, value) VALUES (?, ?)", ("kdf_salt", new_salt))
            self.security_manager.db.conn.commit()

            QMessageBox.information(self, "Succès", "Mot de passe principal changé avec succès.")
            # Update runtime security_manager key
            self.security_manager.vault_key = new_final_key
            self.accept()
        except Exception as e:
            # In case of failure, restore backup
            try:
                shutil.copyfile(backup_path, db_path)
            except Exception:
                pass
            QMessageBox.critical(self, "Erreur", f"Échec de la mise à jour du mot de passe: {e}")
            return
