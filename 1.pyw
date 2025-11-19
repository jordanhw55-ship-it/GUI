import sys
import requests
import json
import os
import re
from datetime import datetime
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget, QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog, QTextEdit, QListWidgetItem, QMenu
from PySide6.QtCore import Signal, Qt, QObject, QThread, QTimer
from typing import List
from PySide6.QtGui import QMouseEvent, QColor
import keyboard
import pyautogui # type: ignore
import win32gui # type: ignore


DARK_STYLE = """ 
    /* Black/Orange Theme */
    QWidget {
        background-color: #121212;
        color: #F0F0F0;
        font-family: 'Segoe UI';
        font-size: 14px;
        outline: none; /* Remove focus outline */
    }
    QMainWindow {
        background-color: #1F1F1F;
    }
    #CustomTitleBar {
        background-color: #1F1F1F;
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
        font-size: 16px;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #FFA64D;
    }
    QPushButton {
        background-color: #FF7F50; /* Coral */
        border: 1px solid #444444;
        padding: 5px;
        border-radius: 6px;
        color: #000000; /* Black text for better contrast on orange */
    }
    QHeaderView::section {
        background-color: #1F1F1F;
        padding: 4px;
        border: 1px solid #444444;
        color: #F0F0F0;
    }
"""

LIGHT_STYLE = """
    /* White/Pink Theme */
    QWidget {
        background-color: #FFFFFF; /* White */
        color: #000000; /* Black */
        font-family: 'Segoe UI';
        font-size: 14px;
        outline: none;
    }
    QMainWindow {
        background-color: #ECEFF4;
    }
    #CustomTitleBar {
        background-color: #FFFFFF;
    }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton {
        background-color: transparent;
        color: #000000;
        border: none;
        font-size: 16px;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #DA3A9D;
    }
    QPushButton {
        background-color: #FFC0CB; /* Pink */
        border: 1px solid #E6A8B8;
        padding: 5px;
        border-radius: 6px;
        color: #000000;
    }
    QHeaderView::section {
        background-color: #FFC0CB;
        border: 1px solid #E6A8B8;
        color: #000000;
    }
"""

FOREST_STYLE = """
    /* Black/Blue Theme */
    QWidget {
        background-color: #121212; /* Very dark grey */
        color: #EAEAEA;
        font-family: 'Segoe UI';
        font-size: 14px;
        outline: none;
    }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton {
        color: #EAEAEA;
        background-color: transparent;
        border: none;
        font-size: 16px;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #4682B4; /* SteelBlue */
    }
    QPushButton {
        background-color: #1E90FF; /* DodgerBlue */
        border: 1px solid #4169E1; /* RoyalBlue */
        padding: 5px;
        border-radius: 6px;
    }
    QHeaderView::section { background-color: #1F1F1F; border: 1px solid #4169E1; }
"""

OCEAN_STYLE = """
    /* White/Blue Theme */
    QWidget {
        background-color: #F0F8FF; /* AliceBlue */
        color: #000080; /* Navy */
        font-family: 'Segoe UI';
        font-size: 14px;
        outline: none;
    }
    QMainWindow { background-color: #F0F8FF; }
    #CustomTitleBar { background-color: #F0F8FF; } /* AliceBlue */
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton {
        color: #000080; /* Navy */
        background-color: transparent;
        border: none;
        font-size: 16px;
    }
    #CustomTitleBar QPushButton:hover {
        background-color: #87CEFA; /* LightSkyBlue */
    }
    QPushButton {
        background-color: #87CEEB; /* SkyBlue */
        border: 1px solid #4682B4; /* SteelBlue */
        padding: 5px;
        border-radius: 6px;
    }
    QHeaderView::section { background-color: #ADD8E6; border: 1px solid #87CEEB; }
"""


class ItemDatabase:
    """Handles loading and searching item data from text files."""
    def __init__(self):
        self.base_path = os.path.join(os.path.dirname(__file__), "contents")
        self.all_items_data = []
        self.drops_data = []
        self.raid_data = []
        self.vendor_data = []
        self.recipes_data = []

    def _clean_item(self, raw_line: str) -> dict:
        """Parses a raw line of text into an item object."""
        line = raw_line.strip()
        if not line:
            return {}
        
        # Regex patterns to match item lines
        patterns = [
            r"^\s*\[([^\]]+)\]\s*(.+?)\s*[:\-]\s*([\d\.]+)%\s*$",  # [Tag] Name : X%
            r"^\s*\[([^\]]+)\]\s*(.+)$",                          # [Tag] Name
            r"^\s*(.+?)\s*[:\-]\s*([\d\.]+)%\s*$",                  # Name : X%
        ]

        for i, pattern in enumerate(patterns):
            match = re.match(pattern, line)
            if match:
                if i == 0: return {"type": match.group(1), "name": match.group(2).strip(), "rate": f"{match.group(3)}%"}
                if i == 1: return {"type": match.group(1), "name": match.group(2).strip(), "rate": ""}
                if i == 2: return {"name": match.group(1).strip(), "rate": f"{match.group(2)}%"}
        
        return {"name": line, "rate": ""} # Fallback

    def _load_item_data_from_folder(self, folder: str) -> list:
        """Loads all item data from a specific subfolder."""
        data = []
        folder_path = os.path.join(self.base_path, folder)
        if not os.path.isdir(folder_path):
            return []

        for filename in os.listdir(folder_path):
            if not filename.endswith(".txt"):
                continue
            
            file_path = os.path.join(folder_path, filename)
            zone = os.path.splitext(filename)[0]
            unit = "?"

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        zone_match = re.match(r"^Zone:\s*(.+)", line)
                        unit_match = re.match(r"^\[Unit\]\s*(.+)", line)

                        if zone_match:
                            zone = zone_match.group(1).strip()
                        elif unit_match:
                            unit = unit_match.group(1).strip()
                        else:
                            item_obj = self._clean_item(line)
                            if item_obj.get("name"):
                                data.append({
                                    "Item": item_obj["name"],
                                    "Drop%": item_obj.get("rate", ""),
                                    "Unit": unit,
                                    "Location": zone
                                })
            except (IOError, OSError):
                continue # Skip files that can't be read
        return data

    def load_recipes(self):
        """Loads recipe data from contents/Recipes.txt."""
        if self.recipes_data: # Already loaded
            return

        file_path = os.path.join(self.base_path, "Recipes.txt")
        if not os.path.exists(file_path):
            return

        self.recipes_data = []
        current_recipe_name = ""
        current_components = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()

                    if not line: # Blank line is a separator
                        if current_recipe_name:
                            self.recipes_data.append({"name": current_recipe_name, "components": current_components})
                            current_recipe_name = ""
                            current_components = []
                        continue

                    material_match = re.match(r"^\s*Material\s*:\s*(.+)", line, re.IGNORECASE)
                    if material_match:
                        if current_recipe_name:
                            current_components.append(material_match.group(1).strip())
                    else: # It's a recipe name
                        if current_recipe_name: # A new recipe starts without a blank line separator
                            self.recipes_data.append({"name": current_recipe_name, "components": current_components})
                        
                        current_recipe_name = line
                        current_components = []

            # Add the last recipe if the file doesn't end with a blank line
            if current_recipe_name:
                self.recipes_data.append({"name": current_recipe_name, "components": current_components})

        except (IOError, OSError):
            print(f"Could not read {file_path}")


class ThemePreview(QWidget):
    """A clickable widget to preview and select a theme."""
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

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

class HotkeyCaptureWorker(QObject):
    """Worker to capture a hotkey in a separate thread to avoid freezing the GUI."""
    hotkey_captured = Signal(str)

    def run(self):
        """Waits for and reads a single hotkey press."""
        try:
            # read_hotkey blocks until a key is pressed
            hotkey = keyboard.read_hotkey(suppress=True)
            self.hotkey_captured.emit(hotkey)
        except Exception as e:
            print(f"Error capturing hotkey: {e}")

class AutomationWorker(QObject):
    """Worker to perform automation tasks in a separate thread."""
    finished = Signal()
    error = Signal(str)

    def __init__(self, game_title: str, action: str, message: str = ""):
        super().__init__()
        self.game_title = game_title
        self.action = action
        self.message = message

    def run(self):
        """Finds the game window and performs the action."""
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                # Don't emit an error for every single timer tick
                print(f"'{self.game_title}' window not found.")
                return

            pyautogui.press('enter')
            pyautogui.write(self.message if self.action == "chat" else self.action, interval=0.05)
            pyautogui.press('enter')
        finally:
            self.finished.emit()

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
        self.resize(700, 800)
        self.current_theme_index = 0
        self.old_pos = None
        self.all_lobbies = [] # To store the full list of lobbies from the API
        self.thread = None
        self.watchlist_file = "watchlist.json"
        self.watchlist = self.load_watchlist()
        self.character_path = ""
        self.previous_watched_lobbies = set()
        self.theme_previews = []
        self.message_hotkeys = {}
        self.game_title = "Warcraft III" # Configurable game window title

        self.themes = [
            {
                "name": "Black/Orange", "style": DARK_STYLE,
                "preview_color": "#FF7F50", "is_dark": True
            },
            {
                "name": "White/Pink", "style": LIGHT_STYLE,
                "preview_color": "#FFC0CB", "is_dark": False
            },
            {
                "name": "Black/Blue", "style": FOREST_STYLE,
                "preview_color": "#1E90FF", "is_dark": True
            },
            {
                "name": "White/Blue", "style": OCEAN_STYLE,
                "preview_color": "#87CEEB", "is_dark": False
            }
        ]

        # Load saved theme or default to the first one
        self.load_settings()


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

        # Path controls
        path_layout = QHBoxLayout()
        self.load_path_edit = QLineEdit()
        self.load_path_edit.setPlaceholderText("Character save path...")
        self.load_path_edit.textChanged.connect(self.on_path_changed)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.select_character_path)
        reset_path_btn = QPushButton("Reset Path")
        reset_path_btn.clicked.connect(self.reset_character_path)
        path_layout.addWidget(self.load_path_edit)
        path_layout.addWidget(browse_btn)
        path_layout.addWidget(reset_path_btn)
        load_layout.addLayout(path_layout)

        # Action buttons
        action_layout = QHBoxLayout()
        load_char_btn = QPushButton("Load Character (F3)")
        load_char_btn.clicked.connect(self.load_selected_character)
        refresh_chars_btn = QPushButton("Refresh")
        refresh_chars_btn.clicked.connect(self.load_characters)
        action_layout.addWidget(load_char_btn)
        action_layout.addWidget(refresh_chars_btn)
        action_layout.addStretch()
        load_layout.addLayout(action_layout)

        # Character list and content view
        content_layout = QHBoxLayout()
        self.char_list_box = QListWidget()
        self.char_list_box.setFixedWidth(200)
        self.char_list_box.currentItemChanged.connect(self.show_character_file_contents)
        
        self.char_content_box = QTextEdit()
        self.char_content_box.setReadOnly(True)
        self.char_content_box.setFontFamily("Consolas")
        self.char_content_box.setFontPointSize(10)

        content_layout.addWidget(self.char_list_box)
        content_layout.addWidget(self.char_content_box)
        load_layout.addLayout(content_layout)

        # Set initial path and load characters
        self.load_path_edit.setText(self.character_path)
        self.load_characters()
        self.stacked_widget.addWidget(load_tab_content)

        # --- Create the "Items" tab ---
        self.item_database = ItemDatabase()
        items_tab_content = QWidget()
        items_main_layout = QVBoxLayout(items_tab_content)

        # Sub-tab and search layout
        items_controls_layout = QHBoxLayout()
        self.items_sub_tabs = QWidget()
        self.items_sub_tabs_layout = QHBoxLayout(self.items_sub_tabs)
        self.items_sub_tabs_layout.setContentsMargins(0,0,0,0)
        self.items_sub_tabs_layout.setSpacing(5)
        
        self.item_tab_buttons = {}
        item_tab_names = ["All Items", "Drops", "Raid Items", "Vendor Items"]
        for i, name in enumerate(item_tab_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self.switch_items_sub_tab(idx))
            self.item_tab_buttons[i] = btn
            self.items_sub_tabs_layout.addWidget(btn)

        self.items_search_box = QLineEdit()
        self.items_search_box.setPlaceholderText("Search...")
        self.items_search_box.textChanged.connect(self.filter_current_item_view)

        items_controls_layout.addWidget(self.items_sub_tabs)
        items_controls_layout.addStretch()
        items_controls_layout.addWidget(self.items_search_box)
        items_main_layout.addLayout(items_controls_layout)

        # Stacked widget for item tables
        self.items_stacked_widget = QStackedWidget()
        items_main_layout.addWidget(self.items_stacked_widget)

        # Create the tables
        self.all_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.drops_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.raid_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.vendor_table = self._create_item_table(["Item", "Unit", "Location"])

        self.items_stacked_widget.addWidget(self.all_items_table)
        self.items_stacked_widget.addWidget(self.drops_table)
        self.items_stacked_widget.addWidget(self.raid_items_table)
        self.items_stacked_widget.addWidget(self.vendor_table)

        self.switch_items_sub_tab(0) # Select "All Items" by default

        self.stacked_widget.addWidget(items_tab_content)

        # --- Create the "Recipes" tab ---
        self.in_progress_recipes = {} # To store recipe objects
        self.material_list_data = {} # To store aggregated materials

        recipes_tab_content = QWidget()
        recipes_main_layout = QVBoxLayout(recipes_tab_content)

        # Top layout with lists and controls
        recipes_top_layout = QHBoxLayout()
        
        # Available Recipes list
        recipes_list_layout = QVBoxLayout()
        self.recipe_search_box = QLineEdit()
        self.recipe_search_box.setPlaceholderText("Search Recipes...")
        self.recipe_search_box.textChanged.connect(self.filter_recipes_list)
        self.available_recipes_list = QListWidget()
        recipes_list_layout.addWidget(self.recipe_search_box)
        recipes_list_layout.addWidget(self.available_recipes_list)

        # Add/Remove buttons
        add_remove_layout = QVBoxLayout()
        add_remove_layout.addStretch()
        add_recipe_btn = QPushButton("Add ->")
        add_recipe_btn.clicked.connect(self.add_recipe_to_progress)
        remove_recipe_btn = QPushButton("<- Remove")
        remove_recipe_btn.clicked.connect(self.remove_recipe_from_progress)
        add_remove_layout.addWidget(add_recipe_btn)
        add_remove_layout.addWidget(remove_recipe_btn)
        add_remove_layout.addStretch()

        # In-Progress Recipes list
        self.in_progress_recipes_list = QListWidget()

        recipes_top_layout.addLayout(recipes_list_layout)
        recipes_top_layout.addLayout(add_remove_layout)
        recipes_top_layout.addWidget(self.in_progress_recipes_list)
        recipes_main_layout.addLayout(recipes_top_layout)

        # Materials Checklist table
        self.materials_table = QTableWidget()
        self.materials_table.setColumnCount(5) # Add a hidden column for sorting
        self.materials_table.setHorizontalHeaderLabels(["Material", "#", "Unit", "Location", "Checked"])
        self.materials_table.setColumnHidden(4, True) # Hide the 'Checked' column
        self.materials_table.verticalHeader().setVisible(False) # Hide row numbers
        self.materials_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.materials_table.setSortingEnabled(True)
        self.materials_table.itemChanged.connect(self.on_material_checked)
        recipes_main_layout.addWidget(self.materials_table)

        self.stacked_widget.addWidget(recipes_tab_content)

        # --- Create the "Automation" tab ---
        self.automation_timers = {}
        self.is_automation_running = False

        automation_tab_content = QWidget()
        automation_main_layout = QHBoxLayout(automation_tab_content)

        # Left side for key automation
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        automation_keys_group = QGroupBox("Key Automation")
        automation_grid = QGridLayout()

        automationKeys = ["q", "w", "e", "r", "d", "f", "t", "z", "x", "Complete Quest"]
        self.automation_key_ctrls = {}
        row, col = 0, 0
        for key in automationKeys:
            btn = QPushButton(key.upper() if key != "Complete Quest" else "Complete Quest")
            btn.setCheckable(True)
            edit = QLineEdit("15000" if key == "Complete Quest" else "500")
            edit.setFixedWidth(60)
            
            automation_grid.addWidget(btn, row, col * 2)
            automation_grid.addWidget(edit, row, col * 2 + 1)
            
            self.automation_key_ctrls[key] = {"btn": btn, "edit": edit}

            col += 1
            if col > 1:
                col = 0
                row += 1

        # Custom Action
        self.custom_action_btn = QPushButton("Custom Action")
        self.custom_action_btn.setCheckable(True)
        self.custom_action_edit1 = QLineEdit("30000")
        self.custom_action_edit1.setFixedWidth(60)
        self.custom_action_edit2 = QLineEdit("-save x")
        
        custom_action_layout = QHBoxLayout()
        custom_action_layout.addWidget(self.custom_action_btn)
        custom_action_layout.addWidget(self.custom_action_edit1)
        custom_action_layout.addWidget(self.custom_action_edit2)
        automation_grid.addLayout(custom_action_layout, row, 0, 1, 4)
        row += 1

        automation_keys_group.setLayout(automation_grid)
        left_layout.addWidget(automation_keys_group)

        self.start_automation_btn = QPushButton("Start (F5)")
        self.start_automation_btn.clicked.connect(self.toggle_automation)
        left_layout.addWidget(self.start_automation_btn)
        
        interval_note = QLabel("Interval delay default 0.5 seconds (500ms)")
        left_layout.addWidget(interval_note)
        left_layout.addStretch()

        # Right side for message hotkeys
        msg_hotkey_group = QGroupBox("Custom Message Hotkeys")
        right_layout = QVBoxLayout(msg_hotkey_group)

        self.msg_hotkey_table = QTableWidget()
        self.msg_hotkey_table.setColumnCount(2)
        self.msg_hotkey_table.setHorizontalHeaderLabels(["Hotkey", "Message"])
        self.msg_hotkey_table.verticalHeader().setVisible(False)
        self.msg_hotkey_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.msg_hotkey_table)

        msg_form_layout = QGridLayout()
        msg_form_layout.addWidget(QLabel("Hotkey:"), 0, 0)
        self.hotkey_capture_btn = QPushButton("Click to set")
        self.hotkey_capture_btn.clicked.connect(self.capture_message_hotkey)
        msg_form_layout.addWidget(self.hotkey_capture_btn, 0, 1)
        msg_form_layout.addWidget(QLabel("Message:"), 1, 0)
        self.message_edit = QLineEdit()
        msg_form_layout.addWidget(self.message_edit, 1, 1)
        right_layout.addLayout(msg_form_layout)

        msg_btn_layout = QHBoxLayout()
        self.add_msg_btn = QPushButton("Add")
        self.add_msg_btn.clicked.connect(self.add_message_hotkey)
        self.update_msg_btn = QPushButton("Update")
        self.update_msg_btn.clicked.connect(self.update_message_hotkey)
        self.delete_msg_btn = QPushButton("Delete")
        self.delete_msg_btn.clicked.connect(self.delete_message_hotkey)
        msg_btn_layout.addWidget(self.add_msg_btn)
        msg_btn_layout.addWidget(self.update_msg_btn)
        msg_btn_layout.addWidget(self.delete_msg_btn)
        right_layout.addLayout(msg_btn_layout)

        automation_main_layout.addWidget(left_panel, 1)
        automation_main_layout.addWidget(msg_hotkey_group, 1)

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
        settings_layout = QGridLayout(settings_tab_content)
        self.create_theme_grid(settings_layout)
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

        # --- Finalize Setup ---
        self.label = QLabel("This is a placeholder label.") # Keep a reference for reset_state

        # Connect tab bar to a method that can handle special loading
        self.custom_tab_bar.tab_selected.connect(self.on_main_tab_selected)

        # Initial tab selection
        self.load_message_hotkeys()
        self.on_main_tab_selected(0)

        # Apply the initial theme and set button text
        self.apply_theme(self.current_theme_index)



        # Apply the initial theme and set button text
        self.apply_theme(self.current_theme_index)
        self.refresh_lobbies() # Initial data load

        # --- Auto-refresh Timer for Lobbies ---
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30000)  # 30 seconds
        self.refresh_timer.timeout.connect(self.refresh_lobbies)
        self.refresh_timer.start()

    def _run_automation_action(self, action, message=""):
        """Helper to run a single automation task in a thread."""
        # This worker will be short-lived and clean itself up.
        worker = AutomationWorker(self.game_title, action, message)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        if self.is_automation_running:
            self.start_automation_btn.setText("Stop (F5)")
            self.start_automation_btn.setStyleSheet("background-color: #B00000;") # Red for running
            print("Automation Started")

            # Iterate through key automations
            for key, ctrls in self.automation_key_ctrls.items():
                if ctrls["btn"].isChecked():
                    try:
                        interval = int(ctrls["edit"].text())
                        timer = QTimer(self)
                        action = f"-{key}" if key != "Complete Quest" else "-c quest"
                        timer.timeout.connect(lambda act=action: self._run_automation_action(act))
                        timer.start(interval)
                        self.automation_timers[key] = timer
                    except ValueError:
                        print(f"Invalid interval for '{key}'. Must be an integer.")

            # Handle Custom Action
            if self.custom_action_btn.isChecked():
                try:
                    interval = int(self.custom_action_edit1.text())
                    message = self.custom_action_edit2.text()
                    timer = QTimer(self)
                    timer.timeout.connect(lambda msg=message: self._run_automation_action("chat", msg))
                    timer.start(interval)
                    self.automation_timers["custom"] = timer
                except ValueError:
                    print("Invalid interval for 'Custom Action'. Must be an integer.")
        else:
            self.start_automation_btn.setText("Start (F5)")
            self.start_automation_btn.setStyleSheet("")
            for timer in self.automation_timers.values():
                timer.stop()
                timer.deleteLater()
            self.automation_timers.clear()
            print("Automation Stopped")

    def on_main_tab_selected(self, index: int):
        """Handles logic when a main tab is selected."""
        self.stacked_widget.setCurrentIndex(index)
        # Lazy load item data only when the "Items" tab is first clicked
        if self.tab_names[index] == "Items" and not self.item_database.all_items_data:
            self.switch_items_sub_tab(0) # This will trigger the data load
        elif self.tab_names[index] == "Lobbies":
            self.refresh_lobbies()
        elif self.tab_names[index] == "Recipes" and not self.item_database.recipes_data:
            self.item_database.load_recipes()
            self.filter_recipes_list()
        elif self.tab_names[index] == "Automation":
            self.load_message_hotkeys()

    def _create_item_table(self, headers: list) -> QTableWidget:
        """Factory function to create and configure an item table."""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Item name
        for i in range(1, len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        return table

    def create_theme_grid(self, layout: QGridLayout):
        """Creates and populates the theme selection grid."""
        row, col = 0, 0
        for i, theme in enumerate(self.themes):
            preview = ThemePreview()
            preview.setFixedSize(150, 120)
            preview.setCursor(Qt.CursorShape.PointingHandCursor)
            preview.setObjectName("ThemePreview")
            preview.clicked.connect(lambda idx=i: self.apply_theme(idx))

            preview_layout = QVBoxLayout(preview)
            
            color_block = QLabel()
            color_block.setFixedHeight(80)
            color_block.setStyleSheet(f"background-color: {theme['preview_color']}; border-radius: 5px;")
            
            name_label = QLabel(theme['name'])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            preview_layout.addWidget(color_block)
            preview_layout.addWidget(name_label)

            layout.addWidget(preview, row, col)
            self.theme_previews.append(preview)

            col += 1
            if col >= 4: # 4 previews per row
                col = 0
                row += 1
        
        layout.setRowStretch(row + 1, 1)
        layout.setColumnStretch(col + 1, 1)


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
        # This function is no longer tied to a counter, let's update it.
        QMessageBox.information(self, "Info", "This button is just for demonstration!")

    def apply_theme(self, theme_index: int):
        """Applies the selected theme and updates UI elements."""
        self.current_theme_index = theme_index
        theme = self.themes[theme_index]
        
        self.dark_mode = theme["is_dark"]
        self.setStyleSheet(theme["style"])

        # Apply theme to custom tab bar buttons
        self.custom_tab_bar.apply_style(theme['name'], self.dark_mode)
        
        # Update selection border on theme previews
        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid #FF7F50;" if i == theme_index else "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}")
        self.save_settings()

        # Manually update colors for items that have been explicitly set
        self.update_materials_table_colors()

    def update_materials_table_colors(self):
        """Updates the text color of items in the materials table to match the current theme."""
        self.materials_table.itemChanged.disconnect(self.on_material_checked)
        for row in range(self.materials_table.rowCount()):
            # Check the hidden sort column to see if the item is checked
            is_checked = self.materials_table.item(row, 4).text() == "1"
            if not is_checked:
                new_color = self.palette().color(self.foregroundRole())
                for col in range(self.materials_table.columnCount()):
                    self.materials_table.item(row, col).setForeground(new_color)
        self.materials_table.itemChanged.connect(self.on_material_checked)

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
        self.resize(700, 800)
        self.label.setText("Hello! Click the button.")
        self.apply_theme(0) # Reset to the first theme
        self.custom_tab_bar._on_button_clicked(0)
        self.watchlist = self.load_watchlist()
        self.watchlist_widget.clear()
        self.watchlist_widget.addItems(self.watchlist)
        self.save_settings()

    def load_settings(self):
        """Loads settings like the current theme from a file."""
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", 'r') as f:
                    settings = json.load(f)
                    self.current_theme_index = settings.get("theme_index", 0)
                    self.character_path = settings.get("character_path", "")
                    self.message_hotkeys = settings.get("message_hotkeys", {})
        except (IOError, json.JSONDecodeError):
            self.current_theme_index = 0 # Default on error
            self.character_path = ""
            self.message_hotkeys = {}

    def save_settings(self):
        """Saves current settings to a file."""
        settings = {
            "theme_index": self.current_theme_index,
            "character_path": self.character_path,
            "message_hotkeys": self.message_hotkeys
        }
        with open("settings.json", 'w') as f:
            json.dump(settings, f, indent=4)

    def load_watchlist(self):
        """Loads the watchlist from a JSON file."""
        try:
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, 'r') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading watchlist: {e}")
        return ["legion", "hellgate"] # Default if file doesn't exist or is corrupt

    def save_watchlist(self):
        """Saves the current watchlist to a JSON file."""
        with open(self.watchlist_file, 'w') as f:
            json.dump(self.watchlist, f, indent=4)

    def add_to_watchlist(self):
        """Adds a keyword to the watchlist."""
        keyword = self.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.watchlist_widget.addItem(keyword)
            self.watchlist_input.clear()
            self.save_watchlist()
            self.filter_lobbies(self.lobby_search_bar.text()) # Re-filter to apply new keyword

    def remove_from_watchlist(self):
        """Removes the selected keyword from the watchlist."""
        selected_items = self.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.watchlist_widget.takeItem(self.watchlist_widget.row(item))
        self.save_watchlist()
        self.filter_lobbies(self.lobby_search_bar.text()) # Re-filter to update highlighting

    def filter_recipes_list(self):
        """Filters the available recipes list based on its search box."""
        query = self.recipe_search_box.text().lower()
        self.available_recipes_list.clear()
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                # Store the full recipe object in the item
                item.setData(Qt.ItemDataRole.UserRole, recipe)
                self.available_recipes_list.addItem(item)

    def add_recipe_to_progress(self):
        """Adds a selected recipe to the 'in-progress' list and updates materials."""
        selected_item = self.available_recipes_list.currentItem()
        if not selected_item:
            return

        recipe = selected_item.data(Qt.ItemDataRole.UserRole)
        recipe_name = recipe["name"]

        if recipe_name in self.in_progress_recipes:
            QMessageBox.information(self, "Duplicate", "This recipe is already in the 'In Progress' list.")
            return

        # Add to UI and internal tracking
        self.in_progress_recipes[recipe_name] = recipe
        self.in_progress_recipes_list.addItem(recipe_name)

        # Add components to the material list
        for component_str in recipe["components"]:
            self._add_component_to_materials(component_str)
        
        self._rebuild_materials_table()

    def remove_recipe_from_progress(self):
        """Removes a recipe from 'in-progress' and updates the material list."""
        selected_item = self.in_progress_recipes_list.currentItem()
        if not selected_item:
            return

        recipe_name = selected_item.text()
        recipe = self.in_progress_recipes.pop(recipe_name, None)

        if recipe:
            # Remove components from the material list
            for component_str in recipe["components"]:
                self._remove_component_from_materials(component_str)

        self.in_progress_recipes_list.takeItem(self.in_progress_recipes_list.row(selected_item))
        self._rebuild_materials_table()

    def _add_component_to_materials(self, component_str: str):
        """Helper to parse and add a material to the master list."""
        match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
        if match:
            name, quantity = match.group(1).strip(), int(match.group(2))
        else:
            name, quantity = component_str.strip(), 1

        if name in self.material_list_data:
            self.material_list_data[name]["#"] += quantity
        else:
            # Find drop info from the main item database
            if not self.item_database.all_items_data:
                self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
            
            drop_info = next((item for item in self.item_database.all_items_data if item["Item"].lower() == name.lower()), None)
            self.material_list_data[name] = {
                "Material": name,
                "#": quantity,
                "Unit": drop_info["Unit"] if drop_info else "?",
                "Location": drop_info["Location"] if drop_info else "?"
            }

    def _remove_component_from_materials(self, component_str: str):
        """Helper to parse and remove a material from the master list."""
        match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
        if match:
            name, quantity = match.group(1).strip(), int(match.group(2))
        else:
            name, quantity = component_str.strip(), 1

        if name in self.material_list_data:
            self.material_list_data[name]["#"] -= quantity
            if self.material_list_data[name]["#"] <= 0:
                del self.material_list_data[name]

    def _rebuild_materials_table(self):
        """Clears and repopulates the materials table from the internal data dictionary."""
        self.materials_table.setSortingEnabled(False) # Disable sorting during rebuild
        self.materials_table.setRowCount(0)
        for row, item_data in enumerate(self.material_list_data.values()):
            self._add_row_to_materials_table(row, item_data)

    def switch_items_sub_tab(self, index: int):
        """Switches the visible table in the Items tab and loads data."""
        for i, btn in self.item_tab_buttons.items():
            btn.setChecked(i == index)

        self.items_stacked_widget.setCurrentIndex(index)
        
        # Show search box for all item tabs
        self.items_search_box.setVisible(True)

        # Lazy load data
        if index == 0 and not self.item_database.all_items_data:
            self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
        elif index == 1 and not self.item_database.drops_data:
            self.item_database.drops_data = self.item_database._load_item_data_from_folder("Drops")
        elif index == 2 and not self.item_database.raid_data:
            self.item_database.raid_data = self.item_database._load_item_data_from_folder("Raid Items")
        elif index == 3 and not self.item_database.vendor_data:
            self.item_database.vendor_data = self.item_database._load_item_data_from_folder("Vendor Items")
        
        self.filter_current_item_view()

    def _add_row_to_materials_table(self, row_num, item_data):
        """Adds a single row to the materials table, including a checkbox."""
        self.materials_table.insertRow(row_num)
        
        # Column 0: Material (with checkbox)
        material_item = QTableWidgetItem(item_data["Material"])
        material_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        material_item.setCheckState(Qt.CheckState.Unchecked)
        self.materials_table.setItem(row_num, 0, material_item)

        # Column 1: Quantity
        quantity_item = AlignedTableWidgetItem(str(item_data["#"]))
        self.materials_table.setItem(row_num, 1, quantity_item)

        # Column 2 & 3: Unit and Location
        self.materials_table.setItem(row_num, 2, QTableWidgetItem(item_data["Unit"]))
        self.materials_table.setItem(row_num, 3, QTableWidgetItem(item_data["Location"]))

        # Column 4: Hidden sort key for checked status
        checked_item = QTableWidgetItem("0")
        self.materials_table.setItem(row_num, 4, checked_item)

    def on_material_checked(self, item: QTableWidgetItem):
        """Grays out a row in the materials table when its checkbox is ticked."""
        if item.column() != 0: # Only respond to changes in the first column
            return

        is_checked = item.checkState() == Qt.CheckState.Checked
        color = QColor("gray") if is_checked else self.palette().color(self.foregroundRole())
        
        # Temporarily disconnect the signal to prevent recursion
        self.materials_table.itemChanged.disconnect(self.on_material_checked)

        for col in range(self.materials_table.columnCount()):
            table_item = self.materials_table.item(item.row(), col)
            if table_item: # Add a check to ensure the item exists before modifying it
                table_item.setForeground(color)

        # Update the hidden sort column and re-sort the table
        sort_item = self.materials_table.item(item.row(), 4)
        if sort_item:
            sort_item.setText("1" if is_checked else "0")
        self.materials_table.setSortingEnabled(True)
        self.materials_table.sortItems(4, Qt.SortOrder.AscendingOrder) # Sort by checked status

        # Reconnect the signal
        self.materials_table.itemChanged.connect(self.on_material_checked)

    def filter_current_item_view(self):
        """Filters the currently visible item table based on the search query."""
        query = self.items_search_box.text().lower()
        current_index = self.items_stacked_widget.currentIndex()

        data_source = []
        table_widget = None

        if current_index == 0:
            data_source = self.item_database.all_items_data
            table_widget = self.all_items_table
        elif current_index == 1:
            data_source = self.item_database.drops_data
            table_widget = self.drops_table
        elif current_index == 2:
            data_source = self.item_database.raid_data
            table_widget = self.raid_items_table
        elif current_index == 3:
            data_source = self.item_database.vendor_data
            table_widget = self.vendor_table

        if not table_widget:
            return

        table_widget.setSortingEnabled(False)
        table_widget.setRowCount(0)

        filtered_data = [
            item for item in data_source
            if query in item.get("Item", "").lower() or \
               query in item.get("Unit", "").lower() or \
               query in item.get("Location", "").lower()
        ]

        for row, item_data in enumerate(filtered_data):
            table_widget.insertRow(row)
            for col, header in enumerate([table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())]):
                table_widget.setItem(row, col, QTableWidgetItem(item_data.get(header, "")))
        
        table_widget.setSortingEnabled(True)

    def on_path_changed(self, new_path: str):
        """Updates character path when the text is edited."""
        self.character_path = new_path
        self.save_settings()

    def select_character_path(self):
        """Opens a dialog to select the character data folder."""
        default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData")
        new_path = QFileDialog.getExistingDirectory(self, "Select the character data folder", dir=default_path)
        if new_path:
            self.load_path_edit.setText(new_path)
            self.load_characters() # Automatically refresh

    def reset_character_path(self):
        """Resets the character path to the default location."""
        confirm_box = QMessageBox.question(self, "Confirm Reset", "Reset character path to default?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)
        if confirm_box == QMessageBox.StandardButton.Yes:
            default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
            self.load_path_edit.setText(default_path)
            self.load_characters() # Automatically refresh

    def load_characters(self):
        """Loads and displays character files from the specified path."""
        self.char_list_box.clear()
        self.char_content_box.clear()

        if not self.character_path or not os.path.isdir(self.character_path):
            if self.character_path: # Only show error if path is set but invalid
                QMessageBox.warning(self, "Error", f"Character save directory not found:\n{self.character_path}")
            return

        char_files = []
        for filename in os.listdir(self.character_path):
            if filename.endswith(".txt"):
                full_path = os.path.join(self.character_path, filename)
                try:
                    mod_time = os.path.getmtime(full_path)
                    char_name = os.path.splitext(filename)[0]
                    char_files.append({"name": char_name, "path": full_path, "mod_time": mod_time})
                except OSError:
                    continue # Skip files that can't be accessed

        # Sort by modification time, descending
        sorted_chars = sorted(char_files, key=lambda x: x["mod_time"], reverse=True)

        for char in sorted_chars:
            item = QListWidgetItem(char["name"])
            item.setData(Qt.ItemDataRole.UserRole, char["path"]) # Store full path in the item
            self.char_list_box.addItem(item)

        if self.char_list_box.count() > 0:
            self.char_list_box.setCurrentRow(0)

    def show_character_file_contents(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """Displays the content of the selected character file."""
        if not current_item:
            self.char_content_box.clear()
            return

        file_path = current_item.data(Qt.ItemDataRole.UserRole)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.char_content_box.setText(f.read())
        except (IOError, OSError) as e:
            self.char_content_box.setText(f"Error reading file: {e}")

    def load_selected_character(self):
        """Sends the -load command for the selected character to the game."""
        current_item = self.char_list_box.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Character Selected", "Please select a character from the list.")
            return

        char_name = current_item.text()
        game_title = "Warcraft III"

        try:
            hwnd = win32gui.FindWindow(None, game_title)
            if hwnd == 0:
                QMessageBox.critical(self, "Error", f"'{game_title}' window not found.")
                return

            win32gui.SetForegroundWindow(hwnd)
            pyautogui.press('enter')
            pyautogui.write(f"-load {char_name}", interval=0.05)
            pyautogui.press('enter')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send command to game: {e}")

    def refresh_lobbies(self):
        """Placeholder method to refresh lobby data."""
        self.lobbies_table.setRowCount(0) # Clear table
        self.lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data...")
        loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # This line is correct
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
        # Check for new watched lobbies before updating the main list
        current_watched_lobbies = set()
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    # Use a unique identifier for the lobby, name is usually good enough
                    current_watched_lobbies.add(lobby.get('name'))
                    break

        newly_found = current_watched_lobbies - self.previous_watched_lobbies
        if newly_found:
            QApplication.beep()

        self.previous_watched_lobbies = current_watched_lobbies
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobby_search_bar.text())

    def on_lobbies_fetch_error(self, error_message: str):
        """Slot to handle errors during lobby data fetching."""
        self.lobbies_table.setRowCount(1)
        self.lobbies_table.setSpan(0, 0, 1, self.lobbies_table.columnCount())
        error_item = QTableWidgetItem(f"Error: {error_message}")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, error_item)

    def filter_lobbies(self, query: str):
        """Filters and displays lobbies based on the search query."""
        self.lobbies_table.setRowCount(0) # Clear table
        self.lobbies_table.setSortingEnabled(False)
        
        # On a simple filter, we don't want to clear the "previous" state for notifications
        # so we only update self.previous_watched_lobbies on a full refresh (in on_lobbies_fetched)

        query = query.lower()
        filtered_lobbies = [
            lobby for lobby in self.all_lobbies 
            if query in lobby.get('name', '').lower() or query in lobby.get('map', '').lower()
        ]

        # Sort the lobbies to show watched ones first
        def is_watched(lobby):
            name = lobby.get('name', '').lower()
            map_name = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in name or keyword in map_name:
                    return True
            return False

        # Sort by watched status (descending) so True comes before False
        sorted_lobbies = sorted(filtered_lobbies, key=is_watched, reverse=True)

        self.lobbies_table.setRowCount(len(sorted_lobbies))
        for row, lobby in enumerate(sorted_lobbies):
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            
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

    def capture_message_hotkey(self):
        """Initiates the process of capturing a new hotkey."""
        # Disable the message box to prevent it from receiving the keypress
        self.message_edit.setEnabled(False)
        self.hotkey_capture_btn.setText("[Press a key...]")
        self.hotkey_capture_btn.setEnabled(False)

        self.capture_thread = QThread()
        self.capture_worker = HotkeyCaptureWorker()
        self.capture_worker.moveToThread(self.capture_thread)

        self.capture_thread.started.connect(self.capture_worker.run)
        self.capture_worker.hotkey_captured.connect(self.on_hotkey_captured)

        self.capture_thread.start()

    def on_hotkey_captured(self, hotkey: str):
        """Updates the UI once a hotkey has been captured by the worker."""
        # Re-enable the message box now that capture is complete
        self.message_edit.setEnabled(True)
        if hotkey == 'esc':
            self.hotkey_capture_btn.setText("Click to set")
        else:
            self.hotkey_capture_btn.setText(hotkey)
        self.hotkey_capture_btn.setEnabled(True)
        self.capture_thread.quit()

    def load_message_hotkeys(self):
        """Loads hotkeys from settings and populates the table."""
        self.msg_hotkey_table.setRowCount(0)
        for hotkey, message in self.message_hotkeys.items():
            row_position = self.msg_hotkey_table.rowCount()
            self.msg_hotkey_table.insertRow(row_position)
            self.msg_hotkey_table.setItem(row_position, 0, QTableWidgetItem(hotkey))
            self.msg_hotkey_table.setItem(row_position, 1, QTableWidgetItem(message))
        self.register_all_message_hotkeys()

    def add_message_hotkey(self):
        """Adds a new hotkey and message to the list."""
        hotkey = self.hotkey_capture_btn.text()
        message = self.message_edit.text()

        if hotkey == "Click to set" or not message:
            QMessageBox.warning(self, "Input Error", "Please set a hotkey and enter a message.")
            return

        if hotkey in self.message_hotkeys:
            QMessageBox.warning(self, "Duplicate Hotkey", "This hotkey is already in use.")
            return

        self.message_hotkeys[hotkey] = message
        self.save_settings()
        self.load_message_hotkeys()
        self.hotkey_capture_btn.setText("Click to set")
        self.message_edit.clear()

    def update_message_hotkey(self):
        """Updates the selected hotkey and message."""
        selected_items = self.msg_hotkey_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to update.")
            return

        selected_row = selected_items[0].row()
        old_hotkey = self.msg_hotkey_table.item(selected_row, 0).text()
        
        new_hotkey = self.hotkey_capture_btn.text()
        new_message = self.message_edit.text()

        if new_hotkey != old_hotkey and new_hotkey in self.message_hotkeys:
            QMessageBox.warning(self, "Duplicate Hotkey", "The new hotkey is already in use.")
            return

        # Remove old, add new
        del self.message_hotkeys[old_hotkey]
        self.message_hotkeys[new_hotkey] = new_message
        self.save_settings()
        self.load_message_hotkeys()

    def delete_message_hotkey(self):
        """Deletes the selected hotkey."""
        selected_items = self.msg_hotkey_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to delete.")
            return

        hotkey_to_delete = self.msg_hotkey_table.item(selected_items[0].row(), 0).text()
        
        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the hotkey '{hotkey_to_delete}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            if hotkey_to_delete in self.message_hotkeys:
                del self.message_hotkeys[hotkey_to_delete]
                self.save_settings()
                self.load_message_hotkeys()

    def register_all_message_hotkeys(self):
        """Registers all loaded hotkeys with the keyboard listener."""
        keyboard.unhook_all() # Clear previous hooks
        for hotkey, message in self.message_hotkeys.items():
            # Create a closure to capture the correct message for the callback
            callback = (lambda msg: lambda: self.send_chat_message(msg))(message)
            keyboard.add_hotkey(hotkey, callback, suppress=True)

    def send_chat_message(self, message: str):
        """Sends a chat message if the game window is active."""
        try:
            if win32gui.GetForegroundWindow() == win32gui.FindWindow(None, self.game_title):
                pyautogui.press('enter')
                pyautogui.write(message, interval=0.01)
                pyautogui.press('enter')
        except Exception as e:
            print(f"Error sending chat message: {e}")

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
        self.layout.setContentsMargins(5, 0, 5, 0) # Add some horizontal margin
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

    def apply_style(self, theme_name: str, dark_mode: bool):
        # This method applies specific styling for the buttons within this custom tab bar,
        # including the :checked state, overriding general QPushButton styles if necessary.
        if theme_name == "Black/Orange":
            # Specific style for Black/Orange
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
                QPushButton:checked {
                    background-color: #FF7F50;
                    color: #F0F0F0;
                    border-color: #FF7F50;
                }
            """)
        elif dark_mode:
            # Generic style for other dark themes (e.g., Black/Blue)
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #EAEAEA;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #4682B4; /* SteelBlue */
                }
                QPushButton:checked {
                    background-color: #1E90FF; /* DodgerBlue */
                    color: #EAEAEA;
                    border-color: #4169E1; /* RoyalBlue */
                }
            """)
        elif theme_name == "White/Blue":
            # Specific style for White/Blue
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #87CEEB; /* SkyBlue */
                    border: 1px solid #4682B4; /* SteelBlue */
                    padding: 8px;
                    border-radius: 6px;
                    color: #000080; /* Navy */
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #87CEFA; /* LightSkyBlue */
                }
                QPushButton:checked {
                    background-color: #4682B4; /* SteelBlue */
                    color: #F0F8FF; /* AliceBlue */
                }
            """)
        else:
            # Default for other light themes (e.g., White/Pink)
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #FFC0CB; /* Pink */
                    border: 1px solid #E6A8B8; /* Darker pink border */
                    padding: 8px;
                    border-radius: 6px;
                    color: #2E3440; /* nord0 */
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #F6B3F5;
                }
                QPushButton:checked {
                    background-color: #DB7093; /* PaleVioletRed for selection */
                    color: #2E3440;
                }
            """)

if __name__ == "__main__":
    # Set this environment variable to prevent Qt from trying to set
    # the DPI awareness, which can suppress the "Access is denied" warning.
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())

    def _create_item_table(self, headers: list) -> QTableWidget:
        """Factory function to create and configure an item table."""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # Item name
        for i in range(1, len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        return table

    def create_theme_grid(self, layout: QGridLayout):
        """Creates and populates the theme selection grid."""
        row, col = 0, 0
        for i, theme in enumerate(self.themes):
            preview = ThemePreview()
            preview.setFixedSize(150, 120)
            preview.setCursor(Qt.CursorShape.PointingHandCursor)
            preview.setObjectName("ThemePreview")
            preview.clicked.connect(lambda idx=i: self.apply_theme(idx))

            preview_layout = QVBoxLayout(preview)
            
            color_block = QLabel()
            color_block.setFixedHeight(80)
            color_block.setStyleSheet(f"background-color: {theme['preview_color']}; border-radius: 5px;")
            
            name_label = QLabel(theme['name'])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            preview_layout.addWidget(color_block)
            preview_layout.addWidget(name_label)

            layout.addWidget(preview, row, col)
            self.theme_previews.append(preview)

            col += 1
            if col >= 4: # 4 previews per row
                col = 0
                row += 1
        
        layout.setRowStretch(row + 1, 1)
        layout.setColumnStretch(col + 1, 1)


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
        # This function is no longer tied to a counter, let's update it.
        QMessageBox.information(self, "Info", "This button is just for demonstration!")

    def apply_theme(self, theme_index: int):
        """Applies the selected theme and updates UI elements."""
        self.current_theme_index = theme_index
        theme = self.themes[theme_index]
        
        self.dark_mode = theme["is_dark"]
        self.setStyleSheet(theme["style"])

        # Apply theme to custom tab bar buttons
        self.custom_tab_bar.apply_style(theme['name'], self.dark_mode)
        
        # Update selection border on theme previews
        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid #FF7F50;" if i == theme_index else "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}")
        self.save_settings()

        # Manually update colors for items that have been explicitly set
        self.update_materials_table_colors()

    def update_materials_table_colors(self):
        """Updates the text color of items in the materials table to match the current theme."""
        self.materials_table.itemChanged.disconnect(self.on_material_checked)
        for row in range(self.materials_table.rowCount()):
            # Check the hidden sort column to see if the item is checked
            is_checked = self.materials_table.item(row, 4).text() == "1"
            if not is_checked:
                new_color = self.palette().color(self.foregroundRole())
                for col in range(self.materials_table.columnCount()):
                    self.materials_table.item(row, col).setForeground(new_color)
        self.materials_table.itemChanged.connect(self.on_material_checked)

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
        self.resize(700, 800)
        self.label.setText("Hello! Click the button.")
        self.apply_theme(0) # Reset to the first theme
        self.custom_tab_bar._on_button_clicked(0)
        self.watchlist = self.load_watchlist()
        self.watchlist_widget.clear()
        self.watchlist_widget.addItems(self.watchlist)
        self.save_settings()

    def load_settings(self):
        """Loads settings like the current theme from a file."""
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", 'r') as f:
                    settings = json.load(f)
                    self.current_theme_index = settings.get("theme_index", 0)
                    self.character_path = settings.get("character_path", "")
        except (IOError, json.JSONDecodeError):
            self.current_theme_index = 0 # Default on error
            self.character_path = ""

    def save_settings(self):
        """Saves current settings to a file."""
        settings = {
            "theme_index": self.current_theme_index,
            "character_path": self.character_path
        }
        with open("settings.json", 'w') as f:
            json.dump(settings, f, indent=4)

    def load_watchlist(self):
        """Loads the watchlist from a JSON file."""
        try:
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, 'r') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading watchlist: {e}")
        return ["legion", "hellgate"] # Default if file doesn't exist or is corrupt

    def save_watchlist(self):
        """Saves the current watchlist to a JSON file."""
        with open(self.watchlist_file, 'w') as f:
            json.dump(self.watchlist, f, indent=4)

    def add_to_watchlist(self):
        """Adds a keyword to the watchlist."""
        keyword = self.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.watchlist_widget.addItem(keyword)
            self.watchlist_input.clear()
            self.save_watchlist()
            self.filter_lobbies(self.lobby_search_bar.text()) # Re-filter to apply new keyword

    def remove_from_watchlist(self):
        """Removes the selected keyword from the watchlist."""
        selected_items = self.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.watchlist_widget.takeItem(self.watchlist_widget.row(item))
        self.save_watchlist()
        self.filter_lobbies(self.lobby_search_bar.text()) # Re-filter to update highlighting

    def filter_recipes_list(self):
        """Filters the available recipes list based on its search box."""
        query = self.recipe_search_box.text().lower()
        self.available_recipes_list.clear()
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                # Store the full recipe object in the item
                item.setData(Qt.ItemDataRole.UserRole, recipe)
                self.available_recipes_list.addItem(item)

    def add_recipe_to_progress(self):
        """Adds a selected recipe to the 'in-progress' list and updates materials."""
        selected_item = self.available_recipes_list.currentItem()
        if not selected_item:
            return

        recipe = selected_item.data(Qt.ItemDataRole.UserRole)
        recipe_name = recipe["name"]

        if recipe_name in self.in_progress_recipes:
            QMessageBox.information(self, "Duplicate", "This recipe is already in the 'In Progress' list.")
            return

        # Add to UI and internal tracking
        self.in_progress_recipes[recipe_name] = recipe
        self.in_progress_recipes_list.addItem(recipe_name)

        # Add components to the material list
        for component_str in recipe["components"]:
            self._add_component_to_materials(component_str)
        
        self._rebuild_materials_table()

    def remove_recipe_from_progress(self):
        """Removes a recipe from 'in-progress' and updates the material list."""
        selected_item = self.in_progress_recipes_list.currentItem()
        if not selected_item:
            return

        recipe_name = selected_item.text()
        recipe = self.in_progress_recipes.pop(recipe_name, None)

        if recipe:
            # Remove components from the material list
            for component_str in recipe["components"]:
                self._remove_component_from_materials(component_str)

        self.in_progress_recipes_list.takeItem(self.in_progress_recipes_list.row(selected_item))
        self._rebuild_materials_table()

    def _add_component_to_materials(self, component_str: str):
        """Helper to parse and add a material to the master list."""
        match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
        if match:
            name, quantity = match.group(1).strip(), int(match.group(2))
        else:
            name, quantity = component_str.strip(), 1

        if name in self.material_list_data:
            self.material_list_data[name]["#"] += quantity
        else:
            # Find drop info from the main item database
            if not self.item_database.all_items_data:
                self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
            
            drop_info = next((item for item in self.item_database.all_items_data if item["Item"].lower() == name.lower()), None)
            self.material_list_data[name] = {
                "Material": name,
                "#": quantity,
                "Unit": drop_info["Unit"] if drop_info else "?",
                "Location": drop_info["Location"] if drop_info else "?"
            }

    def _remove_component_from_materials(self, component_str: str):
        """Helper to parse and remove a material from the master list."""
        match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
        if match:
            name, quantity = match.group(1).strip(), int(match.group(2))
        else:
            name, quantity = component_str.strip(), 1

        if name in self.material_list_data:
            self.material_list_data[name]["#"] -= quantity
            if self.material_list_data[name]["#"] <= 0:
                del self.material_list_data[name]

    def _rebuild_materials_table(self):
        """Clears and repopulates the materials table from the internal data dictionary."""
        self.materials_table.setSortingEnabled(False) # Disable sorting during rebuild
        self.materials_table.setRowCount(0)
        for row, item_data in enumerate(self.material_list_data.values()):
            self._add_row_to_materials_table(row, item_data)

    def switch_items_sub_tab(self, index: int):
        """Switches the visible table in the Items tab and loads data."""
        for i, btn in self.item_tab_buttons.items():
            btn.setChecked(i == index)

        self.items_stacked_widget.setCurrentIndex(index)
        
        # Show search box for all item tabs
        self.items_search_box.setVisible(True)

        # Lazy load data
        if index == 0 and not self.item_database.all_items_data:
            self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
        elif index == 1 and not self.item_database.drops_data:
            self.item_database.drops_data = self.item_database._load_item_data_from_folder("Drops")
        elif index == 2 and not self.item_database.raid_data:
            self.item_database.raid_data = self.item_database._load_item_data_from_folder("Raid Items")
        elif index == 3 and not self.item_database.vendor_data:
            self.item_database.vendor_data = self.item_database._load_item_data_from_folder("Vendor Items")
        
        self.filter_current_item_view()

    def _add_row_to_materials_table(self, row_num, item_data):
        """Adds a single row to the materials table, including a checkbox."""
        self.materials_table.insertRow(row_num)
        
        # Column 0: Material (with checkbox)
        material_item = QTableWidgetItem(item_data["Material"])
        material_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        material_item.setCheckState(Qt.CheckState.Unchecked)
        self.materials_table.setItem(row_num, 0, material_item)

        # Column 1: Quantity
        quantity_item = AlignedTableWidgetItem(str(item_data["#"]))
        self.materials_table.setItem(row_num, 1, quantity_item)

        # Column 2 & 3: Unit and Location
        self.materials_table.setItem(row_num, 2, QTableWidgetItem(item_data["Unit"]))
        self.materials_table.setItem(row_num, 3, QTableWidgetItem(item_data["Location"]))

        # Column 4: Hidden sort key for checked status
        checked_item = QTableWidgetItem("0")
        self.materials_table.setItem(row_num, 4, checked_item)

    def on_material_checked(self, item: QTableWidgetItem):
        """Grays out a row in the materials table when its checkbox is ticked."""
        if item.column() != 0: # Only respond to changes in the first column
            return

        is_checked = item.checkState() == Qt.CheckState.Checked
        color = QColor("gray") if is_checked else self.palette().color(self.foregroundRole())
        
        # Temporarily disconnect the signal to prevent recursion
        self.materials_table.itemChanged.disconnect(self.on_material_checked)

        for col in range(self.materials_table.columnCount()):
            table_item = self.materials_table.item(item.row(), col)
            if table_item: # Add a check to ensure the item exists before modifying it
                table_item.setForeground(color)

        # Update the hidden sort column and re-sort the table
        sort_item = self.materials_table.item(item.row(), 4)
        if sort_item:
            sort_item.setText("1" if is_checked else "0")
        self.materials_table.setSortingEnabled(True)
        self.materials_table.sortItems(4, Qt.SortOrder.AscendingOrder) # Sort by checked status

        # Reconnect the signal
        self.materials_table.itemChanged.connect(self.on_material_checked)

    def filter_current_item_view(self):
        """Filters the currently visible item table based on the search query."""
        query = self.items_search_box.text().lower()
        current_index = self.items_stacked_widget.currentIndex()

        data_source = []
        table_widget = None

        if current_index == 0:
            data_source = self.item_database.all_items_data
            table_widget = self.all_items_table
        elif current_index == 1:
            data_source = self.item_database.drops_data
            table_widget = self.drops_table
        elif current_index == 2:
            data_source = self.item_database.raid_data
            table_widget = self.raid_items_table
        elif current_index == 3:
            data_source = self.item_database.vendor_data
            table_widget = self.vendor_table

        if not table_widget:
            return

        table_widget.setSortingEnabled(False)
        table_widget.setRowCount(0)

        filtered_data = [
            item for item in data_source
            if query in item.get("Item", "").lower() or \
               query in item.get("Unit", "").lower() or \
               query in item.get("Location", "").lower()
        ]

        for row, item_data in enumerate(filtered_data):
            table_widget.insertRow(row)
            for col, header in enumerate([table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())]):
                table_widget.setItem(row, col, QTableWidgetItem(item_data.get(header, "")))
        
        table_widget.setSortingEnabled(True)

    def on_path_changed(self, new_path: str):
        """Updates character path when the text is edited."""
        self.character_path = new_path
        self.save_settings()

    def select_character_path(self):
        """Opens a dialog to select the character data folder."""
        default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData")
        new_path = QFileDialog.getExistingDirectory(self, "Select the character data folder", dir=default_path)
        if new_path:
            self.load_path_edit.setText(new_path)
            self.load_characters() # Automatically refresh

    def reset_character_path(self):
        """Resets the character path to the default location."""
        confirm_box = QMessageBox.question(self, "Confirm Reset", "Reset character path to default?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)
        if confirm_box == QMessageBox.StandardButton.Yes:
            default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
            self.load_path_edit.setText(default_path)
            self.load_characters() # Automatically refresh

    def load_characters(self):
        """Loads and displays character files from the specified path."""
        self.char_list_box.clear()
        self.char_content_box.clear()

        if not self.character_path or not os.path.isdir(self.character_path):
            if self.character_path: # Only show error if path is set but invalid
                QMessageBox.warning(self, "Error", f"Character save directory not found:\n{self.character_path}")
            return

        char_files = []
        for filename in os.listdir(self.character_path):
            if filename.endswith(".txt"):
                full_path = os.path.join(self.character_path, filename)
                try:
                    mod_time = os.path.getmtime(full_path)
                    char_name = os.path.splitext(filename)[0]
                    char_files.append({"name": char_name, "path": full_path, "mod_time": mod_time})
                except OSError:
                    continue # Skip files that can't be accessed

        # Sort by modification time, descending
        sorted_chars = sorted(char_files, key=lambda x: x["mod_time"], reverse=True)

        for char in sorted_chars:
            item = QListWidgetItem(char["name"])
            item.setData(Qt.ItemDataRole.UserRole, char["path"]) # Store full path in the item
            self.char_list_box.addItem(item)

        if self.char_list_box.count() > 0:
            self.char_list_box.setCurrentRow(0)

    def show_character_file_contents(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """Displays the content of the selected character file."""
        if not current_item:
            self.char_content_box.clear()
            return

        file_path = current_item.data(Qt.ItemDataRole.UserRole)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.char_content_box.setText(f.read())
        except (IOError, OSError) as e:
            self.char_content_box.setText(f"Error reading file: {e}")

    def load_selected_character(self):
        """Sends the -load command for the selected character to the game."""
        current_item = self.char_list_box.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Character Selected", "Please select a character from the list.")
            return

        char_name = current_item.text()
        game_title = "Warcraft III"

        try:
            hwnd = win32gui.FindWindow(None, game_title)
            if hwnd == 0:
                QMessageBox.critical(self, "Error", f"'{game_title}' window not found.")
                return

            win32gui.SetForegroundWindow(hwnd)
            pyautogui.press('enter')
            pyautogui.write(f"-load {char_name}", interval=0.05)
            pyautogui.press('enter')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send command to game: {e}")

    def refresh_lobbies(self):
        """Placeholder method to refresh lobby data."""
        self.lobbies_table.setRowCount(0) # Clear table
        self.lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data...")
        loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # This line is correct
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
        # Check for new watched lobbies before updating the main list
        current_watched_lobbies = set()
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    # Use a unique identifier for the lobby, name is usually good enough
                    current_watched_lobbies.add(lobby.get('name'))
                    break

        newly_found = current_watched_lobbies - self.previous_watched_lobbies
        if newly_found:
            QApplication.beep()

        self.previous_watched_lobbies = current_watched_lobbies
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobby_search_bar.text())

    def on_lobbies_fetch_error(self, error_message: str):
        """Slot to handle errors during lobby data fetching."""
        self.lobbies_table.setRowCount(1)
        self.lobbies_table.setSpan(0, 0, 1, self.lobbies_table.columnCount())
        error_item = QTableWidgetItem(f"Error: {error_message}")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, error_item)

    def filter_lobbies(self, query: str):
        """Filters and displays lobbies based on the search query."""
        self.lobbies_table.setRowCount(0) # Clear table
        self.lobbies_table.setSortingEnabled(False)
        
        # On a simple filter, we don't want to clear the "previous" state for notifications
        # so we only update self.previous_watched_lobbies on a full refresh (in on_lobbies_fetched)

        query = query.lower()
        filtered_lobbies = [
            lobby for lobby in self.all_lobbies 
            if query in lobby.get('name', '').lower() or query in lobby.get('map', '').lower()
        ]

        # Sort the lobbies to show watched ones first
        def is_watched(lobby):
            name = lobby.get('name', '').lower()
            map_name = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in name or keyword in map_name:
                    return True
            return False

        # Sort by watched status (descending) so True comes before False
        sorted_lobbies = sorted(filtered_lobbies, key=is_watched, reverse=True)

        self.lobbies_table.setRowCount(len(sorted_lobbies))
        for row, lobby in enumerate(sorted_lobbies):
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            
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
        self.layout.setContentsMargins(5, 0, 5, 0) # Add some horizontal margin
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

    def apply_style(self, theme_name: str, dark_mode: bool):
        # This method applies specific styling for the buttons within this custom tab bar,
        # including the :checked state, overriding general QPushButton styles if necessary.
        if theme_name == "Black/Orange":
            # Specific style for Black/Orange
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
                QPushButton:checked {
                    background-color: #FF7F50;
                    color: #F0F0F0;
                    border-color: #FF7F50;
                }
            """)
        elif dark_mode:
            # Generic style for other dark themes (e.g., Black/Blue)
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #EAEAEA;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #4682B4; /* SteelBlue */
                }
                QPushButton:checked {
                    background-color: #1E90FF; /* DodgerBlue */
                    color: #EAEAEA;
                    border-color: #4169E1; /* RoyalBlue */
                }
            """)
        elif theme_name == "White/Blue":
            # Specific style for White/Blue
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #87CEEB; /* SkyBlue */
                    border: 1px solid #4682B4; /* SteelBlue */
                    padding: 8px;
                    border-radius: 6px;
                    color: #000080; /* Navy */
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #87CEFA; /* LightSkyBlue */
                }
                QPushButton:checked {
                    background-color: #4682B4; /* SteelBlue */
                    color: #F0F8FF; /* AliceBlue */
                }
            """)
        else:
            # Default for other light themes (e.g., White/Pink)
            self.setStyleSheet("""
                QPushButton { /* Tab buttons */
                    background-color: #FFC0CB; /* Pink */
                    border: 1px solid #E6A8B8; /* Darker pink border */
                    padding: 8px;
                    border-radius: 6px;
                    color: #2E3440; /* nord0 */
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #F6B3F5;
                }
                QPushButton:checked {
                    background-color: #DB7093; /* PaleVioletRed for selection */
                    color: #2E3440;
                }
            """)

if __name__ == "__main__":
    # Set this environment variable to prevent Qt from trying to set
    # the DPI awareness, which can suppress the "Access is denied" warning.
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())