from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QTextEdit, QWidget
from PyQt6.QtCore import Qt

class OutputWindow(QMainWindow):
    def __init__(self, title, output, parent=None):
        super().__init__(parent)  # Explicitly set parent to keep app alive
        self.setWindowTitle(title)
        # Set the window geometry 100px from the top-left corner, with a size of 800x600
        self.setGeometry(100, 100, 800, 600)
        # Ensure the window is deleted when closed
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Create a layout and add a read-only text edit widget
        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(output)
        layout.addWidget(text_edit)

        # Create a container widget to hold the layout
        container = QWidget()
        container.setLayout(layout)
        
        # Set the central widget of the window
        self.setCentralWidget(container)