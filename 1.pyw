import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QTabWidget

class SimpleWindow(QMainWindow):
    """
    This is our main window. It inherits from QMainWindow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple GUI with Tabs")
        self.resize(600, 400)  # Set the initial size of the window
        self.counter = 0

        # Create a QTabWidget to hold our tabs
        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        # --- Create the "Load" tab ---
        load_tab = QWidget()
        tabs.addTab(load_tab, "Load")
        load_layout = QVBoxLayout(load_tab)
        load_layout.addWidget(QLabel("This is the 'Load' tab."))
        load_layout.addStretch() # Pushes the content to the top

        # --- Create the "Items" tab ---
        items_tab = QWidget()
        tabs.addTab(items_tab, "Items")
        items_layout = QVBoxLayout(items_tab)

        # Create a label to display text
        self.label = QLabel("Hello! Click the button.")
        items_layout.addWidget(self.label)

        # Create a button that the user can click
        button = QPushButton("Click Me!")
        button.clicked.connect(self.on_button_click) # Connect the click event to our method
        items_layout.addWidget(button)

    def on_button_click(self):
        self.counter += 1
        self.label.setText(f"Button has been clicked {self.counter} times.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())