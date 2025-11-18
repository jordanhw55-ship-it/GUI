import sys
import requests
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QGroupBox
from PySide6.QtCore import Signal, Qt, QObject, QThread
from typing import List
from PySide6.QtGui import QMouseEvent, QColor


DARK_STYLE = """
    /* Nord-inspired Dark Theme */
    QWidget {
        background-color: #1C1C1E;
        color: #F0F0F0;
        font-family: 'Segoe UI';
        font-size: 14px;
    }
    QMainWindow {
        background-color: #1C1C1E;
    }
    #CustomTitleBar {
        background-color: #2A2A2C;
    }
    #CustomTitleBar QLabel {
        background-color: transparent;
        color: #F0F0F0;
        font-size: 16px;
    }
    #CustomTitleBar QPushButton {
        background-color: transparent;
        border: none;
        color: #F0F0F0;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #FFA64D;
    }
    QPushButton {
        background-color: #FF7F50;
        border: 1px solid #444444;
        padding: 5px;
        border-radius: 6px;
    }
    QHeaderView::section {
        background-color: #2A2A2C;
        padding: 4px;
        border: 1px solid #444444;
        color: #F0F0F0;
    }
"""

LIGHT_STYLE = """
    /* Clean Light Theme */
    QWidget {
        background-color: #ECEFF4; /* nord6 */
        color: #2E3440; /* nord0 */
        font-family: 'Segoe UI';
        font-size: 14px;
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
        font-size: 16px;
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
        border-radius: 6px;
    }
"""

class LobbyFetcher(QObject):
    """Worker object to fetch lobby data in a separate thread."""
    finished = Signal(list)
    error = Signal(str)

    def run(self):
        """Fetches lobby data from the API."""
        try:
            response = requests.get("https://api.wc3stats.com/gamelist", timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            data = response.json()
            if data.get("status") == "OK":
                self.finished.emit(data.get("body", []))
            else:
                self.error.emit("API returned an unexpected status.")
        except requests.exceptions.JSONDecodeError:
            self.error.emit("Failed to parse server response.")
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {e}")


class AlignedTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, alignment=Qt.AlignmentFlag.AlignCenter):
        super().__init__(text)
        self.setTextAlignment(alignment)

class SimpleWindow(QMainWindow):
    """
    This is our main window. It inherits from QMainWindow.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hellfire Helper")
        # Make the window frameless to implement a custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(600, 580)
        self.counter = 0
        self.dark_mode = True  # Default to dark mode
        self.old_pos = None
        self.all_lobbies = [] # To store the full list of lobbies from the API
        self.thread = None
        self.watchlist = ["legion", "hellgate"] # Example watchlist

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
        title_bar_layout.setContentsMargins(0, 0, 0, 0) # No margins

        # Left spacer to balance the buttons on the right
        left_spacer = QWidget()
        left_spacer.setFixedSize(60, 30)
        left_spacer.setStyleSheet("background-color: transparent;")

        title_label = QLabel("<span style='color: #FF7F50;'>🔥</span> Hellfire Helper")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        min_button = QPushButton("_")
        min_button.setObjectName("TitleBarButton")
        min_button.setFixedSize(30, 30)
        min_button.clicked.connect(self.showMinimized)

        close_button = QPushButton("X")
        close_button.setObjectName("TitleBarButton")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)

        title_bar_layout.addWidget(left_spacer)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
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

        # --- Search and Refresh Controls ---
        controls_layout = QHBoxLayout()
        self.lobby_search_bar = QLineEdit()
        self.lobby_search_bar.setPlaceholderText("Search by name or map…")
        self.lobby_search_bar.textChanged.connect(self.filter_lobbies)
        controls_layout.addWidget(self.lobby_search_bar)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_lobbies)
        controls_layout.addWidget(refresh_button)

        lobbies_layout.addLayout(controls_layout)

        # --- Watchlist Controls ---
        watchlist_group = QGroupBox("Watchlist")
        watchlist_layout = QHBoxLayout()

        self.watchlist_widget = QListWidget()
        self.watchlist_widget.addItems(self.watchlist)
        watchlist_layout.addWidget(self.watchlist_widget)

        watchlist_controls_layout = QVBoxLayout()
        self.watchlist_input = QLineEdit()
        self.watchlist_input.setPlaceholderText("Add keyword...")
        watchlist_controls_layout.addWidget(self.watchlist_input)

        add_watchlist_button = QPushButton("Add")
        add_watchlist_button.clicked.connect(self.add_to_watchlist)
        watchlist_controls_layout.addWidget(add_watchlist_button)

        remove_watchlist_button = QPushButton("Remove")
        remove_watchlist_button.clicked.connect(self.remove_from_watchlist)
        watchlist_controls_layout.addWidget(remove_watchlist_button)
        watchlist_controls_layout.addStretch()

        watchlist_layout.addLayout(watchlist_controls_layout)
        watchlist_group.setLayout(watchlist_layout)
        lobbies_layout.addWidget(watchlist_group)

        # --- Lobbies Table ---
        self.lobbies_table = QTableWidget()
        self.lobbies_table.setColumnCount(3)
        self.lobbies_table.setHorizontalHeaderLabels(["Name", "Map", "Players"])
        self.lobbies_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Make table read-only
        self.lobbies_table.verticalHeader().setVisible(False) # Hide row numbers
        self.lobbies_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Players column

        lobbies_layout.addWidget(self.lobbies_table)


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
        self.refresh_lobbies() # Initial data load

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
        self.resize(600, 580)
        self.counter = 0
        self.label.setText("Hello! Click the button.")
        self.dark_mode = True
        self.update_theme()
        self.custom_tab_bar._on_button_clicked(0) # Switch to the first tab
        self.watchlist = ["legion", "hellgate"]
        self.watchlist_widget.clear()
        self.watchlist_widget.addItems(self.watchlist)

    def add_to_watchlist(self):
        """Adds a keyword to the watchlist."""
        keyword = self.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.watchlist_widget.addItem(keyword)
            self.watchlist_input.clear()
            self.filter_lobbies(self.lobby_search_bar.text()) # Re-filter to apply new keyword

    def remove_from_watchlist(self):
        """Removes the selected keyword from the watchlist."""
        selected_items = self.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.watchlist_widget.takeItem(self.watchlist_widget.row(item))
        self.filter_lobbies(self.lobby_search_bar.text()) # Re-filter to update highlighting

    def refresh_lobbies(self):
        """Placeholder method to refresh lobby data."""
        self.lobbies_table.setRowCount(0) # Clear table
        self.lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data...")
        loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, loading_item)
        self.lobbies_table.setSpan(0, 0, 1, 3) # Span across all columns

        # Setup and start the worker thread
        self.thread = QThread()
        self.worker = LobbyFetcher()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_lobbies_fetched)
        self.worker.error.connect(self.on_lobbies_fetch_error)
        
        # Clean up the thread when done
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_lobbies_fetched(self, lobbies: list):
        """Slot to handle successfully fetched lobby data."""
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobby_search_bar.text())

    def on_lobbies_fetch_error(self, error_message: str):
        """Slot to handle errors during lobby data fetching."""
        self.lobbies_table.setRowCount(1)
        self.lobbies_table.setSpan(0, 0, 1, 3)
        error_item = QTableWidgetItem(f"Error: {error_message}")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, error_item)

    def filter_lobbies(self, query: str):
        """Filters and displays lobbies based on the search query."""
        self.lobbies_table.setRowCount(0) # Clear table
        self.lobbies_table.setSortingEnabled(False)
        
        query = query.lower()
        filtered_lobbies = [
            lobby for lobby in self.all_lobbies 
            if query in lobby.get('name', '').lower() or query in lobby.get('map', '').lower()
        ]

        self.lobbies_table.setRowCount(len(filtered_lobbies))
        for row, lobby in enumerate(filtered_lobbies):
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            
            # Check for watchlist match
            is_watched = False
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    is_watched = True
                    break

            self.lobbies_table.setItem(row, 0, QTableWidgetItem(lobby.get('name', 'N/A')))
            self.lobbies_table.setItem(row, 1, QTableWidgetItem(lobby.get('map', 'N/A')))
            players = f"{lobby.get('slotsTaken', '?')}/{lobby.get('slotsTotal', '?')}"
            self.lobbies_table.setItem(row, 2, AlignedTableWidgetItem(players))

            if is_watched:
                for col in range(self.lobbies_table.columnCount()):
                    self.lobbies_table.item(row, col).setBackground(QColor("#3A5F0B")) # A dark green color
        self.lobbies_table.setSortingEnabled(True)

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
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #F0F0F0;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #FFA64D;
                }
                QPushButton:pressed {
                    background-color: #FFA64D;
                }
                QPushButton:checked {
                    background-color: #FF7F50;
                    color: #F0F0F0;
                    border-color: #FF7F50;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #F4A3F3; /* This is from a previous request, keeping it for light mode */
                    border: 1px solid #E094DF; /* This is from a previous request, keeping it for light mode */
                    padding: 8px;
                    border-radius: 6px;
                    color: #2E3440; /* nord0 */
                    font-size: 16px;
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