# thanos_app/gui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTableView,
    QPushButton, QAbstractItemView, QHeaderView, QMessageBox, QLineEdit, QComboBox, QFrame, QLabel
)
from PySide6.QtCore import QModelIndex, Qt, QSize, QSortFilterProxyModel
from PySide6.QtGui import QIcon, QFont
import os
from .styles.dark_theme import apply_dark_theme
from thanos_app.core.vault import Vault
from .account_table_model import AccountTableModel
from .account_dialog import AccountDialog
from .account_detail_dialog import AccountDetailDialog
from .security_log_dialog import SecurityLogDialog
from .settings_dialog import SettingsDialog
from thanos_app.core.security_manager import SecurityManager
from thanos_app.core.definitions import CATEGORIES, IMPORTANCE_LEVELS

class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        # Créer une instance unique du SecurityManager
        self.security_manager = SecurityManager(self.vault.db, self.vault.key)
        self.all_accounts = [] # Cache pour le filtrage
        self.setWindowTitle("Thanos - Votre Coffre-fort")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet("background-color: #0d1117; color: #c9d1d9;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        toolbar_layout = QHBoxLayout()
        # Buttons with SVG icons
        icons_dir = os.path.join(os.path.dirname(__file__), "styles", "icons")
        add_icon = QIcon(os.path.join(icons_dir, "add.svg"))
        settings_icon = QIcon(os.path.join(icons_dir, "settings.svg"))
        lock_icon = QIcon(os.path.join(icons_dir, "lock.svg"))

        self.add_button = QPushButton("Ajouter")
        self.add_button.setIcon(add_icon)
        self.add_button.setStyleSheet("background-color: #238636; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold;")
        toolbar_layout.addWidget(self.add_button)

        # Boutons d'action contextuels
        self.edit_button = QPushButton("Modifier")
        self.edit_button.setStyleSheet("background-color: #1f6feb; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold;")
        self.edit_button.clicked.connect(self.edit_selected_account)
        self.edit_button.setEnabled(False)
        toolbar_layout.addWidget(self.edit_button)

        self.delete_button = QPushButton("Supprimer")
        self.delete_button.setStyleSheet("background-color: #da3633; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold;")
        self.delete_button.clicked.connect(self.delete_selected_account)
        self.delete_button.setEnabled(False)
        toolbar_layout.addWidget(self.delete_button)

        self.security_btn = QPushButton("Journal de Sécurité")
        self.security_btn.setIcon(lock_icon)
        self.security_btn.setStyleSheet("background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 8px 16px;")
        self.security_btn.clicked.connect(self.show_security_logs)
        toolbar_layout.addWidget(self.security_btn)

        self.settings_btn = QPushButton("Paramètres")
        self.settings_btn.setIcon(settings_icon)
        self.settings_btn.setStyleSheet("background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 8px 16px;")
        self.settings_btn.clicked.connect(self.show_settings)
        toolbar_layout.addWidget(self.settings_btn)
        
        toolbar_layout.addStretch()

        # --- STATS CARDS ---
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        self.stats_labels = {}
        for title, color in [("Total Comptes", "#58a6ff"), ("Critiques", "#da3633"), ("Alertes Sécurité", "#d29922")]:
            card = QFrame()
            card.setStyleSheet(f"background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; border-left: 4px solid {color};")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 15, 20, 15)
            
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("color: #8b949e; font-size: 10pt; font-weight: 600;")
            
            lbl_val = QLabel("0")
            lbl_val.setFont(QFont("Segoe UI", 24, QFont.Bold))
            lbl_val.setStyleSheet("color: #f0f6fc; border: none;")
            
            self.stats_labels[title] = lbl_val
            
            cl.addWidget(lbl_title)
            cl.addWidget(lbl_val)
            stats_layout.addWidget(card)
        
        main_layout.addLayout(stats_layout)

        # Zone de recherche et filtres
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher (Nom, Tags)...")
        self.search_input.setStyleSheet("background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 8px; color: white;")
        self.search_input.textChanged.connect(self.filter_accounts)
        
        self.cat_filter = QComboBox()
        self.cat_filter.addItem("Toutes les catégories")
        self.cat_filter.addItems(CATEGORIES)
        self.cat_filter.setStyleSheet("QComboBox { background-color: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 5px; color: white; }")
        self.cat_filter.currentTextChanged.connect(self.filter_accounts)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.cat_filter)

        self.add_button.clicked.connect(self.add_account)

        self.table_view = QTableView()
        self.setup_model()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_view.doubleClicked.connect(self.show_account_details)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setShowGrid(False)
        self.table_view.setAlternatingRowColors(True)
        
        # Modern Table Style
        self.table_view.setStyleSheet("""
            QTableView {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                gridline-color: transparent;
                selection-background-color: #1f6feb;
                selection-color: white;
                alternate-background-color: #161b22;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                padding: 12px;
                border: none;
                border-bottom: 1px solid #30363d;
                font-weight: bold;
            }
            QTableView::item {
                padding: 8px;
                border-bottom: 1px solid #21262d;
            }
        """)

        main_layout.addLayout(toolbar_layout)
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.table_view)

        self.add_test_data_if_empty()
        self.load_accounts()

    def setup_model(self):
        self.model = AccountTableModel()
        self.table_view.setModel(self.model)

    def load_accounts(self):
        self.all_accounts = self.vault.get_all_accounts()
        self.filter_accounts()
        self.update_stats()

    def update_stats(self):
        total = len(self.all_accounts)
        critical = len([a for a in self.all_accounts if a.get('importance') == 3])
        self.stats_labels["Total Comptes"].setText(str(total))
        self.stats_labels["Critiques"].setText(str(critical))
        # Pour les alertes, on met un placeholder ou on connecte au security manager plus tard
        self.stats_labels["Alertes Sécurité"].setText("0")

    def filter_accounts(self):
        search_text = self.search_input.text().lower()
        cat_text = self.cat_filter.currentText()
        
        filtered = []
        for acc in self.all_accounts:
            # Filtre Catégorie
            if cat_text != "Toutes les catégories" and acc.get('category') != cat_text:
                continue
            
            # Filtre Recherche (Nom ou Tags)
            name_match = search_text in acc.get('name', '').lower()
            tags_match = search_text in acc.get('tags', '').lower()
            
            if not search_text or name_match or tags_match:
                filtered.append(acc)
                
        self.model.refresh_data(filtered)

    def on_selection_changed(self):
        has_selection = self.table_view.selectionModel().hasSelection()
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def add_test_data_if_empty(self):
        if not self.vault.get_all_accounts():
            try:
                self.vault.add_account("Google", "very-strong-password-123", "test@gmail.com", "https://google.com", "", "Sensible", 3, "email, pro")
                self.vault.add_account("GitHub", "another-secure-password", "dev", "https://github.com", "", "Travail", 2, "code, git")
            except Exception as e:
                print(f"Erreur test data: {e}")

    def add_account(self):
        dialog = AccountDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                self.vault.add_account(
                    data['name'], data['password'], data['username'], 
                    data['url'], data['notes'],
                    data['category'], data['importance'], data['tags']
                )
                self.load_accounts()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", str(e))

    def show_account_details(self, index: QModelIndex):
        if not index.isValid():
            return
        
        row = index.row()
        account_id = self.model.get_account_id_for_row(row)
        if not account_id: return
        
        try:
            dialog = AccountDetailDialog(self.vault, account_id, self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible d'afficher les détails : {e}")

    def edit_selected_account(self):
        index = self.table_view.currentIndex()
        if index.isValid():
            # On réutilise la logique existante via le dialogue de détail ou directement
            # Ici on ouvre le détail qui a le bouton modifier, ou on peut ouvrir directement le dialogue d'édition
            self.show_account_details(index)

    def delete_selected_account(self):
        index = self.table_view.currentIndex()
        if not index.isValid(): return
        
        row = index.row()
        account_id = self.model.get_account_id_for_row(row)
        acc_name = index.siblingAtColumn(1).data() # Colonne nom
        
        confirm = QMessageBox.question(self, "Confirmer suppression",
            f"Voulez-vous vraiment supprimer '{acc_name}' ?",
            QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.vault.delete_account(account_id)
            self.load_accounts()

    def show_security_logs(self):
        dialog = SecurityLogDialog(self.security_manager, self)
        dialog.exec()

    def show_settings(self):
        dialog = SettingsDialog(self.security_manager, self)
        dialog.exec()

    def closeEvent(self, event):
        self.vault.close()
        super().closeEvent(event)
