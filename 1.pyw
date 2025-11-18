import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget

class SimpleWindow(QMainWindow):
    """
    This is our main window. It inherits from QMainWindow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple GUI")
        self.counter = 0

        # A central widget is required for a QMainWindow
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create a layout to arrange our widgets vertically
        layout = QVBoxLayout(central_widget)

        # Create a label to display text
        self.label = QLabel("Hello! Click the button.")
        layout.addWidget(self.label)

        # Create a button that the user can click
        button = QPushButton("Click Me!")
        button.clicked.connect(self.on_button_click) # Connect the click event to our method
        layout.addWidget(button)

    def on_button_click(self):
        self.counter += 1
        self.label.setText(f"Button has been clicked {self.counter} times.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())