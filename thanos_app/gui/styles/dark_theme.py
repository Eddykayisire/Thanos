# thanos_app/gui/styles/dark_theme.py
import os
from PySide6.QtWidgets import QApplication

def apply_dark_theme(app_or_widget):
    style_path = os.path.join(os.path.dirname(__file__), "dark_theme.qss")
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            style = f.read()
        app_or_widget.setStyleSheet(style)
