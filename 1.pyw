import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QStackedWidget, QGridLayout
from PySide6.QtCore import Signal
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
"""

class SimpleWindow(QMainWindow):
    """
    This is our main window. It inherits from QMainWindow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple GUI with Tabs")
        self.resize(0, 400)  # Set the initial size of the window
        self.counter = 0
        self.dark_mode = True  # Default to dark mode

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

        # --- Create the "Recipes" tab ---
        recipes_tab = QWidget()
        tabs.addTab(recipes_tab, "Recipes")
        recipes_layout = QVBoxLayout(recipes_tab)
        recipes_layout.addWidget(QLabel("This is the 'Recipes' tab."))
        recipes_layout.addStretch()

        # --- Create the "Automation" tab ---
        automation_tab = QWidget()
        tabs.addTab(automation_tab, "Automation")
        automation_layout = QVBoxLayout(automation_tab)
        automation_layout.addWidget(QLabel("This is the 'Automation' tab."))
        automation_layout.addStretch()

        # --- Create the "Hotkey" tab ---
        hotkey_tab = QWidget()
        tabs.addTab(hotkey_tab, "Hotkey")
        hotkey_layout = QVBoxLayout(hotkey_tab)
        hotkey_layout.addWidget(QLabel("This is the 'Hotkey' tab."))
        hotkey_layout.addStretch()

        # --- Create the "Lobbies" tab ---
        lobbies_tab = QWidget()
        tabs.addTab(lobbies_tab, "Lobbies")
        lobbies_layout = QVBoxLayout(lobbies_tab)
        lobbies_layout.addWidget(QLabel("This is the 'Lobbies' tab."))
        lobbies_layout.addStretch()

        # --- Create the "Settings" tab ---
        settings_tab = QWidget()
        tabs.addTab(settings_tab, "Settings")
        settings_layout = QVBoxLayout(settings_tab)

        # Add a theme toggle button
        self.theme_button = QPushButton()
        self.theme_button.clicked.connect(self.toggle_theme)
        settings_layout.addWidget(self.theme_button)
        settings_layout.addStretch() # Pushes the content to the top

        # --- Create the "Reset" tab ---
        reset_tab = QWidget()
        tabs.addTab(reset_tab, "Reset")
        reset_layout = QVBoxLayout(reset_tab)
        reset_layout.addWidget(QLabel("This is the 'Reset' tab."))
        reset_layout.addStretch()

        # Apply the initial theme and set button text
        self.update_theme()

    def on_button_click(self):
        self.counter += 1
        self.label.setText(f"Button has been clicked {self.counter} times.")

    def toggle_theme(self):
        """Flips the theme state and updates the UI."""
        self.dark_mode = not self.dark_mode
        self.update_theme()

    def update_theme(self):
        """Applies the current theme and updates the toggle button text."""
        # Apply global stylesheet for general widgets and buttons (like theme_button)
        if self.dark_mode:
            self.setStyleSheet(DARK_STYLE)
            self.theme_button.setText("Toggle Light Mode")
        else:
            self.setStyleSheet(LIGHT_STYLE)
            self.theme_button.setText("Toggle Dark Mode")
        # Apply theme to custom tab bar buttons
        self.custom_tab_bar.apply_style(self.dark_mode)


class CustomTabBar(QWidget):
    """
    A custom widget to act as a tab bar, allowing for multi-row tab buttons.
    """
    tab_selected = Signal(int)

    def __init__(self, tab_names: List[str], tabs_per_row: int = 4):
        super().__init__()
        self.tab_names = tab_names
        self.tabs_per_row = tabs_per_row
        self.buttons: List[QPushButton] = []
        self.current_index = -1

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2) # Small spacing between buttons

        self._create_buttons()

    def _create_buttons(self):
        for i, name in enumerate(self.tab_names):
            button = QPushButton(name)
            button.setCheckable(True) # Make buttons toggleable
            button.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            self.buttons.append(button)

            row = i // self.tabs_per_row
            col = i % self.tabs_per_row
            self.layout.addWidget(button, row, col)

        # Set initial selection
        if self.buttons:
            self._on_button_clicked(0) # Select the first tab by default

    def _on_button_clicked(self, index: int):
        if self.current_index != index:
            if self.current_index != -1:
                self.buttons[self.current_index].setChecked(False)
            self.buttons[index].setChecked(True)
            self.current_index = index
            self.tab_selected.emit(index)

    def apply_style(self, dark_mode: bool):
        # This method applies specific styling for the buttons within this custom tab bar,
        # including the :checked state, overriding general QPushButton styles if necessary.
        if dark_mode:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4a4a4a;
                    border: 1px solid #555;
                    padding: 8px;
                    border-radius: 4px;
                    color: #d0d0d0;
                }
                QPushButton:hover {
                    background-color: #5a5a5a;
                }
                QPushButton:pressed {
                    background-color: #3a3a3a;
                }
                QPushButton:checked {
                    background-color: #6a6a6a; /* Darker background for selected tab */
                    border-color: #777;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #c5c5c5;
                    padding: 8px;
                    border-radius: 4px;
                    color: #000000;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
                QPushButton:pressed {
                    background-color: #d0d0d0;
                }
                QPushButton:checked {
                    background-color: #cccccc; /* Darker background for selected tab */
                    border-color: #b0b0b0;
                }
            """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())