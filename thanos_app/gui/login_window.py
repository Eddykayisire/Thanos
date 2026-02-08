import os
import datetime
import threading

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel,
    QMessageBox, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation
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
        self.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0E1117, stop:1 #161B22);")

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

    def setup_ui(self):
        # Layout principal centré
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Carte centrale
        self.card = QFrame()
        self.card.setObjectName("LoginCard")
        self.card.setFixedSize(480, 650)
        self.card.setStyleSheet("""
            #LoginCard {
                background-color: #1e2228;
                border-radius: 16px;
                border: 1px solid #333;
            }
        """)
        
        # Ombre portée
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)

        # Logo / Icône
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "styles", "icons", "lock.svg")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            icon_label.setPixmap(pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        
        # Titre
        title = QLabel("Thanos")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 5px;")
        
        subtitle = QLabel("Sécurité Maximale")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8b949e; font-size: 11pt; margin-bottom: 30px;")

        # Champ mot de passe
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Mot de passe principal")
        self.password_input.returnPressed.connect(self.attempt_login)
        self.password_input.textChanged.connect(self.update_strength_indicator)
        self.password_input.setFixedHeight(50)
        self.password_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 0 15px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #58a6ff; }
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
        self.login_button.setStyleSheet("background-color: #238636; color: white; border-radius: 8px; font-weight: bold; font-size: 14px;")

        self.create_button = QPushButton("Créer un coffre")
        self.create_button.clicked.connect(self.create_vault)
        self.create_button.setCursor(Qt.PointingHandCursor)
        self.create_button.setStyleSheet("background-color: #1f6feb; color: white; border-radius: 8px; font-weight: bold; font-size: 14px;")
        self.create_button.setFixedHeight(50)

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
            self.setWindowTitle("Thanos - Ouvrir le coffre")
            self.strength_label.setVisible(False)
        else:
            self.login_button.setVisible(False)
            self.create_button.setVisible(True)
            self.setWindowTitle("Thanos - Créer un nouveau coffre")
            self.strength_label.setVisible(True)

    def update_strength_indicator(self, text):
        if not self.create_button.isVisible(): return # Only show for creation
        
        length = len(text)
        if length == 0:
            self.strength_label.setText("")
            return

        score = 0
        if any(c.islower() for c in text): score += 1
        if any(c.isupper() for c in text): score += 1
        if any(c.isdigit() for c in text): score += 1
        if any(not c.isalnum() for c in text): score += 1
        if length >= 12: score += 1

        labels = {0: ("❌ Faible", "#ff7b72"), 1: ("❌ Faible", "#ff7b72"), 2: ("⚠️ Moyen", "#d29922"), 
                  3: ("✅ Fort", "#3fb950"), 4: ("✅ Très fort", "#238636"), 5: ("🔥 Légendaire", "#a371f7")}
        
        text_label, color = labels.get(score, ("❌ Faible", "#ff7b72"))
        self.strength_label.setText(text_label)
        self.strength_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 10pt; margin-top: 5px;")

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
        
        try:
            VaultManager.create_vault(config.VAULT_DB_FILE, master_password)
            QMessageBox.information(self, "Succès", "Coffre-fort créé avec succès. Vous pouvez maintenant vous connecter.")
            self._check_vault_exists()
            self.password_input.clear()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de créer le coffre-fort: {e}")