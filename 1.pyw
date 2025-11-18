import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QTabWidget

DARK_STYLE = """
    QWidget {
        background-color: #2d2d2d;
        color: #d0d0d0;
        font-family: Arial;
        font-size: 12px;
    }
    QMainWindow {
        background-color: #2d2d2d;
    }
    QTabWidget::pane {
        border: 1px solid #444;
    }
    QTabBar::tab {
        background: #2d2d2d;
        border: 1px solid #444;
        padding: 8px 20px;
    }
    QTabBar::tab:selected {
        background: #4a4a4a;
        border-bottom-color: #4a4a4a; /* Same as background */
    }
    QPushButton {
        background-color: #4a4a4a;
        border: 1px solid #555;
        padding: 8px;
        border-radius: 4px;
    }
    QPushButton:hover {
        background-color: #5a5a5a;
    }
    QPushButton:pressed {
        background-color: #3a3a3a;
    }
"""

LIGHT_STYLE = """
    QWidget {
        background-color: #f0f0f0;
        color: #000000;
        font-family: Arial;
        font-size: 12px;
    }
    QMainWindow {
        background-color: #f0f0f0;
    }
    QTabWidget::pane {
        border: 1px solid #c5c5c5;
    }
    QTabBar::tab {
        background: #f0f0f0;
        border: 1px solid #c5c5c5;
        padding: 8px 20px;
    }
    QTabBar::tab:selected {
        background: #dcdcdc;
        border-bottom-color: #dcdcdc;
    }
    QPushButton {
        padding: 8px;
        border-radius: 4px;
    }
"""

class SimpleWindow(QMainWindow):
    """
    This is our main window. It inherits from QMainWindow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple GUI with Tabs")
        self.resize(600, 400)  # Set the initial size of the window
        self.counter = 0
        self.dark_mode = False

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

        # --- Create the "Settings" tab ---
        settings_tab = QWidget()
        tabs.addTab(settings_tab, "Settings")
        settings_layout = QVBoxLayout(settings_tab)

        # Add a theme toggle button
        theme_button = QPushButton("Toggle Dark Mode")
        theme_button.clicked.connect(self.toggle_theme)
        settings_layout.addWidget(theme_button)
        settings_layout.addStretch() # Pushes the content to the top

        # Apply the initial theme
        self.setStyleSheet(LIGHT_STYLE)

    def on_button_click(self):
        self.counter += 1
        self.label.setText(f"Button has been clicked {self.counter} times.")

    def toggle_theme(self):
        """Toggles between light and dark mode."""
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.setStyleSheet(DARK_STYLE)
        else:
            self.setStyleSheet(LIGHT_STYLE) # Revert to a consistent light style

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())