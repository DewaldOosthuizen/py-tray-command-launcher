import sys
from PyQt6.QtWidgets import QApplication
from core.tray_app import TrayApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tray_app = TrayApp(app)
    tray_app.run()
