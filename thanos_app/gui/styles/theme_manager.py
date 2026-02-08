import os
from PySide6.QtWidgets import QApplication

BASE_DIR = os.path.dirname(__file__)

def _load_qss(path: str) -> str:
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read()
    return ""

def apply_theme(theme: str, app_or_widget=None):
    """Applique le thème spécifié sur l'application ou le widget donné.
    theme: 'dark' or 'light'
    """
    if app_or_widget is None:
        app_or_widget = QApplication.instance()
    qss = ""
    # Load base styles first
    base_path = os.path.join(BASE_DIR, 'base.qss')
    qss += _load_qss(base_path)

    if theme == 'light':
        qss += _load_qss(os.path.join(BASE_DIR, 'light_theme.qss'))
    else:
        qss += _load_qss(os.path.join(BASE_DIR, 'dark_theme.qss'))

    if app_or_widget:
        app_or_widget.setStyleSheet(qss)
