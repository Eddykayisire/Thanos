# main.py
import sys
import os
from PySide6.QtWidgets import QApplication
from thanos_app.gui.login_window import LoginWindow
from thanos_app.gui.styles import theme_manager
from thanos_app.gui.main_window import MainWindow
import config # Import config for APP_DATA_DIR

def main():
    os.makedirs(config.APP_DATA_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    # Apply saved theme at startup
    try:
        theme_manager.apply_theme(getattr(config, 'THEME', 'dark'), app)
    except Exception:
        pass
    login_win = LoginWindow()

    if login_win.exec():
        main_win = MainWindow(login_win.vault)
        main_win.show()
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
