import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout
from PySide6.QtCore import Signal, Qt
from typing import List
from PySide6.QtGui import QMouseEvent

DARK_STYLE = """
    /* Nord-inspired Dark Theme */
    QWidget {
        background-color: #1B1B1B;
        color: #ECEFF4; /* nord6 */
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12px;
    }
    QMainWindow {
        background-color: #1B1B1B;
    }
    #CustomTitleBar {
        background-color: #3B4252; /* nord1 */
    }
    #CustomTitleBar QLabel {
        background-color: transparent;
        color: #ECEFF4;
    }
    #CustomTitleBar QPushButton {
        background-color: transparent;
        border: none;
        color: #ECEFF4;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #4C566A; /* nord3 */
    }
    QPushButton {
        background-color: #434C5E; /* nord3 */
        border: 1px solid #4C566A;
        padding: 5px;
        border-radius: 4px;
    }
"""

LIGHT_STYLE = """
    /* Clean Light Theme */
    QWidget {
        background-color: #ECEFF4; /* nord6 */
        color: #2E3440; /* nord0 */
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 12px;
    }
    QMainWindow {
        background-color: #ECEFF4;
    }
    #CustomTitleBar {
        background-color: #C11C84;
    }
    #CustomTitleBar QLabel {
        background-color: transparent;
        color: #2E3440;
    }
    #CustomTitleBar QPushButton {
        background-color: transparent;
        border: none;
        color: #2E3440;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #E5E9F0; /* nord6, slightly lighter */
    }
    QPushButton {
        background-color: #D8DEE9; /* nord5 */
        border: 1px solid #C5C9D1;
        padding: 5px;
        border-radius: 4px;
    }
"""

class SimpleWindow(QMainWindow):
    """
    This is our main window. It inherits from QMainWindow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hellfire Helper")
        # Make the window frameless to implement a custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(600, 450)
        self.counter = 0
        self.dark_mode = True  # Default to dark mode
        self.old_pos = None

        # Main layout for the window
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(5)
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # --- Create Custom Title Bar ---
        self.title_bar = QWidget()
        self.title_bar.setObjectName("CustomTitleBar")
        self.title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(10, 0, 0, 0)

        title_label = QLabel("Hellfire Helper")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        min_button = QPushButton("_")
        min_button.setObjectName("TitleBarButton")
        min_button.setFixedSize(30, 30)
        min_button.clicked.connect(self.showMinimized)

        close_button = QPushButton("X")
        close_button.setObjectName("TitleBarButton")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)

        title_bar_layout.addWidget(min_button)
        title_bar_layout.addWidget(close_button)
        main_layout.addWidget(self.title_bar)

        # Create a custom tab bar
        self.tab_names = ["Load", "Items", "Recipes", "Automation", "Hotkey", "Lobbies", "Settings", "Reset"]
        self.custom_tab_bar = CustomTabBar(self.tab_names, tabs_per_row=4)
        main_layout.addWidget(self.custom_tab_bar)

        # Create a QStackedWidget to hold our tab contents
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Connect the custom tab bar to the stacked widget
        self.custom_tab_bar.tab_selected.connect(self.stacked_widget.setCurrentIndex)

        # --- Create the "Load" tab ---
        load_tab_content = QWidget()
        load_layout = QVBoxLayout(load_tab_content)
        load_layout.addWidget(QLabel("This is the 'Load' tab."))
        load_layout.addStretch() # Pushes the content to the top
        self.stacked_widget.addWidget(load_tab_content)

        # --- Create the "Items" tab ---
        items_tab_content = QWidget()
        items_layout = QVBoxLayout(items_tab_content)
        self.label = QLabel("Hello! Click the button.")
        items_layout.addWidget(self.label)
        button = QPushButton("Click Me!")
        button.clicked.connect(self.on_button_click) # Connect the click event to our method
        items_layout.addWidget(button)
        self.stacked_widget.addWidget(items_tab_content)

        # --- Create the "Recipes" tab ---
        recipes_tab_content = QWidget()
        recipes_layout = QVBoxLayout(recipes_tab_content)
        recipes_layout.addWidget(QLabel("This is the 'Recipes' tab."))
        recipes_layout.addStretch()
        self.stacked_widget.addWidget(recipes_tab_content)

        # --- Create the "Automation" tab ---
        automation_tab_content = QWidget()
        automation_layout = QVBoxLayout(automation_tab_content)
        automation_layout.addWidget(QLabel("This is the 'Automation' tab."))
        automation_layout.addStretch()
        self.stacked_widget.addWidget(automation_tab_content)

        # --- Create the "Hotkey" tab ---
        hotkey_tab_content = QWidget()
        hotkey_layout = QVBoxLayout(hotkey_tab_content)
        hotkey_layout.addWidget(QLabel("This is the 'Hotkey' tab."))
        hotkey_layout.addStretch()
        self.stacked_widget.addWidget(hotkey_tab_content)

        # --- Create the "Lobbies" tab ---
        lobbies_tab_content = QWidget()
        lobbies_layout = QVBoxLayout(lobbies_tab_content)
        lobbies_layout.addWidget(QLabel("This is the 'Lobbies' tab."))
        lobbies_layout.addStretch()
        self.stacked_widget.addWidget(lobbies_tab_content)

        # --- Create the "Settings" tab ---
        settings_tab_content = QWidget()
        settings_layout = QVBoxLayout(settings_tab_content)
        self.theme_button = QPushButton()
        self.theme_button.clicked.connect(self.toggle_theme)
        settings_layout.addWidget(self.theme_button)
        settings_layout.addStretch() # Pushes the content to the top
        self.stacked_widget.addWidget(settings_tab_content)

        # --- Create the "Reset" tab ---
        reset_tab_content = QWidget()
        self.reset_layout = QVBoxLayout(reset_tab_content)
        
        warning_text = QLabel("This will reset the GUI to its default state.\nAre you sure you want to continue?")
        warning_text.setStyleSheet("font-weight: bold;")
        self.reset_layout.addWidget(warning_text, 0, Qt.AlignmentFlag.AlignCenter)

        reset_button = QPushButton("Reset GUI")
        reset_button.clicked.connect(self.confirm_reset)
        self.reset_layout.addWidget(reset_button, 0, Qt.AlignmentFlag.AlignCenter)

        self.reset_layout.addStretch()
        self.stacked_widget.addWidget(reset_tab_content)

        # Apply the initial theme and set button text
        self.update_theme()

    def mousePressEvent(self, event: QMouseEvent):
        """Captures the initial mouse position for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.underMouse():
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Moves the window if the mouse is being dragged from the title bar."""
        if self.old_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Resets the drag position when the mouse is released."""
        self.old_pos = None

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

    def confirm_reset(self):
        """Shows a confirmation dialog before resetting the application state."""
        confirm_box = QMessageBox(self)
        confirm_box.setWindowTitle("Confirm Reset")
        confirm_box.setText("Are you sure you want to reset the application?\nAll settings will be returned to their defaults.")
        confirm_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        if confirm_box.exec() == QMessageBox.StandardButton.Yes:
            self.reset_state()

    def reset_state(self):
        """Resets the application to its initial state."""
        self.resize(600, 450)
        self.counter = 0
        self.label.setText("Hello! Click the button.")
        self.dark_mode = True
        self.update_theme()
        self.custom_tab_bar._on_button_clicked(0) # Switch to the first tab


class CustomTabBar(QWidget):
    """
    A custom widget to act as a tab bar, allowing for multi-row tab buttons.
    """
    tab_selected = Signal(int)

    def __init__(self, tab_names: list[str], tabs_per_row: int = 4):
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
                QPushButton { /* Tab buttons */
                    background-color: #F4A3F3;
                    border: 1px solid #E094DF;
                    padding: 8px;
                    border-radius: 4px;
                    color: #2E3440; /* nord0 */
                }
                QPushButton:hover {
                    background-color: #F6B3F5;
                }
                QPushButton:pressed {
                    background-color: #E094DF;
                }
                QPushButton:checked {
                    background-color: #D685D4; /* Darker accent for selection */
                    color: #2E3440;
                    border-color: #D685D4;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #F4A3F3;
                    border: 1px solid #E094DF;
                    padding: 8px;
                    border-radius: 4px;
                    color: #2E3440; /* nord0 */
                }
                QPushButton:hover {
                    background-color: #F6B3F5;
                }
                QPushButton:pressed {
                    background-color: #E094DF;
                }
                QPushButton:checked {
                    background-color: #D685D4; /* Darker accent for selection */
                    color: #2E3440;
                    border-color: #D685D4;
                }
            """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())