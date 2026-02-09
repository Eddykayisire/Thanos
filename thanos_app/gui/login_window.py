import os
import datetime
import threading

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel, QInputDialog, QFileDialog,
    QMessageBox, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QFont, QColor
from thanos_app.core.vault import VaultManager, Vault
from thanos_app.core.database import DatabaseManager
from thanos_app.core.security_manager import SecurityManager
from thanos_app.core.definitions import LOG_EVENT_INCORRECT_ATTEMPT, LOG_EVENT_SECURITY_TRIGGER, LOG_EVENT_LOGIN_SUCCESS, LOG_EVENT_PHOTO_CAPTURE
from .styles.dark_theme import apply_dark_theme
from thanos_app.utils.password_validator import validate_master_password
import config

class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thanos - Connexion")
        self.showMaximized()
        self.setStyleSheet("background: qradialgradient(cx:0.5, cy:0.5, radius: 1.2, fx:0.5, fy:0.5, stop:0 #161b22, stop:1 #000000);")

        self.vault: Vault | None = None
        self.db_manager = DatabaseManager(config.VAULT_DB_FILE)
        
        # Tampon pour les événements/photos avant déverrouillage du coffre
        self._pending_logs = [] 
        # Manager temporaire pour actions immédiates (email) sans clé du coffre
        self._temp_security_manager = SecurityManager(self.db_manager, os.urandom(32))

        self._incorrect_attempts_count = 0
        self._last_attempt_time = None
        self._login_blocked = False
        self._block_timer = QTimer(self)
        self._block_timer.setSingleShot(True)
        self._block_timer.timeout.connect(self._unblock_login)

        self.setup_ui()
        self._check_vault_exists()
        
        # Animation d'apparition en fondu
        self.setWindowOpacity(0)
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(800)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def setup_ui(self):
        # Layout principal centré
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Carte centrale
        self.card = QFrame()
        self.card.setObjectName("LoginCard")
        self.card.setFixedSize(440, 600)
        self.card.setStyleSheet("""
            #LoginCard {
                background-color: rgba(22, 27, 34, 0.95);
                border-radius: 24px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        
        # Ombre portée
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(60)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)

        # Logo / Icône
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "styles", "icons", "logo_icon.svg")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            icon_label.setPixmap(pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        
        # Titre
        title = QLabel()
        text_path = os.path.join(os.path.dirname(__file__), "styles", "icons", "logo_text.svg")
        if os.path.exists(text_path):
            pix = QPixmap(text_path)
            title.setPixmap(pix.scaled(280, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            title.setText("Thanos")
            title.setFont(QFont("Segoe UI", 28, QFont.Bold))
            title.setStyleSheet("color: #ffffff; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Sécurité Maximale")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8b949e; font-size: 11pt; margin-bottom: 20px; letter-spacing: 1px;")

        # Champ mot de passe
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Mot de passe principal")
        self.password_input.returnPressed.connect(self.attempt_login)
        self.password_input.textChanged.connect(self.update_strength_indicator)
        self.password_input.setFixedHeight(50)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 0 15px;
                color: white;
                font-size: 15px;
                selection-background-color: #9C27B0;
            }
            QLineEdit:focus { 
                border: 1px solid #9C27B0; 
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        
        self.strength_label = QLabel("")
        self.strength_label.setAlignment(Qt.AlignLeft)
        self.strength_label.setStyleSheet("font-size: 10pt; font-weight: bold; margin-top: 5px;")

        # Status et Boutons
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #ff7b72; font-weight: bold;")
        self.status_label.setWordWrap(True)

        self.login_button = QPushButton("Ouvrir le coffre")
        self.login_button.clicked.connect(self.attempt_login)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setFixedHeight(50)
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9C27B0, stop:1 #7B1FA2);
                color: white;
                border-radius: 12px;
                font-weight: bold;
                font-size: 15px;
                border: none;
            }
            QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #AB47BC, stop:1 #8E24AA); }
            QPushButton:pressed { background-color: #6A1B9A; }
        """)

        self.create_button = QPushButton("Créer un coffre")
        self.create_button.clicked.connect(self.create_vault)
        self.create_button.setCursor(Qt.PointingHandCursor)
        self.create_button.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2196F3, stop:1 #1976D2);
                color: white;
                border-radius: 12px;
                font-weight: bold;
                font-size: 15px;
                border: none;
            }
            QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #42A5F5, stop:1 #1E88E5); }
            QPushButton:pressed { background-color: #0D47A1; }
        """)
        self.create_button.setFixedHeight(50)

        self.import_button = QPushButton("Importer un coffre existant")
        self.import_button.setCursor(Qt.PointingHandCursor)
        self.import_button.clicked.connect(self.import_vault)
        self.import_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 12px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.05); color: white; }
        """)
        self.import_button.setFixedHeight(40)

        # Assemblage
        card_layout.addStretch()
        card_layout.addWidget(icon_label)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.strength_label)
        card_layout.addWidget(self.status_label)
        card_layout.addSpacing(10)
        card_layout.addWidget(self.login_button)
        card_layout.addWidget(self.create_button)
        card_layout.addWidget(self.import_button)
        card_layout.addStretch()

        main_layout.addWidget(self.card)

    def _check_vault_exists(self):
        vault_initialized = False
        if os.path.exists(config.VAULT_DB_FILE):
            try:
                # Le fichier peut exister (créé par SecurityManager pour les logs),
                # on vérifie donc la présence de la table de configuration.
                if not self.db_manager.conn:
                    self.db_manager.connect()
                cursor = self.db_manager.conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vault_config'")
                if cursor.fetchone():
                    vault_initialized = True
            except Exception:
                pass

        if vault_initialized:
            self.create_button.setVisible(False)
            self.login_button.setVisible(True)
            self.import_button.setVisible(False)
            self.setWindowTitle("Thanos - Ouvrir le coffre")
            self.strength_label.setVisible(False)
        else:
            self.login_button.setVisible(False)
            self.create_button.setVisible(True)
            self.import_button.setVisible(True)
            self.setWindowTitle("Thanos - Créer un nouveau coffre")
            self.strength_label.setVisible(True)

    def update_strength_indicator(self, text):
        if not self.create_button.isVisible(): return # Only show for creation
        
        length = len(text)
        if length == 0:
            self.strength_label.setText("")
            return
        
        res = validate_master_password(text)
        self.strength_label.setText(res['label'])
        self.strength_label.setStyleSheet(f"color: {res['color']}; font-weight: bold; font-size: 10pt; margin-top: 5px;")

    def _unblock_login(self):
        self._login_blocked = False
        self.status_label.setText("")
        self.login_button.setEnabled(True)
        self.password_input.setEnabled(True)

    def attempt_login(self):
        if self._login_blocked:
            self.status_label.setText(f"Veuillez patienter {config.LOGIN_BLOCK_DELAY_SECONDS} secondes avant de réessayer.")
            return

        master_password = self.password_input.text()
        if not master_password:
            self.status_label.setText("Veuillez entrer un mot de passe.")
            return

        try:
            self.vault = VaultManager.open_vault(config.VAULT_DB_FILE, master_password)
            # Connexion réussie
            self._incorrect_attempts_count = 0
            self.status_label.setText("")
            
            # Initialisation du manager de sécurité avec la vraie clé
            self.security_manager = SecurityManager(self.db_manager, self.vault.key) 
            # Traitement des logs et photos en attente
            self._flush_pending_logs()
            self._process_pending_photos()
            self.security_manager.log_event(LOG_EVENT_LOGIN_SUCCESS, {"method": "password"})
            
            self.accept() # Close login window and proceed to main window
        except ValueError as e: # Incorrect password or invalid vault config
            error_msg = str(e)
            if "DEVICE_MISMATCH" in error_msg:
                self.status_label.setText("Nouvel appareil détecté.")
                QApplication.processEvents()
                
                recovery_key, ok = QInputDialog.getText(
                    self, "Migration de Sécurité",
                    "Ce coffre est lié à un autre appareil.\n\n"
                    "Pour autoriser la migration et re-chiffrer vos données,\n"
                    "veuillez entrer votre Clé de Récupération :",
                    QLineEdit.Normal
                )
                
                if ok and recovery_key:
                    try:
                        self.vault = VaultManager.open_vault(config.VAULT_DB_FILE, master_password, recovery_key.strip())
                        QMessageBox.information(self, "Migration Réussie", 
                                              "Votre coffre a été migré avec succès vers cet appareil.\n"
                                              "L'ancien appareil n'a plus accès.")
                        
                        self._incorrect_attempts_count = 0
                        self.security_manager = SecurityManager(self.db_manager, self.vault.key)
                        self._flush_pending_logs()
                        self.security_manager.log_event("VAULT_MIGRATION", {"status": "success"})
                        self.accept()
                        return
                    except Exception as mig_e:
                        QMessageBox.critical(self, "Échec Migration", f"Erreur : {mig_e}")
                        return
                else:
                    self.status_label.setText("Migration annulée.")
                    return

            self._incorrect_attempts_count += 1
            self._last_attempt_time = datetime.datetime.now()
            
            self.status_label.setText(f"Mot de passe incorrect. Veuillez patienter {config.LOGIN_BLOCK_DELAY_SECONDS} secondes avant de réessayer.")
            self.login_button.setEnabled(False)
            self.password_input.setEnabled(False)
            self._login_blocked = True
            self._block_timer.start(config.LOGIN_BLOCK_DELAY_SECONDS * 1000)
            self.password_input.clear()
            
            # Force l'affichage immédiat des changements d'interface pour éviter l'impression de plantage
            QApplication.processEvents()

            # Enregistrement de la tentative échouée
            self._pending_logs.append((LOG_EVENT_INCORRECT_ATTEMPT, 
                                       {"attempt_number": self._incorrect_attempts_count, "error": str(e)}))

            if self._incorrect_attempts_count >= config.MAX_INCORRECT_ATTEMPTS_BEFORE_SECURITY_EVENTS:
                self.status_label.setText("Seuil de tentatives atteint. Événements de sécurité déclenchés.")
                QApplication.processEvents()
                
                self._pending_logs.append((LOG_EVENT_SECURITY_TRIGGER, 
                                           {"attempts_count": self._incorrect_attempts_count}))
                
                # Capture photo en mémoire (sera chiffrée après connexion réussie)
                photo_bytes = self._temp_security_manager.capture_webcam_bytes()
                
                if not photo_bytes and not self._temp_security_manager.is_camera_available():
                    print("⚠️ ATTENTION: La librairie 'opencv-python' est manquante ou la caméra est introuvable.")
                    print("   Installez-la avec: pip install opencv-python")
                
                # Envoi d'email en arrière-plan
                self._run_background_alert(self._incorrect_attempts_count)
                
                if photo_bytes:
                    self._save_temp_photo(photo_bytes)
                    print("📸 Photo capturée et mise en attente (sera chiffrée à la connexion).")
                else:
                    print("Warning: No photo captured (Camera disabled or unavailable)")

        except FileNotFoundError:
            QMessageBox.warning(self, "Erreur", "Le fichier du coffre-fort n'existe pas ou est corrompu.")
            self.create_button.setVisible(True)
            self.login_button.setVisible(False)
        except Exception as e:
            QMessageBox.critical(self, "Erreur inattendue", f"Une erreur est survenue: {e}")

    def _run_background_alert(self, attempts):
        def task():
            try:
                # Connexion isolée pour le thread (évite les conflits SQLite)
                db = DatabaseManager(config.VAULT_DB_FILE)
                db.connect()
                # Manager temporaire (suffisant pour email et logs non chiffrés)
                sm = SecurityManager(db, os.urandom(32))
                sm.send_email_alert(attempts)
                db.close()
            except Exception as e:
                print(f"Background alert error: {e}")
        
        threading.Thread(target=task, daemon=True).start()

    def _flush_pending_logs(self):
        for event_type, details in self._pending_logs:
            self.security_manager.log_event(event_type, details)

    def _save_temp_photo(self, photo_bytes):
        # Sauvegarde temporaire de la photo brute (en attendant le chiffrement)
        if not os.path.exists(config.SECURITY_PHOTO_DIR):
            os.makedirs(config.SECURITY_PHOTO_DIR)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(config.SECURITY_PHOTO_DIR, f"pending_{timestamp}.jpg")
        try:
            with open(temp_path, "wb") as f:
                f.write(photo_bytes)
        except Exception as e:
            print(f"Error saving temp photo: {e}")

    def _process_pending_photos(self):
        if not os.path.exists(config.SECURITY_PHOTO_DIR): return
        
        # Trier pour traiter dans l'ordre chronologique
        files = sorted([f for f in os.listdir(config.SECURITY_PHOTO_DIR) if f.startswith("pending_") and f.endswith(".jpg")])
        
        for filename in files:
            file_path = os.path.join(config.SECURITY_PHOTO_DIR, filename)
            try:
                with open(file_path, "rb") as f:
                    photo_bytes = f.read()
                
                # Utiliser le security_manager authentifié (avec la clé du coffre)
                enc_filename = self.security_manager.save_encrypted_photo(photo_bytes)
                if enc_filename:
                    self.security_manager.log_event(LOG_EVENT_PHOTO_CAPTURE, {"status": "success", "filename": enc_filename})
                    print(f"✅ Photo en attente traitée et chiffrée : {enc_filename}")
                
                os.remove(file_path)
            except Exception as e:
                print(f"Error processing pending photo {filename}: {e}")

    def create_vault(self):
        master_password = self.password_input.text()
        if not master_password:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un mot de passe principal.")
            return
        
        # Validation stricte avant création
        val = validate_master_password(master_password)
        if not val['valid']:
            QMessageBox.warning(self, "Mot de passe trop faible", f"Sécurité insuffisante :\n{val['feedback']}")
            return

        try:
            recovery_key = VaultManager.create_vault(config.VAULT_DB_FILE, master_password)
            
            msg = QMessageBox(self)
            msg.setWindowTitle("⚠️ Clé de Récupération - IMPORTANT")
            msg.setText("Votre coffre-fort a été créé avec succès.")
            msg.setInformativeText(
                "Voici votre CLÉ DE RÉCUPÉRATION.\n\n"
                f"<h2 style='color:#ff7b72; text-align:center;'>{recovery_key}</h2>\n\n"
                "Copiez-la et conservez-la en lieu sûr (hors de cet ordinateur).\n"
                "Elle sera **INDISPENSABLE** pour transférer votre coffre sur un autre appareil."
            )
            msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
            msg.setIcon(QMessageBox.Warning)
            msg.exec()
            
            self._check_vault_exists()
            self.password_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de créer le coffre-fort: {e}")

    def import_vault(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Sélectionner une sauvegarde ou un coffre", "", "Thanos Files (*.enc *.db)")
        if file_path:
            try:
                if file_path.endswith(".enc"):
                    # Restauration sécurisée
                    dialog = QDialog(self)
                    dialog.setWindowTitle("Restauration Sécurisée")
                    layout = QVBoxLayout(dialog)
                    layout.addWidget(QLabel("Fichier chiffré détecté.\nEntrez vos identifiants pour déchiffrer et restaurer :"))
                    
                    pw_input = QLineEdit()
                    pw_input.setPlaceholderText("Mot de passe principal")
                    pw_input.setEchoMode(QLineEdit.Password)
                    layout.addWidget(pw_input)
                    
                    rk_input = QLineEdit()
                    rk_input.setPlaceholderText("Clé de récupération")
                    layout.addWidget(rk_input)
                    
                    btn = QPushButton("Restaurer")
                    btn.clicked.connect(dialog.accept)
                    layout.addWidget(btn)
                    
                    if dialog.exec():
                        VaultManager.restore_vault(file_path, config.VAULT_DB_FILE, pw_input.text(), rk_input.text().strip())
                        QMessageBox.information(self, "Succès", "Coffre restauré et migré avec succès.")
                        self._check_vault_exists()
                else:
                    # Import simple (copie)
                    import shutil
                    shutil.copy2(file_path, config.VAULT_DB_FILE)
                    QMessageBox.information(self, "Importation", "Fichier importé. Veuillez vous connecter pour lancer la migration.")
                    self._check_vault_exists()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Impossible d'importer le fichier : {e}")