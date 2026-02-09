from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QTableView, QScrollArea, QFrame,
    QComboBox, QCheckBox, QTextEdit, QSpacerItem, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
from PySide6.QtCore import QAbstractTableModel
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap
import os
from .styles.dark_theme import apply_dark_theme
from .styles.base import fill_color
from .styles.utils import add_shadow
from thanos_app.core.vault import VaultManager, Vault, Account
from thanos_app.core.database import DatabaseManager
from thanos_app.core.security_manager import SecurityManager
from .account_table_model import AccountTableModel
import config
from PySide6.QtWidgets import QMessageBox
from enum import Enum

from PySide6.QtWidgets import QStyledItemDelegate

class ModernLoginPage(QWidget):
    login_success = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setObjectName("modern-login-page")
        self.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0E1117, stop:1 #161B22);")
        main = QHBoxLayout(self)
        main.setContentsMargins(60, 60, 60, 60)

        # Left: decorative area
        left = QVBoxLayout()
        left.addStretch()
        
        # Logo Icon
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "styles", "icons", "logo_icon.svg")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            icon_label.setPixmap(pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            icon_label.setAlignment(Qt.AlignCenter)
            left.addWidget(icon_label)

        # Logo Text
        text_label = QLabel()
        text_path = os.path.join(os.path.dirname(__file__), "styles", "icons", "logo_text.svg")
        if os.path.exists(text_path):
            pix = QPixmap(text_path)
            text_label.setPixmap(pix.scaled(280, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            text_label.setText("THANOS")
            text_label.setFont(QFont("Segoe UI", 32, QFont.Bold))
            text_label.setStyleSheet("color: #9C27B0; letter-spacing: 4px;")
            
        text_label.setAlignment(Qt.AlignCenter)
        left.addWidget(text_label)
        
        subtitle = QLabel("Votre coffre-fort numérique sécurisé")
        subtitle.setAlignment(Qt.AlignCenter)
        left.addWidget(subtitle)
        left.addStretch()

        # Right: central card
        card = QVBoxLayout()
        card_widget = QWidget()
        card_widget.setObjectName("login-card")
        add_shadow(card_widget)
        card_layout = QVBoxLayout(card_widget)
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(14)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Mot de passe principal")
        self.password_input.setFixedHeight(48)
        self.password_input.setStyleSheet("font-size: 12pt; padding: 8px;")

        self.strength_label = QLabel("")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #ff8b8b; font-weight: bold;")
        self.strength_label.setAlignment(Qt.AlignLeft)

        self.unlock_btn = QPushButton("Déverrouiller le coffre")
        self.unlock_btn.setFixedHeight(48)
        self.unlock_btn.setProperty("variant", "primary")
        self.unlock_btn.clicked.connect(self._on_unlock)

        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.strength_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.unlock_btn)

        card.addWidget(card_widget)

        main.addLayout(left, 1)
        main.addLayout(card, 1)
        
        # Set initial focus
        self.password_input.setFocus()


        # Live password strength feedback
        self.password_input.textChanged.connect(self._update_strength)

    def _update_strength(self, text: str):
        length = len(text)
        if length == 0:
            self.strength_label.setText("")
            self.strength_label.setStyleSheet("")
            return
        score = 0
        if any(c.islower() for c in text): score += 1
        if any(c.isupper() for c in text): score += 1
        if any(c.isdigit() for c in text): score += 1
        if any(not c.isalnum() for c in text): score += 1
        if length >= 12: score += 1

        if score <= 2:
            self.strength_label.setText("❌ Faible")
            self.strength_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
        elif score == 3:
            self.strength_label.setText("⚠️ Fort")
            self.strength_label.setStyleSheet("color: #ffb74d; font-weight: bold;")
        elif score == 4:
            self.strength_label.setText("✅ Très fort")
            self.strength_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        else:
            self.strength_label.setText("🔥 Légendaire")
            self.strength_label.setStyleSheet("color: #9c27b0; font-weight: bold;")

    def _on_unlock(self):
        # Live validation
        self.status_label.setText("")
        master_password = self.password_input.text()
        if not master_password:
            self.status_label.setText("Veuillez entrer un mot de passe.")
            return

        try:
            vault = VaultManager.open_vault(config.VAULT_DB_FILE, master_password)
            # Validation successful
            self.password_input.clear()
            self.status_label.setText("")
            self.login_success.emit(vault)
        except ValueError:
            # Incorrect password
            self.status_label.setStyleSheet("color: #ff6b6b; font-weight: bold;")
            self.status_label.setText("Mot de passe incorrect.")
            self.password_input.clear()
        except FileNotFoundError:
            self.status_label.setText("Coffre-fort introuvable ou corrompu.")
        except Exception as e:
            # Other unexpected errors
            self.status_label.setText(f"Erreur: {e}")


class ModernDashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: #12161d;")
        v = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("THÁNOS")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #fff;")
        header.addWidget(title)
        header.addStretch()


        # Add icons to buttons
        icons_dir = os.path.join(os.path.dirname(__file__), "styles", "icons")
        settings_icon = QIcon(os.path.join(icons_dir, "settings.svg"))
        lock_icon = QIcon(os.path.join(icons_dir, "lock.svg"))
        self.settings_btn = QPushButton("Paramètres")
        self.lock_btn = QPushButton("Verrouiller")

        header.addWidget(self.settings_btn) # settings_icon
        header.addWidget(self.lock_btn) # lock_icon

        v.addLayout(header)

        # Stats cards
        stats = QHBoxLayout()
        stats_titles = ("Total mots de passe", "Critiques", "Alertes")
        self.stats_labels = {}

        for name in stats_titles:
            card = QFrame()
            card.setObjectName("stat-card")

            cl = QVBoxLayout(card)
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #fff; font-size: 11pt;")
            lbl.setAlignment(Qt.AlignCenter)
            val = QLabel("—")
            val.setAlignment(Qt.AlignCenter)
            val.setFont(QFont("Segoe UI", 18, QFont.Bold))
            val.setStyleSheet("color: #fff;")
            cl.addWidget(lbl)
            self.stats_labels[name] = val
            cl.addWidget(val)
            stats.addWidget(card)
        v.addLayout(stats)

        # Table area (placeholder for AccountTableModel)
        # Header
        toolbar = QHBoxLayout()
        search_input = QLineEdit()

        search_input.setPlaceholderText("Rechercher...")
        toolbar.addWidget(search_input)
        toolbar.addStretch()
        add_btn = QPushButton("Ajouter")
        add_btn.setProperty("variant", "primary")
        toolbar.addWidget(add_btn)
        v.addLayout(toolbar)

        # Table
        self.table = QTableView()
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


        # Apply modern table style
        # Modern Table Style
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.setShowGrid(False)

        # More subtle
        self.table.setStyleSheet("""
            QTableView {
                background-color: rgba(255,255,255,0.03);
                border: none;
                gridline-color: rgba(255,255,255,0.03);
                selection-background-color: rgba(79,179,255,0.12);
            }
            QHeaderView::section {
                background-color: transparent;
                padding: 8px;
                border: none;
                font-weight: 600;
                color: #cfe8ff;
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }
            QTableView::item {
                padding: 4px;
            }
        """)

        # Mock Data

        v.addWidget(self.table)


class Importance(Enum):
    CRITICAL = 3
    HIGH = 2
    NORMAL = 1

class ImportanceDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index: QModelIndex):
        importance = Importance(index.model().data(index, Qt.UserRole))
        color = {
            Importance.CRITICAL: "#ff6b6b",
            Importance.HIGH: "#ffb74d",
            Importance.NORMAL: "#4caf50"
        }[importance]
        painter.fillRect(option.rect, QColor(color))


class SecurityLogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background: #12161d;")
        v = QVBoxLayout(self)
        title = QLabel("Journal de sécurité")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        v.addWidget(title)
        title.setStyleSheet("color: #fff;")

        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.cards_layout = QVBoxLayout(container)
        self.cards_layout.addStretch()
        scroll.setWidget(container)
        v.addWidget(scroll)

    def add_log_card(self, text: str, timestamp: str = "—"):
        card = QFrame()
        card.setObjectName("log-card")
        layout = QHBoxLayout(card)

        # Left side: Content
        left = QVBoxLayout()
        header = QLabel(f"{timestamp}")
        header.setStyleSheet("color: #ddd; font-size: 9pt;")
        body = QLabel(text)
        body.setWordWrap(True)
        left.addWidget(header) # Timestamp
        left.addWidget(body) # Log Text

        # Right side: Thumbnail + Buttons
        right = QVBoxLayout()
        thumb = QLabel()

        thumb.setFixedSize(120, 72)
        thumb.setStyleSheet("background: rgba(255,255,255,0.02); border-radius:6px;")
        right.addWidget(thumb) # Placeholder
        btn_view = QPushButton("Voir image")
        btn_delete = QPushButton("Supprimer")
        btn_view.setProperty("variant", "ghost") # style
        right.addWidget(btn_view)
        right.addWidget(btn_delete)

        # Connect signals using a lambda function to capture the current timestamp
        btn_view.clicked.connect(lambda checked=False, ts=timestamp: self.view_image(ts))
        btn_delete.clicked.connect(lambda checked=False, ts=timestamp: self.delete_log(ts))



    def view_image(self, timestamp):
        QMessageBox.information(self, "Voir image", f"Afficher l'image pour {timestamp}")

    def delete_log(self, timestamp):
        QMessageBox.warning(self, "Supprimer log", f"Supprimer le log pour {timestamp}")
        layout.addLayout(left, 1)
        layout.addLayout(right)

        # Insert at top
        self.cards_layout.insertWidget(0, card)

from PySide6.QtWidgets import QStyledItemDelegate

class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    # Adjust SettingsPage
    def setup_ui(self):
        v = QVBoxLayout(self)
        title = QLabel("Paramètres")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #fff;")
        v.addWidget(title)

        # Appearance
        appearance_box = QHBoxLayout()
        appearance_box.addWidget(QLabel("Thème:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Sombre", "Clair"])

        appearance_box.addWidget(self.theme_combo)
        v.addLayout(appearance_box)

        # Security options
        sec_box = QVBoxLayout()
        self.change_pw_btn = QPushButton("Changer le mot de passe principal")
        self.capture_checkbox = QCheckBox("Activer capture de sécurité")
        sec_box.addWidget(self.change_pw_btn)
        sec_box.addWidget(self.capture_checkbox)
        v.addLayout(sec_box)

        # Alerts
        alert_box = QHBoxLayout()
        alert_box.addWidget(QLabel("Email d'alerte:"))
        self.email_edit = QLineEdit()
        alert_box.addWidget(self.email_edit)
        v.addLayout(alert_box)

        # Spacer
        v.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))


class ModernMainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("THÁNOS")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet("background: #0E1117;")

        apply_dark_theme(self)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = ModernLoginPage()
        self.dashboard_page = ModernDashboardPage()
        self.logs_page = SecurityLogPage()
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.login_page)
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.logs_page)
        self.stack.addWidget(self.settings_page)

        self._on_login_success(vault=None) # Start on login page

        # Wire navigation
        self.login_page.login_success.connect(self._on_login_success)
        self.dashboard_page.settings_btn.clicked.connect(self.show_settings)
        self.dashboard_page.lock_btn.clicked.connect(self.lock_app)

    def _animate_switch(self, new_index: int):
        # Add animated transition between widgets in stack

        old_widget = self.stack.currentWidget()
        if old_widget is None:
            self.stack.setCurrentIndex(new_index)
            return

        new_widget = self.stack.widget(new_index)
        if new_widget is old_widget:
            return

        # Prepare opacity effects
        old_effect = QGraphicsOpacityEffect(old_widget)
        old_widget.setGraphicsEffect(old_effect)
        new_effect = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(new_effect)
        new_effect.setOpacity(0.0)

        # Ensure new widget is visible under the stack
        # Use fade animation
        self.stack.setCurrentIndex(new_index)
        anim_old = QPropertyAnimation(old_effect, b"opacity")
        anim_old.setDuration(300)
        anim_old.setStartValue(1.0)
        anim_old.setEndValue(0.0)
        anim_old.setEasingCurve(QEasingCurve.InOutQuad)

        # Define new animation
        anim_new = QPropertyAnimation(new_effect, b"opacity")
        anim_new.setDuration(300)
        anim_new.setStartValue(0.0)
        anim_new.setEndValue(1.0)
        anim_new.setEasingCurve(QEasingCurve.InOutQuad)

        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_old)
        group.addAnimation(anim_new)

        def on_finished():
            try:
                old_widget.setGraphicsEffect(None)
            except Exception:
                pass
            try:
                new_widget.setGraphicsEffect(None)
            except Exception:
                pass

        group.finished.connect(on_finished)
        group.start()

    def show_dashboard(self, vault=None):
        self._animate_switch(self.stack.indexOf(self.dashboard_page))

    def _on_login_success(self, vault: Vault | None):

        # Load vault and setup security manager
        if vault is None:
            self._animate_switch(self.stack.indexOf(self.login_page))

            return
        self.vault = vault
        try:
            self.security_manager = SecurityManager(self.vault.db, self.vault.key)
        except Exception:
            self.security_manager = None


        # Set login page to zero
        self._animate_switch(self.stack.indexOf(self.login_page))

        # Wire table model
        self.account_model = AccountTableModel(self.vault.get_all_accounts())
        self.dashboard_page.table.setModel(self.account_model)
        self.show_dashboard(vault)

        # Mettre à jour les statistiques
        total_accounts = len(self.vault.get_all_accounts())
        critical_accounts = len([acc for acc in self.vault.get_all_accounts() if acc.get('importance') == 3])
        self.dashboard_page.stats_labels["Total mots de passe"].setText(str(total_accounts))
        self.dashboard_page.stats_labels["Critiques"].setText(str(critical_accounts))
        # Les alertes nécessiteraient une logique plus complexe
        self.dashboard_page.stats_labels["Alertes"].setText("0")
    def show_logs(self):

        self._animate_switch(self.stack.indexOf(self.logs_page))
    def show_settings(self):

        self._animate_switch(self.stack.indexOf(self.settings_page))

    def lock_app(self):
        self._animate_switch(self.stack.indexOf(self.login_page))
