from PySide6.QtWidgets import QApplication
import sys
from thanos_app.gui.modern_main import ModernMainWindow

def main():
    # Run ModernMainWindow
    app = QApplication(sys.argv)
    w = ModernMainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
