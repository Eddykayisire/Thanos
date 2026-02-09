# main.py
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from thanos_app.gui.login_window import LoginWindow
from thanos_app.gui.styles import theme_manager
from thanos_app.gui.main_window import MainWindow
import config # Import config for APP_DATA_DIR

def main():
    # Fix pour l'icône dans la barre des tâches Windows
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("thanos.app.1")

    os.makedirs(config.APP_DATA_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    # Apply saved theme at startup
    try:
        theme_manager.apply_theme(getattr(config, 'THEME', 'dark'), app)
    except Exception:
        pass

    # Configuration de l'icône globale
    icon_path = os.path.join(os.path.dirname(__file__), "thanos_app", "gui", "styles", "icons", "logo_icon.svg")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    login_win = LoginWindow()

    if login_win.exec():
        main_win = MainWindow(login_win.vault)
        main_win.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
