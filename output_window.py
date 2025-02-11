from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QTextEdit, QWidget
from PyQt6.QtCore import Qt

class OutputWindow(QMainWindow):
    def __init__(self, title, output, parent=None):
        super().__init__(parent)  # Explicitly set parent to keep app alive
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 600, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)  # Ensure only this window closes

        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(output)
        layout.addWidget(text_edit)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)