# thanos_app/gui/account_detail_dialog.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                               QPushButton, QHBoxLayout, QMessageBox, QLabel, QApplication)
from PySide6.QtCore import Qt, QTimer
from .styles.dark_theme import apply_dark_theme
from thanos_app.core.vault import Vault
from thanos_app.core.definitions import IMPORTANCE_LEVELS
from .account_dialog import AccountDialog

class AccountDetailDialog(QDialog):
    """
    Fenêtre affichant les détails d'un compte.
    Permet de voir/copier le mot de passe, et d'accéder aux actions de modification/suppression.
    """
    def __init__(self, vault: Vault, account_id: int, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.account_id = account_id
        
        self.account_data = self.vault.db.get_account(self.account_id)
        if not self.account_data:
            self.close()
            return
            
        self.decrypted_password = self.vault.get_decrypted_password(self.account_id)
        
        self.setWindowTitle(f"Détails - {self.account_data.get('name')}")
        self.setMinimumWidth(450)
        apply_dark_theme(self)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Champs d'information (non éditables)
        importance_level = self.account_data.get('importance', 0)
        importance_data = IMPORTANCE_LEVELS.get(importance_level, {})
        self.importance_label = QLabel(importance_data.get('label', 'N/A'))
        self.importance_label.setStyleSheet(f"font-weight: bold; color: {importance_data.get('color', 'white')};")
        
        notes_label = QLabel(self.account_data.get('notes', ''))
        notes_label.setWordWrap(True)

        # Champ de mot de passe avec actions
        self.password_input = QLineEdit(self.decrypted_password)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setReadOnly(True)

        pass_layout = QHBoxLayout()
        pass_layout.addWidget(self.password_input)
        
        self.toggle_btn = QPushButton("👁️")
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_password)
        pass_layout.addWidget(self.toggle_btn)

        self.copy_btn = QPushButton("Copier")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.clicked.connect(self.copy_password)
        pass_layout.addWidget(self.copy_btn)

        form.addRow("Service / Plateforme :", QLabel(self.account_data.get('name', '')))
        form.addRow("Identifiant principal :", QLabel(self.account_data.get('username', '')))
        form.addRow("Mot de passe :", pass_layout)
        form.addRow("URL :", QLabel(self.account_data.get('url', '')))
        form.addRow("Catégorie :", QLabel(self.account_data.get('category', '')))
        form.addRow("Importance :", self.importance_label)
        form.addRow("Tags :", QLabel(self.account_data.get('tags', '')))
        form.addRow("Notes :", notes_label)
        
        layout.addLayout(form)

        # Boutons d'action
        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("✏️ Modifier")
        self.delete_btn = QPushButton("🗑️ Supprimer")
        self.close_btn = QPushButton("Fermer")
        
        self.edit_btn.clicked.connect(self.edit_account)
        self.delete_btn.clicked.connect(self.delete_account)
        self.close_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def toggle_password(self):
        self.password_input.setEchoMode(QLineEdit.Normal if self.password_input.echoMode() == QLineEdit.Password else QLineEdit.Password)

    def copy_password(self):
        QApplication.clipboard().setText(self.decrypted_password)
        self.copy_btn.setText("Copié !")
        self.copy_btn.setEnabled(False)
        QTimer.singleShot(2000, lambda: (self.copy_btn.setText("Copier"), self.copy_btn.setEnabled(True)))

    def edit_account(self):
        main_window = self.parent()
        dialog = AccountDialog(main_window, self.account_data)
        if dialog.exec():
            data = dialog.get_data()
            self.vault.update_account(
                self.account_id, data['name'], data['password'], 
                data['username'], data['url'], data['notes'],
                data['category'], data['importance'], data['tags']
            )
            main_window.load_accounts()
            self.accept()

    def delete_account(self):
        main_window = self.parent()
        confirm = QMessageBox.question(self, "Confirmer suppression",
            f"Voulez-vous vraiment supprimer '{self.account_data.get('name', 'Compte')}' ?",
            QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            self.vault.delete_account(self.account_id)
            main_window.load_accounts()
            self.accept()