from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                               QTextEdit, QPushButton, QHBoxLayout, QMessageBox, QComboBox, QLabel)
from PySide6.QtCore import Qt
from thanos_app.utils.password_generator import generate_password
from .styles.dark_theme import apply_dark_theme
from thanos_app.core.definitions import CATEGORIES, IMPORTANCE_LEVELS, CATEGORY_TO_IMPORTANCE, SERVICE_TO_URL

class AccountDialog(QDialog):
    def __init__(self, parent=None, account_data=None):
        super().__init__(parent)
        self.setWindowTitle("Détails du compte")
        self.setMinimumWidth(400)
        # Ne pas suggérer/écraser l'URL si une URL existe déjà (mode édition) ou si l'utilisateur l'a modifiée.
        self.user_edited_url = True if account_data and account_data.get('url') else False

        self._current_importance_level = 1 # Default
        self.account_data = account_data or {}
        apply_dark_theme(self)
        self.setup_ui()
        self.update_importance_from_category(self.category_combo.currentText())
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit(self.account_data.get('name', ''))
        self.name_input.setPlaceholderText("ex: Google, Facebook, Ma Banque...")
        self.name_input.textChanged.connect(self.suggest_url)

        self.username_input = QLineEdit(self.account_data.get('username', ''))
        self.username_input.setPlaceholderText("ex: mon.email@domaine.com, mon_user...")
        
        self.password_input = QLineEdit(self.account_data.get('password', ''))
        self.password_input.setEchoMode(QLineEdit.Password)
        
        self.url_input = QLineEdit(self.account_data.get('url', ''))
        self.url_input.setPlaceholderText("Optionnel, ex: https://www.domaine.com")
        self.url_input.textEdited.connect(self.on_url_manually_edited)
        
        # Nouveaux champs
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        self.category_combo.setCurrentText(self.account_data.get('category', 'Autre'))
        self.category_combo.currentTextChanged.connect(self.update_importance_from_category)
        
        # Le champ d'importance est maintenant un label non-éditable
        self.importance_label = QLabel()
        self.importance_label.setStyleSheet("font-weight: bold;")
        
        self.tags_input = QLineEdit(self.account_data.get('tags', ''))
        self.tags_input.setPlaceholderText("ex: crypto, travail, urgent")

        self.notes_input = QTextEdit()
        self.notes_input.setPlainText(self.account_data.get('notes', ''))
        self.notes_input.setMaximumHeight(80)

        # Password actions
        pass_layout = QHBoxLayout()
        pass_layout.addWidget(self.password_input)
        
        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle_password)
        pass_layout.addWidget(self.toggle_btn)

        self.gen_btn = QPushButton("Générer")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.clicked.connect(self.generate_password)
        pass_layout.addWidget(self.gen_btn)

        form.addRow("Service / Plateforme :", self.name_input)
        form.addRow("Identifiant principal :", self.username_input)
        form.addRow("Mot de passe :", pass_layout)
        form.addRow("URL (optionnel) :", self.url_input)
        form.addRow("Catégorie :", self.category_combo)
        form.addRow("Importance :", self.importance_label)
        form.addRow("Tags :", self.tags_input)
        form.addRow("Notes :", self.notes_input)
        
        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Enregistrer")
        self.save_btn.clicked.connect(self.validate_and_accept)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def update_importance_from_category(self, category_name: str):
        """Met à jour le label d'importance en fonction de la catégorie sélectionnée."""
        self._current_importance_level = CATEGORY_TO_IMPORTANCE.get(category_name, 0)
        importance_data = IMPORTANCE_LEVELS.get(self._current_importance_level, {})
        
        self.importance_label.setText(importance_data.get("label", "N/A"))
        self.importance_label.setStyleSheet(f"font-weight: bold; color: {importance_data.get('color', 'white')};")

    def on_url_manually_edited(self):
        """Marque que l'utilisateur a modifié l'URL, désactivant les suggestions."""
        self.user_edited_url = True

    def suggest_url(self, service_name: str):
        """Suggère une URL basée sur le nom du service si l'utilisateur n'a pas déjà modifié le champ URL."""
        if self.user_edited_url:
            return

        suggested_url = SERVICE_TO_URL.get(service_name.lower().strip())
        # Met à jour le champ URL avec la suggestion, ou le vide s'il n'y en a pas
        self.url_input.setText(suggested_url or "")

    def toggle_password(self):
        if self.password_input.echoMode() == QLineEdit.Password:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def generate_password(self):
        pwd = generate_password(length=20)
        self.password_input.setText(pwd)
        self.password_input.setEchoMode(QLineEdit.Normal)

    def validate_and_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Champ manquant", "Le nom du service est obligatoire.")
            return
        if not self.username_input.text().strip():
            QMessageBox.warning(self, "Champ manquant", "L'identifiant principal est obligatoire.")
            return
        if not self.password_input.text():
            QMessageBox.warning(self, "Erreur", "Le mot de passe est obligatoire.")
            return
        self.accept()

    def get_data(self):
        return {
            'name': self.name_input.text().strip(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.text(),
            'url': self.url_input.text().strip(),
            'notes': self.notes_input.toPlainText(),
            'category': self.category_combo.currentText(),
            'importance': self._current_importance_level,
            'tags': self.tags_input.text().strip()
        }