import json
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QMessageBox, QSpinBox, QLabel, QComboBox, QCheckBox, QWidget, QScrollArea, QFileDialog
)

import config
from .styles.dark_theme import apply_dark_theme
from .styles import theme_manager
from .change_password_dialog import ChangePasswordDialog
from thanos_app.core.vault import VaultManager

class EmailTestWorker(QThread):
    """
    Thread dédié à l'envoi d'email de test pour ne pas bloquer l'interface.
    """
    result = Signal(bool, str)

    def __init__(self, security_manager, email_config):
        super().__init__()
        self.security_manager = security_manager
        self.email_config = email_config

    def run(self):
        try:
            self.security_manager.send_test_email(self.email_config)
            self.result.emit(True, "Email de test envoyé avec succès !")
        except Exception as e:
            self.result.emit(False, f"Échec de l'envoi de l'email :\n\n{e}")

class SettingsDialog(QDialog):
    def __init__(self, security_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setWindowTitle("Paramètres Thanos")
        
        # Configuration de la fenêtre
        self.resize(900, 600)
        self.setMinimumSize(700, 450)
        apply_dark_theme(self)
        
        self.worker = None
        self.setup_ui()
        self.theme = getattr(config, 'THEME', 'dark')
        self.change_theme(self.theme)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create scrollable area for long forms
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        form = QFormLayout(scroll_widget)
        scroll.setWidget(scroll_widget)

        # ===== SECTION: Email Alerts Configuration =====
        alerts_title = QLabel("📧 Configuration des Alertes Email")
        alerts_title.setStyleSheet("font-weight: bold; font-size: 11pt; margin-top: 10px;")
        form.addRow(alerts_title)

        self.email_alerts_cb = QCheckBox("Activer alertes email")
        self.email_alerts_cb.setChecked(getattr(config, 'EMAIL_ALERTS_ENABLED', True))
        form.addRow(self.email_alerts_cb)

        recipient_help = QLabel("Adresse email qui recevra les alertes de sécurité :")
        recipient_help.setStyleSheet("color: #aaa; font-size: 9pt;")
        self.email_recipient = QLineEdit(config.EMAIL_RECIPIENT)
        self.email_recipient.setPlaceholderText("ex: vous@domaine.com")
        form.addRow("Email Destinataire (vos alertes) :", self.email_recipient)
        form.addRow("", recipient_help)

        # ===== SECTION: Theme & Security =====
        theme_title = QLabel("🎨 Apparence et Sécurité")
        theme_title.setStyleSheet("font-weight: bold; font-size: 11pt; margin-top: 15px;")
        form.addRow(theme_title)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        current_theme = getattr(config, 'THEME', 'dark')
        try:
            self.theme_combo.setCurrentText(current_theme)
        except Exception:
            pass
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        form.addRow("Thème :", self.theme_combo)

        self.security_photo_cb = QCheckBox("Activer capture photo de sécurité")
        self.security_photo_cb.setChecked(getattr(config, 'SECURITY_PHOTO_ENABLED', True))
        form.addRow(self.security_photo_cb)

        self.max_attempts = QSpinBox()
        self.max_attempts.setRange(1, 20)
        self.max_attempts.setValue(config.MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS)
        form.addRow("Seuil tentatives avant alerte :", self.max_attempts)

        # Change password button
        self.change_master_btn = QPushButton("Changer le mot de passe principal")
        self.change_master_btn.clicked.connect(self.open_change_password_dialog)
        form.addRow(self.change_master_btn)

        # ===== SECTION: Sauvegarde =====
        backup_title = QLabel("💾 Sauvegarde et Restauration")
        backup_title.setStyleSheet("font-weight: bold; font-size: 11pt; margin-top: 15px;")
        form.addRow(backup_title)
        
        self.backup_btn = QPushButton("Créer une sauvegarde chiffrée")
        self.backup_btn.clicked.connect(self.create_backup)
        self.backup_btn.setStyleSheet("background-color: #1f6feb; color: white;")
        form.addRow(self.backup_btn)

        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        self.test_email_btn = QPushButton("Tester la configuration email")
        self.test_email_btn.clicked.connect(self.test_email_settings)

        self.save_btn = QPushButton("Enregistrer")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.test_email_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # Styles modernes
        self.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; /* Couleur de fond */
                color: white; /* Couleur du texte */
                border-radius: 10px; /* Coins arrondis */
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049; /* Couleur au survol */
            }
            QPushButton:pressed {
                background-color: #3e8e41; /* Couleur lors de l'appui */
            }
            QLineEdit {
                border: 2px solid #ccc;
                border-radius: 5px;
                padding: 10px;
            }
        """)

    def test_email_settings(self):
        current_config = {
            "sender": config.EMAIL_SENDER,
            "recipient": self.email_recipient.text().strip(),
            "server": config.SMTP_SERVER,
            "port": config.SMTP_PORT,
            "username": config.SMTP_USERNAME,
            "password": config.SMTP_PASSWORD
        }

        self.test_email_btn.setEnabled(False)
        self.test_email_btn.setText("Envoi en cours...")

        self.worker = EmailTestWorker(self.security_manager, current_config)
        self.worker.result.connect(self.on_test_email_finished)
        self.worker.start()

    def on_test_email_finished(self, success, message):
        self.test_email_btn.setEnabled(True)
        self.test_email_btn.setText("Tester la configuration email")

        if success:
            QMessageBox.information(self, "Succès", message)
        else:
            QMessageBox.critical(self, "Erreur", message)

    def save_settings(self):
        new_settings = {
            "email_sender": config.EMAIL_SENDER,
            "email_recipient": self.email_recipient.text().strip(),
            "max_attempts": self.max_attempts.value(),
            "smtp_server": config.SMTP_SERVER,
            "smtp_port": config.SMTP_PORT,
            "smtp_username": config.SMTP_USERNAME,
            "smtp_password": config.SMTP_PASSWORD
        }

        try:
            with open(config.SETTINGS_FILE, 'w') as f:
                json.dump(new_settings, f, indent=4)
            
            # Mise à jour de la configuration en mémoire
            config.EMAIL_SENDER = new_settings["email_sender"]
            config.EMAIL_RECIPIENT = new_settings["email_recipient"]
            config.MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS = new_settings["max_attempts"]
            config.SMTP_SERVER = new_settings["smtp_server"]
            config.SMTP_PORT = new_settings["smtp_port"]
            config.SMTP_USERNAME = new_settings["smtp_username"]
            config.SMTP_PASSWORD = new_settings["smtp_password"]
            
            # Options de thème et sécurité
            selected_theme = self.theme_combo.currentText()
            try:
                config.THEME = selected_theme
            except Exception:
                pass
            config.SECURITY_PHOTO_ENABLED = bool(self.security_photo_cb.isChecked())
            config.EMAIL_ALERTS_ENABLED = bool(self.email_alerts_cb.isChecked())


            # Sauvegarde persistante des options supplémentaires
            try:
                with open(config.SETTINGS_FILE, 'w') as f:
                    data = {
                        "email_sender": config.EMAIL_SENDER,
                        "email_recipient": config.EMAIL_RECIPIENT,
                        "max_attempts": config.MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS,
                        "smtp_server": config.SMTP_SERVER,
                        "smtp_port": config.SMTP_PORT,
                        "smtp_username": config.SMTP_USERNAME,
                        "smtp_password": config.SMTP_PASSWORD,
                        "theme": config.THEME,
                        "security_photo_enabled": config.SECURITY_PHOTO_ENABLED,
                        "email_alerts_enabled": config.EMAIL_ALERTS_ENABLED
                    }
                    json.dump(data, f, indent=4)
            except Exception:
                pass
            
            QMessageBox.information(self, "Succès", "Paramètres enregistrés.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'enregistrer les paramètres: {e}")

    def open_change_password_dialog(self):
        try:
            dlg = ChangePasswordDialog(self.security_manager, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le dialogue: {e}")

    def change_theme(self, theme):
        """Applique le thème sélectionné à l'application."""
        try:
            theme_manager.apply_theme(theme)
            self.theme = theme
        except Exception:
            # fallback: local stylesheet
            if theme == 'dark':
                self.setStyleSheet("background-color: #2E2E2E; color: white;")
            else:
                self.setStyleSheet("background-color: white; color: black;")
            self.theme = theme

    def create_backup(self):
        # Demander MP et RK pour chiffrer la sauvegarde
        dialog = QDialog(self)
        dialog.setWindowTitle("Sécurité de la sauvegarde")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Pour sécuriser l'export, veuillez confirmer vos identifiants :"))
        
        pw_input = QLineEdit()
        pw_input.setPlaceholderText("Mot de passe principal")
        pw_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(pw_input)
        
        rk_input = QLineEdit()
        rk_input.setPlaceholderText("Clé de récupération")
        layout.addWidget(rk_input)
        
        btn = QPushButton("Confirmer et Sauvegarder")
        btn.clicked.connect(dialog.accept)
        layout.addWidget(btn)
        
        if dialog.exec():
            mp = pw_input.text()
            rk = rk_input.text().strip()
            
            if not mp or not rk:
                QMessageBox.warning(self, "Erreur", "Tous les champs sont requis.")
                return
                
            file_path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la sauvegarde", "thanos_backup.enc", "Thanos Backup (*.enc)")
            if file_path:
                try:
                    VaultManager.backup_vault(config.VAULT_DB_FILE, file_path, mp, rk)
                    QMessageBox.information(self, "Succès", "Sauvegarde chiffrée créée avec succès.")
                except Exception as e:
                    QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde : {e}")