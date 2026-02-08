from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, 
                               QPushButton, QLabel, QMessageBox, QDialogButtonBox, QWidget, QFrame)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import json
from datetime import datetime, timedelta
from .styles.dark_theme import apply_dark_theme

class SecurityLogDialog(QDialog):
    def __init__(self, security_manager, parent=None):
        super().__init__(parent)
        self.security_manager = security_manager
        self.setWindowTitle("Journal de Sécurité")
        self.setMinimumSize(1000, 700)
        self.setup_ui()
        self.load_logs()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget { background-color: #0d1117; border: none; } QListWidget::item { background: transparent; }")
        self.list_widget.setSpacing(10)
        layout.addWidget(self.list_widget)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)

    def load_logs(self):
        self.list_widget.clear()
        logs = self.security_manager.get_decrypted_logs()
        
        if not logs:
            item = QListWidgetItem(self.list_widget)
            lbl = QLabel("Aucun événement de sécurité enregistré.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #8b949e; padding: 20px; font-style: italic;")
            item.setSizeHint(lbl.sizeHint())
            self.list_widget.setItemWidget(item, lbl)
            return
        
        for log in logs:
            # Create Item
            item = QListWidgetItem(self.list_widget)
            
            # Create Widget for Item
            widget = QFrame()
            widget.setObjectName("LogCard")
            widget.setStyleSheet("""
                #LogCard {
                    background-color: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 8px;
                }
            """)
            
            h_layout = QHBoxLayout(widget)
            h_layout.setContentsMargins(15, 15, 15, 15)
            
            # Left: Info
            v_info = QVBoxLayout()
            
            # Format date
            ts_str = log.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts_str)
                display_date = dt.strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                display_date = ts_str
            
            lbl_date = QLabel(f"🕒 {display_date}")
            lbl_date.setStyleSheet("color: #8b949e; font-size: 9pt;")
            
            lbl_type = QLabel(log.get("event_type", "UNKNOWN"))
            lbl_type.setStyleSheet("font-weight: bold; font-size: 11pt; color: #58a6ff;")
            
            details = log.get("details", {})
            try:
                details_str = json.dumps(details, indent=2, ensure_ascii=False)
            except:
                details_str = str(details)
            
            lbl_details = QLabel(details_str)
            lbl_details.setWordWrap(True)
            lbl_details.setStyleSheet("color: #c9d1d9; font-family: Consolas; margin-top: 5px;")
            
            v_info.addWidget(lbl_type)
            v_info.addWidget(lbl_date)
            
            h_layout.addLayout(v_info, stretch=1)
            
            # Middle: Image Preview (if any)
            if log.get("event_type") == "PHOTO_CAPTURE" and details.get("status") == "success":
                filename = details.get("filename")
                try:
                    image_data = self.security_manager.get_decrypted_photo(filename)
                    img = QImage.fromData(image_data)
                    if not img.isNull():
                        pix = QPixmap.fromImage(img).scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        lbl_img = QLabel()
                        lbl_img.setPixmap(pix)
                        lbl_img.setStyleSheet("border: 1px solid #30363d; border-radius: 4px;")
                        h_layout.addWidget(lbl_img)
                        
                        # Click to enlarge
                        btn_view = QPushButton("🔍")
                        btn_view.clicked.connect(lambda c, f=filename: self.view_photo(f))
                        h_layout.addWidget(btn_view)
                except Exception:
                    pass

            # Right: Delete Action
            del_btn = QPushButton("🗑️")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedSize(40, 40)
            del_btn.setStyleSheet("background-color: #2b1414; color: #ff7b72; border: 1px solid #da3633; border-radius: 20px;")
            del_btn.clicked.connect(lambda checked, lid=log.get("id"), ts=log.get("timestamp"): self.try_delete_log(lid, ts))
            
            h_layout.addWidget(del_btn)

            item.setSizeHint(widget.sizeHint())
            self.list_widget.setItemWidget(item, widget)

    def try_delete_log(self, log_id, timestamp_str):
        reply = QMessageBox.question(self, "Confirmer suppression", 
                                   "Voulez-vous vraiment supprimer cet événement de sécurité ?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Accès direct à la DB via le manager pour garantir la suppression
            self.security_manager.db.delete_log(log_id)
            self.load_logs()

    def view_photo(self, filename):
        try:
            image_data = self.security_manager.get_decrypted_photo(filename)
            image = QImage.fromData(image_data)
            if image.isNull():
                QMessageBox.warning(self, "Erreur", "Impossible de décoder l'image.")
                return
            
            viewer = QDialog(self)
            viewer.setWindowTitle(f"Preuve - {filename}")
            viewer.setMinimumSize(600, 400)
            apply_dark_theme(viewer)
            
            v_layout = QVBoxLayout(viewer)
            lbl = QLabel()
            lbl.setPixmap(QPixmap.fromImage(image))
            lbl.setScaledContents(True)
            lbl.setAlignment(Qt.AlignCenter)
            v_layout.addWidget(lbl)
            
            viewer.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement de la photo: {e}")