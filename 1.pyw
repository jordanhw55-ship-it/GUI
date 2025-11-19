import sys
import requests
import json
import os
import re
from typing import List
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog, QTextEdit, QComboBox,
    QListWidgetItem, QColorDialog, QCheckBox
)
from PySide6.QtCore import Signal, Qt, QObject, QThread, QTimer, QUrl
from PySide6.QtGui import QMouseEvent, QColor, QIntValidator
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import keyboard   # type: ignore
import pyautogui  # type: ignore
try:
    import win32gui
    import winsound
except ImportError:
    print("Windows-specific libraries (pywin32) not found. Some features will be disabled.")


DARK_STYLE = """
    /* Black/Orange Theme */
    QWidget {
        background-color: #121212;
        color: #F0F0F0;
        font-family: 'Segoe UI';
        font-size: 14px;
        outline: none;
    }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel { background-color: transparent; color: #F0F0F0; font-size: 16px; }
    #CustomTitleBar QPushButton { background-color: transparent; border: none; color: #F0F0F0; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #FFA64D; }
    QPushButton {
        background-color: #FF7F50;
        border: 1px solid #444444;
        padding: 5px;
        border-radius: 6px;
        color: #000000;
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
    QWidget { background-color: #FFFFFF; color: #000000; font-family: 'Segoe UI'; font-size: 14px; outline: none; }
    QMainWindow { background-color: #ECEFF4; }
    #CustomTitleBar { background-color: #FFFFFF; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { background-color: transparent; color: #000000; border: none; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #DA3A9D; }
    QPushButton {
        background-color: #FFC0CB;
        border: 1px solid #E6A8B8;
        padding: 5px;
        border-radius: 6px;
        color: #000000;
    }
    QHeaderView::section { background-color: #FFC0CB; border: 1px solid #E6A8B8; color: #000000; }
"""

FOREST_STYLE = """
    /* Black/Blue Theme */
    QWidget { background-color: #121212; color: #EAEAEA; font-family: 'Segoe UI'; font-size: 14px; outline: none; }
    QMainWindow { background-color: #1F1F1F; }
    #CustomTitleBar { background-color: #1F1F1F; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { color: #EAEAEA; background-color: transparent; border: none; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #4682B4; }
    QPushButton { background-color: #1E90FF; border: 1px solid #4169E1; padding: 5px; border-radius: 6px; }
    QHeaderView::section { background-color: #1F1F1F; border: 1px solid #4169E1; }
"""

OCEAN_STYLE = """
    /* White/Blue Theme */
    QWidget { background-color: #F0F8FF; color: #000080; font-family: 'Segoe UI'; font-size: 14px; outline: none; }
    QMainWindow { background-color: #F0F8FF; }
    #CustomTitleBar { background-color: #F0F8FF; }
    #CustomTitleBar QLabel, #CustomTitleBar QPushButton { color: #000080; background-color: transparent; border: none; font-size: 16px; }
    #CustomTitleBar QPushButton:hover { background-color: #87CEFA; }
    QPushButton { background-color: #87CEEB; border: 1px solid #4682B4; padding: 5px; border-radius: 6px; }
    QHeaderView::section { background-color: #ADD8E6; border: 1px solid #87CEEB; }
"""

def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka """
    if getattr(sys, 'frozen', False):
        # The application is frozen
        return os.path.dirname(sys.executable)
    else:
        # The application is not frozen
        # Change this to the directory of your main script
        return os.path.dirname(os.path.abspath(__file__))

class ItemDatabase:
    """Handles loading and searching item data from text files."""
    def __init__(self):
        self.base_path = os.path.join(get_base_path(), "contents")
        self.all_items_data = []
        self.drops_data = []
        self.raid_data = []
        self.vendor_data = []
        self.recipes_data = []

    def _clean_item(self, raw_line: str) -> dict:
        line = raw_line.strip()
        if not line:
            return {}
        patterns = [
            r"^\s*\[([^\]]+)\]\s*(.+?)\s*[:\-]\s*([\d\.]+)%\s*$",
            r"^\s*\[([^\]]+)\]\s*(.+)$",
            r"^\s*(.+?)\s*[:\-]\s*([\d\.]+)%\s*$",
        ]
        for i, pattern in enumerate(patterns):
            match = re.match(pattern, line)
            if match:
                if i == 0: return {"type": match.group(1), "name": match.group(2).strip(), "rate": f"{match.group(3)}%"}
                if i == 1: return {"type": match.group(1), "name": match.group(2).strip(), "rate": ""}
                if i == 2: return {"name": match.group(1).strip(), "rate": f"{match.group(2)}%"}
        return {"name": line, "rate": ""}

    def _load_item_data_from_folder(self, folder: str) -> list:
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
                    for raw in f:
                        line = raw.strip()
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
                continue
        return data

    def load_recipes(self):
        if self.recipes_data:
            return
        file_path = os.path.join(self.base_path, "Recipes.txt")
        if not os.path.exists(file_path):
            return
        self.recipes_data = []
        current_recipe_name = ""
        current_components = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        if current_recipe_name:
                            self.recipes_data.append({"name": current_recipe_name, "components": current_components})
                            current_recipe_name = ""
                            current_components = []
                        continue
                    material_match = re.match(r"^\s*Material\s*:\s*(.+)", line, re.IGNORECASE)
                    if material_match:
                        if current_recipe_name:
                            current_components.append(material_match.group(1).strip())
                    else:
                        if current_recipe_name:
                            self.recipes_data.append({"name": current_recipe_name, "components": current_components})
                        current_recipe_name = line
                        current_components = []
            if current_recipe_name:
                self.recipes_data.append({"name": current_recipe_name, "components": current_components})
        except (IOError, OSError):
            print(f"Could not read {file_path}")


class ThemePreview(QWidget):
    """Clickable theme preview."""
    clicked = Signal()
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class LobbyFetcher(QObject):
    finished = Signal(list)
    error = Signal(str)
    def run(self):
        try:
            response = requests.get("https://api.wc3stats.com/gamelist", timeout=10)
            response.raise_for_status()
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
    """Runs in a separate thread to capture a hotkey without freezing the GUI."""
    hotkey_captured = Signal(str)
    def run(self):
        try:
            # Capture a single hotkey string, suppress so it doesn't leak into GUI
            hotkey = keyboard.read_hotkey(suppress=True)
            self.hotkey_captured.emit(hotkey)
        except Exception as e:
            print(f"Error capturing hotkey: {e}")


class ChatMessageWorker(QObject):
    """Runs in a separate thread to send a chat message without freezing the GUI."""
    finished = Signal()
    error = Signal(str)
    def __init__(self, game_title: str, hotkey_pressed: str, message: str):
        super().__init__()
        self.game_title = game_title
        self.hotkey_pressed = hotkey_pressed
        self.message = message
    def run(self):
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                self.error.emit(f"Window '{self.game_title}' not found")
                return
            # No need to set foreground, pyautogui handles it
            pyautogui.press('enter')
            pyautogui.write(self.message, interval=0.01)
            pyautogui.press('enter')
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

class AlignedTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, alignment=Qt.AlignmentFlag.AlignCenter):
        super().__init__(text)
        self.setTextAlignment(alignment)


class CustomTabBar(QWidget):
    tab_selected = Signal(int)
    def __init__(self, tab_names: list[str], tabs_per_row: int = 4):
        super().__init__()
        self.tab_names = tab_names
        self.tabs_per_row = tabs_per_row
        self.buttons: List[QPushButton] = []
        self.current_index = -1
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(2)
        self._create_buttons()
    def _create_buttons(self):
        for i, name in enumerate(self.tab_names):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            self.buttons.append(button)
            row = i // self.tabs_per_row
            col = i % self.tabs_per_row
            self.layout.addWidget(button, row, col)
        if self.buttons:
            self._on_button_clicked(0)
    def _on_button_clicked(self, index: int):
        if self.current_index != index:
            if self.current_index != -1:
                self.buttons[self.current_index].setChecked(False)
            self.buttons[index].setChecked(True)
            self.current_index = index
            self.tab_selected.emit(index)
    def apply_style(self, theme_name: str, dark_mode: bool):
        if theme_name == "Black/Orange":
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #F0F0F0;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #FFA64D; }
                QPushButton:checked {
                    background-color: #FF7F50;
                    color: #F0F0F0;
                    border-color: #FF7F50;
                }
            """)
        elif dark_mode:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #EAEAEA;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #4682B4; }
                QPushButton:checked {
                    background-color: #1E90FF;
                    color: #EAEAEA;
                    border-color: #4169E1;
                }
            """)
        elif theme_name == "White/Blue":
            self.setStyleSheet("""
                QPushButton {
                    background-color: #87CEEB;
                    border: 1px solid #4682B4;
                    padding: 8px;
                    border-radius: 6px;
                    color: #000080;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #87CEFA; }
                QPushButton:checked {
                    background-color: #4682B4;
                    color: #F0F8FF;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #FFC0CB;
                    border: 1px solid #E6A8B8;
                    padding: 8px;
                    border-radius: 6px;
                    color: #2E3440;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #F6B3F5; }
                QPushButton:checked {
                    background-color: #DB7093;
                    color: #2E3440;
                }
            """)


class SimpleWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Theme state
        self.current_theme_index = 0
        self.last_tab_index = 0
        self.custom_theme_enabled = False
        self.custom_theme = {
            "bg": "#121212",
            "fg": "#F0F0F0",
            "accent": "#FF7F50"
        }

        self.old_pos = None
        self.all_lobbies = []
        self.thread = None # type: ignore
        self.hotkey_ids = {}            # {hotkey_str: id from keyboard.add_hotkey}
        self.is_sending_message = False
        self.game_title = "Warcraft III"

        # Automation state flags
        self.automation_timers = {}
        self.is_automation_running = False
        self.automation_settings = {} # To hold loaded settings
        self.custom_action_running = False
        self.theme_previews = []
        self.message_hotkeys = {}       # {hotkey_str: message_str}
        self.watchlist = ["hellfire", "rpg"] # Default, will be overwritten by load_settings
        self.play_sound_on_found = False # Default, will be overwritten by load_settings


        self.setWindowTitle("Hellfire Helper")
        # Load settings first, which will overwrite the defaults above if a file exists
        self.load_settings()

        # Initialize media player for custom sounds
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(700, 800)

        self.themes = [
            {"name": "Black/Orange", "style": DARK_STYLE, "preview_color": "#FF7F50", "is_dark": True},
            {"name": "White/Pink", "style": LIGHT_STYLE, "preview_color": "#FFC0CB", "is_dark": False},
            {"name": "Black/Blue", "style": FOREST_STYLE, "preview_color": "#1E90FF", "is_dark": True},
            {"name": "White/Blue", "style": OCEAN_STYLE, "preview_color": "#87CEEB", "is_dark": False},
        ]

        self.is_fetching_lobbies = False # Add a flag to prevent concurrent refreshes
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Title bar
        self.title_bar = QWidget()
        self.title_bar.setObjectName("CustomTitleBar")
        self.title_bar.setFixedHeight(30)
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        left_spacer = QWidget(); left_spacer.setFixedSize(60, 30); left_spacer.setStyleSheet("background-color: transparent;")
        title_label = QLabel("<span style='color: #FF7F50;'>🔥</span> Hellfire Helper")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_button = QPushButton("_"); min_button.setFixedSize(30, 30); min_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("X"); close_button.setFixedSize(30, 30); close_button.clicked.connect(self.close)
        title_bar_layout.addWidget(left_spacer); title_bar_layout.addStretch(); title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch(); title_bar_layout.addWidget(min_button); title_bar_layout.addWidget(close_button)
        main_layout.addWidget(self.title_bar)

        # Tabs
        self.tab_names = ["Load", "Items", "Recipes", "Automation", "Hotkey", "Lobbies", "Settings", "Reset"]
        self.custom_tab_bar = CustomTabBar(self.tab_names, tabs_per_row=4)
        main_layout.addWidget(self.custom_tab_bar)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self.custom_tab_bar.tab_selected.connect(self.stacked_widget.setCurrentIndex)

        # Load tab
        load_tab_content = QWidget()
        load_layout = QVBoxLayout(load_tab_content)
        path_layout = QHBoxLayout()
        self.load_path_edit = QLineEdit(); self.load_path_edit.setPlaceholderText("Character save path...")
        self.load_path_edit.textChanged.connect(self.on_path_changed)
        browse_btn = QPushButton("Browse..."); browse_btn.clicked.connect(self.select_character_path)
        reset_path_btn = QPushButton("Reset Path"); reset_path_btn.clicked.connect(self.reset_character_path)
        path_layout.addWidget(self.load_path_edit); path_layout.addWidget(browse_btn); path_layout.addWidget(reset_path_btn)
        load_layout.addLayout(path_layout)
        action_layout = QHBoxLayout()
        load_char_btn = QPushButton("Load Character (F3)"); load_char_btn.clicked.connect(self.load_selected_character)
        refresh_chars_btn = QPushButton("Refresh"); refresh_chars_btn.clicked.connect(self.load_characters)
        action_layout.addWidget(load_char_btn); action_layout.addWidget(refresh_chars_btn); action_layout.addStretch()
        load_layout.addLayout(action_layout)
        content_layout = QHBoxLayout()
        self.char_list_box = QListWidget(); self.char_list_box.setFixedWidth(200)
        self.char_list_box.currentItemChanged.connect(self.show_character_file_contents)
        self.char_content_box = QTextEdit(); self.char_content_box.setReadOnly(True)
        self.char_content_box.setFontFamily("Consolas"); self.char_content_box.setFontPointSize(10)
        content_layout.addWidget(self.char_list_box); content_layout.addWidget(self.char_content_box)
        load_layout.addLayout(content_layout)
        self.stacked_widget.addWidget(load_tab_content)
        
        # Set initial path and load characters
        if not self.character_path:
            self.character_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
        self.load_path_edit.setText(self.character_path)

        # Items tab
        self.item_database = ItemDatabase()
        items_tab_content = QWidget()
        items_main_layout = QVBoxLayout(items_tab_content)
        items_controls_layout = QHBoxLayout()
        self.items_sub_tabs = QWidget(); self.items_sub_tabs_layout = QHBoxLayout(self.items_sub_tabs)
        self.items_sub_tabs_layout.setContentsMargins(0,0,0,0); self.items_sub_tabs_layout.setSpacing(5)
        self.item_tab_buttons = {}
        item_tab_names = ["All Items", "Drops", "Raid Items", "Vendor Items"]
        for i, name in enumerate(item_tab_names):
            btn = QPushButton(name); btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self.switch_items_sub_tab(idx))
            self.item_tab_buttons[i] = btn; self.items_sub_tabs_layout.addWidget(btn)
        self.items_search_box = QLineEdit(); self.items_search_box.setPlaceholderText("Search...")
        self.items_search_box.textChanged.connect(self.filter_current_item_view)
        items_controls_layout.addWidget(self.items_sub_tabs); items_controls_layout.addStretch(); items_controls_layout.addWidget(self.items_search_box)
        items_main_layout.addLayout(items_controls_layout)
        self.items_stacked_widget = QStackedWidget(); items_main_layout.addWidget(self.items_stacked_widget)
        self.all_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.drops_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.raid_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.vendor_table = self._create_item_table(["Item", "Unit", "Location"])
        self.items_stacked_widget.addWidget(self.all_items_table)
        self.items_stacked_widget.addWidget(self.drops_table)
        self.items_stacked_widget.addWidget(self.raid_items_table)
        self.items_stacked_widget.addWidget(self.vendor_table)
        self.switch_items_sub_tab(0)
        self.stacked_widget.addWidget(items_tab_content)

        # Recipes tab
        self.in_progress_recipes = {}
        self.material_list_data = {}
        recipes_tab_content = QWidget()
        recipes_main_layout = QVBoxLayout(recipes_tab_content)
        recipes_top_layout = QHBoxLayout()
        recipes_list_layout = QVBoxLayout()
        self.recipe_search_box = QLineEdit(); self.recipe_search_box.setPlaceholderText("Search Recipes...")
        self.recipe_search_box.textChanged.connect(self.filter_recipes_list)
        self.available_recipes_list = QListWidget()
        recipes_list_layout.addWidget(self.recipe_search_box); recipes_list_layout.addWidget(self.available_recipes_list)
        add_remove_layout = QVBoxLayout(); add_remove_layout.addStretch()
        add_recipe_btn = QPushButton("Add ->"); add_recipe_btn.clicked.connect(self.add_recipe_to_progress)
        remove_recipe_btn = QPushButton("<- Remove"); remove_recipe_btn.clicked.connect(self.remove_recipe_from_progress)
        reset_recipes_btn = QPushButton("Reset"); reset_recipes_btn.clicked.connect(self.reset_recipes)
        add_remove_layout.addWidget(add_recipe_btn); add_remove_layout.addWidget(remove_recipe_btn); add_remove_layout.addWidget(reset_recipes_btn); add_remove_layout.addStretch()
        self.in_progress_recipes_list = QListWidget()
        self.in_progress_recipes_list.itemChanged.connect(self.on_recipe_check_changed)
        recipes_top_layout.addLayout(recipes_list_layout); recipes_top_layout.addLayout(add_remove_layout); recipes_top_layout.addWidget(self.in_progress_recipes_list)
        recipes_main_layout.addLayout(recipes_top_layout)
        self.materials_table = QTableWidget()
        self.materials_table.setColumnCount(5)
        self.materials_table.setHorizontalHeaderLabels(["Material", "#", "Unit", "Location", "Checked"])
        self.materials_table.setColumnHidden(4, True)
        self.materials_table.verticalHeader().setVisible(False)
        self.materials_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.materials_table.setSortingEnabled(True)
        self.materials_table.itemChanged.connect(self.on_material_checked)
        recipes_main_layout.addWidget(self.materials_table)
        self.stacked_widget.addWidget(recipes_tab_content)

        # Automation tab
        automation_tab_content = QWidget()
        automation_main_layout = QHBoxLayout(automation_tab_content)

        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        automation_keys_group = QGroupBox("Key Automation"); automation_grid = QGridLayout()
        automationKeys = ["q", "w", "e", "r", "d", "f", "t", "z", "x", "Complete Quest"]
        self.automation_key_ctrls = {}; row, col = 0, 0

        # Use checkboxes for stable toggling; add numeric validators to intervals
        int_validator = QIntValidator(50, 600000, self)  # 50 ms to 10 min
        for key in automationKeys:
            chk = QCheckBox(key.upper() if key != "Complete Quest" else "Complete Quest")
            edit = QLineEdit("15000" if key == "Complete Quest" else "500"); edit.setFixedWidth(70); edit.setValidator(int_validator)
            automation_grid.addWidget(chk, row, col * 2); automation_grid.addWidget(edit, row, col * 2 + 1)
            self.automation_key_ctrls[key] = {"chk": chk, "edit": edit}
            col += 1
            if col > 1: col = 0; row += 1

        self.custom_action_btn = QCheckBox("Custom Action")
        self.custom_action_edit1 = QLineEdit("30000"); self.custom_action_edit1.setFixedWidth(70); self.custom_action_edit1.setValidator(int_validator)
        self.custom_action_edit2 = QLineEdit("-save x")
        custom_action_layout = QHBoxLayout()
        custom_action_layout.addWidget(self.custom_action_btn); custom_action_layout.addWidget(self.custom_action_edit1); custom_action_layout.addWidget(self.custom_action_edit2)
        automation_grid.addLayout(custom_action_layout, row, 0, 1, 4); row += 1

        automation_keys_group.setLayout(automation_grid); left_layout.addWidget(automation_keys_group)
        self.start_automation_btn = QPushButton("Start (F5)"); self.start_automation_btn.clicked.connect(self.toggle_automation)
        reset_automation_btn = QPushButton("Reset Automation"); reset_automation_btn.clicked.connect(self.reset_automation_settings)
        left_layout.addWidget(self.start_automation_btn)
        left_layout.addWidget(reset_automation_btn)
        interval_note = QLabel("Intervals are in ms. Example: 500 = 0.5s"); left_layout.addWidget(interval_note); left_layout.addStretch()

        # Placeholder right panel (message hotkeys section left as-is)
        msg_hotkey_group = QGroupBox("Custom Message Hotkeys"); right_layout = QVBoxLayout(msg_hotkey_group)
        self.msg_hotkey_table = QTableWidget(); self.msg_hotkey_table.setColumnCount(2)
        self.msg_hotkey_table.setHorizontalHeaderLabels(["Hotkey", "Message"])
        self.msg_hotkey_table.verticalHeader().setVisible(False)
        self.msg_hotkey_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.msg_hotkey_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.msg_hotkey_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
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
        self.add_msg_btn = QPushButton("Add"); self.add_msg_btn.clicked.connect(self.add_message_hotkey)
        self.update_msg_btn = QPushButton("Update"); self.update_msg_btn.clicked.connect(self.update_message_hotkey)
        self.delete_msg_btn = QPushButton("Delete"); self.delete_msg_btn.clicked.connect(self.delete_message_hotkey)
        msg_btn_layout.addWidget(self.add_msg_btn); msg_btn_layout.addWidget(self.update_msg_btn); msg_btn_layout.addWidget(self.delete_msg_btn)
        right_layout.addLayout(msg_btn_layout)

        automation_main_layout.addWidget(left_panel, 1)
        automation_main_layout.addWidget(msg_hotkey_group, 1)
        self.stacked_widget.addWidget(automation_tab_content)

        # Apply loaded automation settings after UI is created
        self.apply_automation_settings()

        # Hotkey tab placeholder
        hotkey_tab_content = QWidget()
        hotkey_layout = QVBoxLayout(hotkey_tab_content)
        hotkey_layout.addWidget(QLabel("This is the 'Hotkey' tab."))
        hotkey_layout.addStretch()
        self.stacked_widget.addWidget(hotkey_tab_content)

        # Lobbies tab
        lobbies_tab_content = QWidget()
        lobbies_layout = QVBoxLayout(lobbies_tab_content)
        controls_layout = QHBoxLayout()
        self.lobby_search_bar = QLineEdit(); self.lobby_search_bar.setPlaceholderText("Search by name or map…")
        self.lobby_search_bar.textChanged.connect(self.filter_lobbies); controls_layout.addWidget(self.lobby_search_bar)
        refresh_button = QPushButton("Refresh"); refresh_button.clicked.connect(self.refresh_lobbies); controls_layout.addWidget(refresh_button)
        lobbies_layout.addLayout(controls_layout)
        watchlist_group = QGroupBox("Watchlist"); watchlist_layout = QHBoxLayout()
        self.watchlist_widget = QListWidget(); self.watchlist_widget.addItems(self.watchlist)
        watchlist_layout.addWidget(self.watchlist_widget)
        watchlist_controls_layout = QVBoxLayout()
        self.watchlist_input = QLineEdit(); self.watchlist_input.setPlaceholderText("Add keyword...")
        watchlist_controls_layout.addWidget(self.watchlist_input)
        add_watchlist_button = QPushButton("Add"); add_watchlist_button.clicked.connect(self.add_to_watchlist)
        watchlist_controls_layout.addWidget(add_watchlist_button)
        remove_watchlist_button = QPushButton("Remove"); remove_watchlist_button.clicked.connect(self.remove_from_watchlist)
        watchlist_controls_layout.addWidget(remove_watchlist_button)

        self.sound_select_dropdown = QComboBox()
        self.sound_select_dropdown.addItems(["Ping 1", "Ping 2", "Ping 3"])
        watchlist_controls_layout.addWidget(self.sound_select_dropdown)
        watchlist_controls_layout.addStretch()

        watchlist_layout.addLayout(watchlist_controls_layout); watchlist_group.setLayout(watchlist_layout)
        lobbies_layout.addWidget(watchlist_group)
        self.lobbies_table = QTableWidget(); self.lobbies_table.setColumnCount(3)
        self.lobbies_table.setHorizontalHeaderLabels(["Name", "Map", "Players"])
        self.lobbies_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lobbies_table.verticalHeader().setVisible(False)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        lobbies_layout.addWidget(self.lobbies_table)
        self.stacked_widget.addWidget(lobbies_tab_content)

        # Settings tab (themes + custom theme picker)
        settings_tab_content = QWidget()
        settings_layout = QGridLayout(settings_tab_content)

        # Preset themes grid
        self.create_theme_grid(settings_layout)

        # Custom theme controls below presets
        row_below = (len(self.themes) - 1) // 4 + 1
        custom_box = QGroupBox("Custom theme")
        custom_layout = QGridLayout(custom_box)

        self.custom_enable_checkbox = QCheckBox("Enable custom theme (overrides preset)")
        self.custom_enable_checkbox.setChecked(self.custom_theme_enabled)
        self.custom_enable_checkbox.stateChanged.connect(self.on_custom_theme_toggled)
        custom_layout.addWidget(self.custom_enable_checkbox, 0, 0, 1, 3)

        self.bg_color_btn = QPushButton("Pick background")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color('bg'))
        self.fg_color_btn = QPushButton("Pick text")
        self.fg_color_btn.clicked.connect(lambda: self.pick_color('fg'))
        self.accent_color_btn = QPushButton("Pick accent")
        self.accent_color_btn.clicked.connect(lambda: self.pick_color('accent'))

        self.apply_custom_btn = QPushButton("Apply custom")
        self.apply_custom_btn.clicked.connect(self.apply_custom_theme)
        self.reset_custom_btn = QPushButton("Reset custom")
        self.reset_custom_btn.clicked.connect(self.reset_custom_theme_to_defaults)

        custom_layout.addWidget(self.bg_color_btn, 1, 0)
        custom_layout.addWidget(self.fg_color_btn, 1, 1)
        custom_layout.addWidget(self.accent_color_btn, 1, 2)
        custom_layout.addWidget(self.apply_custom_btn, 2, 0, 1, 2)
        custom_layout.addWidget(self.reset_custom_btn, 2, 2)

        settings_layout.addWidget(custom_box, row_below + 1, 0, 1, 4)

        self.stacked_widget.addWidget(settings_tab_content)

        # Reset tab
        reset_tab_content = QWidget()
        self.reset_layout = QVBoxLayout(reset_tab_content)
        warning_text = QLabel("This will reset the GUI to its default state.\nAre you sure you want to continue?")
        warning_text.setStyleSheet("font-weight: bold;")
        self.reset_layout.addWidget(warning_text, 0, Qt.AlignmentFlag.AlignCenter)
        reset_button = QPushButton("Reset GUI"); reset_button.clicked.connect(self.confirm_reset)
        self.reset_layout.addWidget(reset_button, 0, Qt.AlignmentFlag.AlignCenter)
        self.reset_layout.addStretch()
        self.stacked_widget.addWidget(reset_tab_content)

        # Finalize
        self.custom_tab_bar.tab_selected.connect(self.on_main_tab_selected)

        # Apply preset or custom theme depending on the flag
        self.custom_tab_bar._on_button_clicked(self.last_tab_index)
        self.refresh_lobbies()
        self.load_characters() # Load characters on startup
        self.refresh_timer = QTimer(self); self.refresh_timer.setInterval(30000); self.refresh_timer.timeout.connect(self.refresh_lobbies); self.refresh_timer.start()
        
        # Load saved recipes after the UI is fully initialized
        self.item_database.load_recipes()
        self.load_saved_recipes()

        # Register global hotkeys (F5 for automation, etc.)
        self.register_global_hotkeys()

        # Apply theme last to ensure all widgets are styled correctly on startup
        if self.custom_theme_enabled:
            self.apply_custom_theme()
        else:
            self.apply_theme(self.current_theme_index)

    # Core helpers
    def _create_item_table(self, headers: list) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        return table

    def create_theme_grid(self, layout: QGridLayout):
        row, col = 0, 0
        for i, theme in enumerate(self.themes):
            preview = ThemePreview(); preview.setFixedSize(150, 120)
            preview.setCursor(Qt.CursorShape.PointingHandCursor); preview.setObjectName("ThemePreview")
            preview.clicked.connect(lambda idx=i: self.apply_theme(idx))
            preview_layout = QVBoxLayout(preview)
            color_block = QLabel(); color_block.setFixedHeight(80)
            color_block.setStyleSheet(f"background-color: {theme['preview_color']}; border-radius: 5px;")
            name_label = QLabel(theme['name']); name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(color_block); preview_layout.addWidget(name_label)
            layout.addWidget(preview, row, col); self.theme_previews.append(preview)
            col += 1
            if col >= 4: col = 0; row += 1
        layout.setRowStretch(row + 1, 1); layout.setColumnStretch(col + 1, 1)

    # Title bar dragging
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.underMouse():
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None

    # Preset themes
    def apply_theme(self, theme_index: int):
        self.custom_theme_enabled = False  # disable custom when preset applied
        self.current_theme_index = theme_index
        theme = self.themes[theme_index]

        self.dark_mode = theme["is_dark"]
        self.setStyleSheet(theme["style"])
        self.custom_tab_bar.apply_style(theme['name'], self.dark_mode)
        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid #FF7F50;" if i == theme_index else "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}")

    # Custom theme builder
    def build_custom_stylesheet(self) -> str:
        bg = self.custom_theme["bg"]
        fg = self.custom_theme["fg"]
        accent = self.custom_theme["accent"]
        return f"""
        QWidget {{
            background-color: {bg};
            color: {fg};
            font-family: 'Segoe UI';
            font-size: 14px;
            outline: none;
        }}
        QMainWindow {{ background-color: {bg}; }}
        #CustomTitleBar {{
            background-color: {bg};
        }}
        #CustomTitleBar QLabel, #CustomTitleBar QPushButton {{
            background-color: transparent;
            border: none;
            color: {fg};
            font-size: 16px;
        }}
        #CustomTitleBar QPushButton:hover {{
            background-color: {accent};
        }}
        QPushButton {{
            background-color: {accent};
            border: 1px solid {fg};
            padding: 5px;
            border-radius: 6px;
            color: {bg};
        }}
        QHeaderView::section {{
            background-color: {bg};
            border: 1px solid {fg};
            color: {fg};
        }}
        QLineEdit, QTextEdit, QListWidget, QTableWidget {{
            background-color: {bg};
            color: {fg};
            border: 1px solid {fg};
        }}
        QGroupBox {{
            border: 1px solid {fg};
            margin-top: 6px;
        }}
        QGroupBox:title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
        }}
        QCheckBox::indicator {{
            border: 1px solid {fg};
            background-color: {bg};
        }}
        QComboBox#SoundSelect {{
            border: 1px solid {fg};
            background-color: {bg};
        }}
        """

    def apply_custom_theme(self):
        self.custom_theme_enabled = True
        self.setStyleSheet(self.build_custom_stylesheet())
        self.custom_tab_bar.setStyleSheet(f"""            
            QPushButton {{
                background-color: {self.custom_theme['bg']};
                border: 1px solid {self.custom_theme['fg']};
                padding: 8px;
                border-radius: 6px;
                color: {self.custom_theme['fg']};
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {self.custom_theme['accent']};
            }}
            QPushButton:checked {{
                background-color: {self.custom_theme['accent']};
                color: {self.custom_theme['bg']};
                border-color: {self.custom_theme['accent']};
            }}
        """)
        # Re-apply theme to ensure all child widgets get the new style
        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}")

    def on_custom_theme_toggled(self, state: int):
        self.custom_theme_enabled = state == Qt.CheckState.Checked
        
        if self.custom_theme_enabled:
            self.apply_custom_theme()
        else:
            self.apply_theme(self.current_theme_index)

    def pick_color(self, key: str):
        initial = QColor(self.custom_theme[key])
        color = QColorDialog.getColor(initial, self, f"Pick {key} color")
        if color.isValid():
            self.custom_theme[key] = color.name()
            if self.custom_theme_enabled:
                self.apply_custom_theme()


    def reset_custom_theme_to_defaults(self):
        """Resets custom theme colors to their default values."""
        self.custom_theme = {
            "bg": "#121212",
            "fg": "#F0F0F0",
            "accent": "#FF7F50"
        }
        if self.custom_theme_enabled:
            self.apply_custom_theme()

    def confirm_reset(self):
        confirm_box = QMessageBox(self); confirm_box.setWindowTitle("Confirm Reset")
        confirm_box.setText("Are you sure you want to reset the application?\nAll settings will be returned to their defaults.")
        confirm_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_box.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm_box.exec() == QMessageBox.StandardButton.Yes:
            self.reset_state()

    def reset_state(self):
        self.resize(700, 800)
        self.custom_theme_enabled = False
        self.custom_theme = {"bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50"}
        self.apply_theme(0)
        self.custom_tab_bar._on_button_clicked(0)
        self.watchlist = ["hellfire", "rpg"]
        self.watchlist_widget.clear(); self.watchlist_widget.addItems(self.watchlist)
        
        # Also reset recipes and automation settings
        self.in_progress_recipes.clear()
        self.in_progress_recipes_list.clear()
        self._rebuild_materials_table()
        self._reset_automation_ui()

        # Reset message hotkeys
        self.message_hotkeys.clear()
        self.load_message_hotkeys() # This will clear the table
        self.register_global_hotkeys() # This will unhook old and register new (just F5)

    # Settings
    def capture_message_hotkey(self):
        """Starts a worker thread to capture a key combination."""

        self.message_edit.setEnabled(False)
        self.hotkey_capture_btn.setText("[Press a key...]")
        self.hotkey_capture_btn.setEnabled(False)

        # Unhook all keyboard listeners to ensure a clean capture
        keyboard.unhook_all()

        self.capture_thread = QThread()
        self.capture_worker = HotkeyCaptureWorker()
        self.capture_worker.moveToThread(self.capture_thread)
        self.capture_thread.started.connect(self.capture_worker.run)
        self.capture_worker.hotkey_captured.connect(self.on_hotkey_captured)
        self.capture_thread.start()

    def on_hotkey_captured(self, hotkey: str):
        """Handles the captured hotkey string from the worker."""
        is_valid = True
        if '+' in hotkey:
            parts = hotkey.split('+')
            # Ensure modifiers are valid and not something like "2+3"
            for part in parts[:-1]:
                if part.strip().lower() not in keyboard.all_modifiers:
                    is_valid = False
                    break

        self.message_edit.setEnabled(True)

        if not is_valid or hotkey == 'esc':
            self.hotkey_capture_btn.setText("Click to set")
        else:
            self.hotkey_capture_btn.setText(hotkey)
        
        self.hotkey_capture_btn.setEnabled(True)

        # Stop the capture thread and re-register all hotkeys
        self.capture_thread.quit()
        self.capture_thread.wait()
        self.register_global_hotkeys()

    def load_message_hotkeys(self):
        """Populates the hotkey table from the loaded settings."""
        self.msg_hotkey_table.setRowCount(0)
        if not isinstance(self.message_hotkeys, dict):
            self.message_hotkeys = {}
        for hotkey, message in self.message_hotkeys.items():
            row_position = self.msg_hotkey_table.rowCount()
            self.msg_hotkey_table.insertRow(row_position)
            self.msg_hotkey_table.setItem(row_position, 0, QTableWidgetItem(hotkey))
            self.msg_hotkey_table.setItem(row_position, 1, QTableWidgetItem(message))

    def add_message_hotkey(self):
        """Adds a new hotkey and message to the system."""
        hotkey = self.hotkey_capture_btn.text()
        message = self.message_edit.text()

        if hotkey == "Click to set" or not message:
            QMessageBox.warning(self, "Input Error", "Please set a hotkey and enter a message.")
            return
        if hotkey in self.message_hotkeys:
            QMessageBox.warning(self, "Duplicate Hotkey", "This hotkey is already in use.")
            return

        self.message_hotkeys[hotkey] = message
        self.load_message_hotkeys()
        self.register_global_hotkeys() # Re-register all to include the new one

        # Reset UI
        self.hotkey_capture_btn.setText("Click to set")
        self.message_edit.clear()

    def update_message_hotkey(self):
        """Updates an existing hotkey."""
        selected_items = self.msg_hotkey_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to update.")
            return
        
        selected_row = selected_items[0].row()
        old_hotkey = self.msg_hotkey_table.item(selected_row, 0).text()

        new_hotkey = self.hotkey_capture_btn.text()
        new_message = self.message_edit.text()

        if new_hotkey == "Click to set" or not new_message:
            QMessageBox.warning(self, "Input Error", "Please set a new hotkey and enter a message.")
            return
        if new_hotkey != old_hotkey and new_hotkey in self.message_hotkeys:
            QMessageBox.warning(self, "Duplicate Hotkey", "The new hotkey is already in use.")
            return

        # Update the dictionary
        self.message_hotkeys.pop(old_hotkey, None)
        self.message_hotkeys[new_hotkey] = new_message
        
        self.load_message_hotkeys()
        self.register_global_hotkeys() # Re-register all

        # Reset UI
        self.hotkey_capture_btn.setText("Click to set")
        self.message_edit.clear()

    def delete_message_hotkey(self):
        """Deletes a selected hotkey."""
        selected_items = self.msg_hotkey_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to delete.")
            return
        
        selected_row = selected_items[0].row()
        hotkey_to_delete = self.msg_hotkey_table.item(selected_row, 0).text()

        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the hotkey '{hotkey_to_delete}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.message_hotkeys.pop(hotkey_to_delete, None)
            self.msg_hotkey_table.removeRow(selected_row)
            self.register_global_hotkeys() # Re-register to remove the deleted one

            # Reset UI
            self.hotkey_capture_btn.setText("Click to set")
            self.message_edit.clear()

    def send_chat_message(self, hotkey_pressed: str, message: str):
        """Sends a chat message if the game is active, otherwise passes the keypress through."""
        try:
            game_hwnd = win32gui.FindWindow(None, self.game_title)
            is_game_active = (win32gui.GetForegroundWindow() == game_hwnd)
        except Exception:
            is_game_active = False

        if not is_game_active:
            try: keyboard.send(hotkey_pressed)
            except Exception: pass
            return

        if self.is_sending_message: return
        self.is_sending_message = True

        worker = ChatMessageWorker(self.game_title, hotkey_pressed, message)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda: self.cleanup_chat_thread(thread, worker))
        worker.error.connect(lambda e: self.cleanup_chat_thread(thread, worker))
        thread.start()

    def cleanup_chat_thread(self, thread: QThread, worker: ChatMessageWorker):
        self.is_sending_message = False
        try: worker.deleteLater(); thread.quit(); thread.wait(); thread.deleteLater()
        except Exception: pass

    def load_settings(self):
        """Loads settings from a JSON file."""
        settings_path = os.path.join(get_base_path(), "settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    self.current_theme_index = settings.get("theme_index", 0)
                    self.last_tab_index = settings.get("last_tab_index", 0)
                    self.character_path = settings.get("character_path", "")
                    self.message_hotkeys = settings.get("message_hotkeys", {})
                    self.custom_theme_enabled = settings.get("custom_theme_enabled", False)
                    self.automation_settings = settings.get("automation", {})
                    self.custom_theme = settings.get("custom_theme", {"bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50"})
                    self.watchlist = settings.get("watchlist", ["hellfire", "rpg"])
                    self.play_sound_on_found = settings.get("play_sound_on_found", False)
        except (IOError, json.JSONDecodeError):
            self.current_theme_index = 0
            self.last_tab_index = 0
            self.character_path = ""
            self.message_hotkeys = {}
            self.custom_theme_enabled = False
            self.play_sound_on_found = False
            self.custom_theme = {"bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50"}
            self.automation_settings = {}
            self.watchlist = ["hellfire", "rpg"]

    def apply_automation_settings(self):
        """Applies loaded automation settings to the UI controls."""
        if not self.automation_settings:
            return

        key_settings = self.automation_settings.get("keys", {})
        for key, settings in key_settings.items():
            if key in self.automation_key_ctrls:
                self.automation_key_ctrls[key]["chk"].setChecked(settings.get("checked", False)) # type: ignore
                self.automation_key_ctrls[key]["edit"].setText(settings.get("interval", "500"))

        custom_settings = self.automation_settings.get("custom", {})
        if custom_settings:
            self.custom_action_btn.setChecked(custom_settings.get("checked", False))
            self.custom_action_edit1.setText(custom_settings.get("interval", "30000"))
            self.custom_action_edit2.setText(custom_settings.get("message", "-save x"))




    def load_saved_recipes(self):
        """Loads and populates the in-progress recipes from settings."""
        settings_path = os.path.join(get_base_path(), "settings.json")
        if not os.path.exists(settings_path): return
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            saved_recipes = settings.get("in_progress_recipes", [])
            for recipe_name in saved_recipes:
                self._add_recipe_by_name(recipe_name)

    def save_settings(self):
        """Saves current settings to a JSON file."""
        settings_path = os.path.join(get_base_path(), "settings.json")
        settings = {
            "theme_index": self.current_theme_index,
            "last_tab_index": self.stacked_widget.currentIndex(),
            "character_path": self.character_path,
            "message_hotkeys": self.message_hotkeys,
            "custom_theme_enabled": self.custom_theme_enabled,
            "custom_theme": self.custom_theme,
            "in_progress_recipes": [self.in_progress_recipes_list.item(i).text() for i in range(self.in_progress_recipes_list.count())],
            "automation": {
                "keys": {
                    key: {"checked": ctrls["chk"].isChecked(), "interval": ctrls["edit"].text()}
                    for key, ctrls in self.automation_key_ctrls.items()
                },
                "custom": {
                    "checked": self.custom_action_btn.isChecked(),
                    "interval": self.custom_action_edit1.text(),
                    "message": self.custom_action_edit2.text()
                }
            },
            "watchlist": self.watchlist,
            "play_sound_on_found": self.lobby_placeholder_checkbox.isChecked()
        }
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)

    # Watchlist
    def load_watchlist(self):
        """Loads the watchlist from settings. This is now handled by load_settings()."""
        # This method is kept for compatibility but logic is in load_settings()
        # The watchlist is loaded with other settings at startup.
        self.watchlist_widget.clear()
        self.watchlist_widget.addItems(self.watchlist)
    def add_to_watchlist(self):
        keyword = self.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.watchlist_widget.addItem(keyword)
            self.watchlist_input.clear()
            self.filter_lobbies(self.lobby_search_bar.text())
    def remove_from_watchlist(self):
        selected_items = self.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.watchlist_widget.takeItem(self.watchlist_widget.row(item))
        self.filter_lobbies(self.lobby_search_bar.text())

    # Items
    def filter_current_item_view(self):
        query = self.items_search_box.text().lower()
        current_index = self.items_stacked_widget.currentIndex()
        data_source, table_widget = [], None
        if current_index == 0: data_source, table_widget = self.item_database.all_items_data, self.all_items_table
        elif current_index == 1: data_source, table_widget = self.item_database.drops_data, self.drops_table
        elif current_index == 2: data_source, table_widget = self.item_database.raid_data, self.raid_items_table
        elif current_index == 3: data_source, table_widget = self.item_database.vendor_data, self.vendor_table
        if not table_widget: return
        table_widget.setSortingEnabled(False); table_widget.setRowCount(0)
        filtered_data = [item for item in data_source if query in item.get("Item", "").lower() or
                         query in item.get("Unit", "").lower() or query in item.get("Location", "").lower()]
        headers = [table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())]
        for row, item_data in enumerate(filtered_data):
            table_widget.insertRow(row)
            for col, header in enumerate(headers):
                table_widget.setItem(row, col, QTableWidgetItem(item_data.get(header, "")))
        table_widget.setSortingEnabled(True)

    def switch_items_sub_tab(self, index: int):
        for i, btn in self.item_tab_buttons.items():
            btn.setChecked(i == index)
        self.items_stacked_widget.setCurrentIndex(index)
        self.items_search_box.setVisible(True)
        if index == 0 and not self.item_database.all_items_data:
            self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
        elif index == 1 and not self.item_database.drops_data:
            self.item_database.drops_data = self.item_database._load_item_data_from_folder("Drops")
        elif index == 2 and not self.item_database.raid_data:
            self.item_database.raid_data = self.item_database._load_item_data_from_folder("Raid Items")
        elif index == 3 and not self.item_database.vendor_data:
            self.item_database.vendor_data = self.item_database._load_item_data_from_folder("Vendor Items")
        self.filter_current_item_view()

    # Recipes
    def filter_recipes_list(self):
        if not self.item_database.recipes_data:
            self.item_database.load_recipes()
        query = self.recipe_search_box.text().lower()
        self.available_recipes_list.clear()
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                item.setData(Qt.ItemDataRole.UserRole, recipe)
                self.available_recipes_list.addItem(item)

    def add_recipe_to_progress(self):
        """Adds a recipe to the 'in-progress' list from the UI selection."""
        selected_item = self.available_recipes_list.currentItem()
        if not selected_item:
            return False
        if self._add_recipe_by_name(selected_item.text()):
            self._rebuild_materials_table()
            return True
        return False

    def _add_recipe_by_name(self, recipe_name: str):
        """Helper to add a recipe to the in-progress list by its name."""
        if recipe_name in self.in_progress_recipes:
            # Don't show a message box when loading from settings, just skip.
            # QMessageBox.information(self, "Duplicate", "This recipe is already in the 'In Progress' list.")
            return False

        # Find the full recipe object from the database
        recipe = next((r for r in self.item_database.recipes_data if r["name"] == recipe_name), None)
        if not recipe:
            return False # Recipe not found in database

        recipe_name = recipe["name"]
        self.in_progress_recipes[recipe_name] = recipe
        item = QListWidgetItem(recipe_name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        # No need to connect a signal here, the list widget's itemChanged handles it
        self.in_progress_recipes_list.addItem(item)
        return True

    def remove_recipe_from_progress(self):
        selected_item = self.in_progress_recipes_list.currentItem()
        if not selected_item:
            return
        recipe_name = selected_item.text()
        recipe = self.in_progress_recipes.pop(recipe_name, None)
        if recipe:
            self.in_progress_recipes_list.takeItem(self.in_progress_recipes_list.row(selected_item))
            self._rebuild_materials_table()

    def reset_recipes(self):
        """Clears all in-progress recipes and the materials list."""
        confirm = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to clear all in-progress recipes?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.in_progress_recipes.clear()
            self.in_progress_recipes_list.clear()
            self._rebuild_materials_table()

    def _reset_automation_ui(self):
        """Resets the automation UI controls to their default values without confirmation."""
        self.reset_automation_settings(confirm=False)


    def _add_component_to_materials(self, component_str: str):
        match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
        if match:
            name, quantity = match.group(1).strip(), int(match.group(2))
        else:
            name, quantity = component_str.strip(), 1
        if name in self.material_list_data:
            self.material_list_data[name]["#"] += quantity
        else:
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
        """Clears and repopulates the materials table based on the internal data dictionary and checked recipes."""
        # Disconnect signals to prevent loops during update
        self.materials_table.setSortingEnabled(False)
        self.materials_table.itemChanged.disconnect(self.on_material_checked)
        self.materials_table.setRowCount(0)
        
        # Determine which recipes to calculate materials for
        checked_recipe_names = []
        for i in range(self.in_progress_recipes_list.count()):
            item = self.in_progress_recipes_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_recipe_names.append(item.text())
        
        # If no recipes are checked, use all recipes in the "In Progress" list
        target_recipe_names = checked_recipe_names if checked_recipe_names else [self.in_progress_recipes_list.item(i).text() for i in range(self.in_progress_recipes_list.count())]
        
        # Calculate materials needed for the target recipes
        materials_to_display = {}
        for recipe_name in target_recipe_names:
            recipe = self.in_progress_recipes.get(recipe_name)
            if not recipe: continue
            
            for component_str in recipe["components"]:
                match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
                name, quantity = (match.group(1).strip(), int(match.group(2))) if match else (component_str.strip(), 1)
                
                if name in materials_to_display:
                    materials_to_display[name]["#"] += quantity
                else:
                    drop_info = next((item for item in self.item_database.all_items_data if item["Item"].lower() == name.lower()), None)
                    materials_to_display[name] = {"Material": name, "#": quantity, "Unit": drop_info["Unit"] if drop_info else "?", "Location": drop_info["Location"] if drop_info else "?"}
        
        # Populate the table
        for row, item_data in enumerate(materials_to_display.values()):
            self.materials_table.insertRow(row)
            material_item = QTableWidgetItem(item_data["Material"])
            self.materials_table.setItem(row, 0, material_item)
            self.materials_table.setItem(row, 1, QTableWidgetItem(str(item_data["#"])))
            self.materials_table.setItem(row, 2, QTableWidgetItem(item_data["Unit"]))
            self.materials_table.setItem(row, 3, QTableWidgetItem(item_data["Location"]))
            self.materials_table.setItem(row, 4, QTableWidgetItem("0"))
        
        # Reconnect signals and enable sorting
        self.materials_table.itemChanged.connect(self.on_material_checked)
        self.materials_table.setSortingEnabled(True)

    def on_material_checked(self, item: QTableWidgetItem):
        if item.column() != 0: return
        is_checked = item.checkState() == Qt.CheckState.Checked
        color = QColor("gray") if is_checked else self.palette().color(self.foregroundRole())
        self.materials_table.itemChanged.disconnect(self.on_material_checked)
        for col in range(self.materials_table.columnCount()):
            table_item = self.materials_table.item(item.row(), col)
            if table_item: table_item.setForeground(color)
        sort_item = self.materials_table.item(item.row(), 4)
        if sort_item: sort_item.setText("1" if is_checked else "0")
        self.materials_table.setSortingEnabled(True)
        self.materials_table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.materials_table.itemChanged.connect(self.on_material_checked)

    def on_recipe_check_changed(self, item: QListWidgetItem):
        """Called when any recipe's check state changes to rebuild the material list."""
        # This handler is now connected to QListWidget.itemChanged
        self._rebuild_materials_table()

    # Character loading
    def on_path_changed(self, new_path: str):
        self.character_path = new_path
    def select_character_path(self):
        default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData")
        new_path = QFileDialog.getExistingDirectory(self, "Select the character data folder", dir=default_path)
        if new_path:
            self.load_path_edit.setText(new_path); self.load_characters()
    def reset_character_path(self):
        confirm_box = QMessageBox.question(self, "Confirm Reset", "Reset character path to default?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)
        if confirm_box == QMessageBox.StandardButton.Yes:
            default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
            self.load_path_edit.setText(default_path); self.load_characters()
    def load_characters(self):
        self.char_list_box.clear(); self.char_content_box.clear()
        if not self.character_path or not os.path.isdir(self.character_path):
            if self.character_path:
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
                    continue
        sorted_chars = sorted(char_files, key=lambda x: x["mod_time"], reverse=True)
        for char in sorted_chars:
            item = QListWidgetItem(char["name"])
            item.setData(Qt.ItemDataRole.UserRole, char["path"])
            self.char_list_box.addItem(item)
        if self.char_list_box.count() > 0:
            self.char_list_box.setCurrentRow(0)
    def show_character_file_contents(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if not current_item:
            self.char_content_box.clear(); return
        file_path = current_item.data(Qt.ItemDataRole.UserRole)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.char_content_box.setText(f.read())
        except (IOError, OSError) as e:
            self.char_content_box.setText(f"Error reading file: {e}")
    def load_selected_character(self):
        current_item = self.char_list_box.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Character Selected", "Please select a character from the list."); return
        char_name = current_item.text()
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                QMessageBox.critical(self, "Error", f"'{self.game_title}' window not found."); return
            win32gui.SetForegroundWindow(hwnd)
            pyautogui.press('enter'); pyautogui.write(f"-load {char_name}", interval=0.05); pyautogui.press('enter')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send command to game: {e}")

    # Lobbies
    def refresh_lobbies(self):
        if self.is_fetching_lobbies:
            return # Don't start a new refresh if one is already running
        self.is_fetching_lobbies = True

        self.lobbies_table.setRowCount(0); self.lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data..."); loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, loading_item); self.lobbies_table.setSpan(0, 0, 1, 3)
        self.thread = QThread(); self.worker = LobbyFetcher(); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_lobbies_fetched)
        self.worker.error.connect(self.on_lobbies_fetch_error)
        self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
    def on_lobbies_fetched(self, lobbies: list):
        current_watched_lobbies = set()
        self.is_fetching_lobbies = False # Reset the flag
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    current_watched_lobbies.add(lobby.get('name')); break
        if current_watched_lobbies and self.lobby_placeholder_checkbox.isChecked():
            self.play_notification_sound()
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobby_search_bar.text())
    def on_lobbies_fetch_error(self, error_message: str):
        self.is_fetching_lobbies = False # Reset the flag
        self.lobbies_table.setRowCount(1)
        self.lobbies_table.setSpan(0, 0, 1, self.lobbies_table.columnCount())
        error_item = QTableWidgetItem(f"Error: {error_message}")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, error_item)
    def filter_lobbies(self, query: str):
        self.lobbies_table.setRowCount(0); self.lobbies_table.setSortingEnabled(False)
        query = query.lower()
        filtered_lobbies = [l for l in self.all_lobbies if query in l.get('name', '').lower() or query in l.get('map', '').lower()]
        def is_watched(lobby):
            name = lobby.get('name', '').lower(); map_name = lobby.get('map', '').lower()
            return any(k in name or k in map_name for k in self.watchlist)
        sorted_lobbies = sorted(filtered_lobbies, key=is_watched, reverse=True)
        self.lobbies_table.setRowCount(len(sorted_lobbies))
        for row, lobby in enumerate(sorted_lobbies):
            lobby_name = lobby.get('name', '').lower(); lobby_map = lobby.get('map', '').lower()
            watched = any(k in lobby_name or k in lobby_map for k in self.watchlist)
            self.lobbies_table.setItem(row, 0, QTableWidgetItem(lobby.get('name', 'N/A')))
            self.lobbies_table.setItem(row, 1, QTableWidgetItem(lobby.get('map', 'N/A')))
            players = f"{lobby.get('slotsTaken', '?')}/{lobby.get('slotsTotal', '?')}"
            self.lobbies_table.setItem(row, 2, AlignedTableWidgetItem(players))
            if watched:
                for col in range(self.lobbies_table.columnCount()):
                    self.lobbies_table.item(row, col).setBackground(QColor("#3A5F0B"))
        self.lobbies_table.setSortingEnabled(True)

    # Tab select logic
    def on_main_tab_selected(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        tab_name = self.tab_names[index]
        if tab_name == "Items" and not self.item_database.all_items_data:
            self.switch_items_sub_tab(0) # Lazy load
        elif tab_name == "Lobbies":
            self.refresh_lobbies() # Refresh when tab is viewed
        elif tab_name == "Recipes":
            if not self.item_database.recipes_data: self.item_database.load_recipes()
            self.filter_recipes_list()
            self._rebuild_materials_table() # Rebuild materials when tab is viewed
        elif tab_name == "Automation":
            self.load_message_hotkeys()

    # --- Automation: AHK-style behavior ---
    def pause_all_automation(self):
        # Unhook message hotkeys temporarily to prevent them from firing
        for hk, hk_id in list(self.hotkey_ids.items()):
            if hk not in ['f5']: # Keep global toggle active
                try: keyboard.remove_hotkey(hk_id)
                except Exception: pass

        for timer in self.automation_timers.values():
            timer.stop()

    def resume_all_automation(self):
        # Re-register message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            if hotkey not in self.hotkey_ids:
                self.register_single_hotkey(hotkey, message)

        for timer in self.automation_timers.values():
            timer.start()

    def run_complete_quest(self):
        # If custom action is running, wait then retry
        if self.custom_action_running:
            QTimer.singleShot(2500, self.run_complete_quest)
            return
        # Pause QWERDFZX timers
        self.pause_all_automation()
        # Sequence: y -> 50ms -> e -> 50ms -> esc
        pyautogui.press('y')
        QTimer.singleShot(50, lambda: pyautogui.press('e'))
        QTimer.singleShot(100, lambda: pyautogui.press('esc'))
        # Resume after ~2s
        QTimer.singleShot(2100, self.resume_all_automation)

    def run_custom_action(self, message: str):
        # Highest priority, pauses everything including complete quest
        self.custom_action_running = True
        self.pause_all_automation()
        def type_message():
            pyautogui.press('enter')
            pyautogui.write(message, interval=0.03)
            pyautogui.press('enter')
        # Wait 2s, type, then wait 2s more and resume
        QTimer.singleShot(2000, type_message)
        QTimer.singleShot(4000, self._end_custom_action)

    def _end_custom_action(self):
        self.custom_action_running = False
        self.resume_all_automation()

    def _reset_automation_button_style(self):
        """Resets the automation button to its default theme color."""
        if self.custom_theme_enabled:
            accent_color = self.custom_theme.get("accent", "#FF7F50")
            text_color = self.custom_theme.get("bg", "#121212")
            self.start_automation_btn.setStyleSheet(f"background-color: {accent_color}; color: {text_color};")
        else:
            # For preset themes, setting an empty stylesheet is enough to revert.
            # However, to be explicit and robust:
            self.start_automation_btn.setStyleSheet("")

    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        if self.is_automation_running:
            self.start_automation_btn.setText("Stop (F5)")
            self.start_automation_btn.setStyleSheet("background-color: #B00000;")
            # Start timers
            for key, ctrls in self.automation_key_ctrls.items():
                if ctrls["chk"].isChecked():
                    interval_text = ctrls["edit"].text().strip()
                    if not interval_text:
                        continue
                    try:
                        interval = int(interval_text)
                        timer = QTimer(self)
                        if key == "Complete Quest":
                            timer.timeout.connect(self.run_complete_quest)
                        else:
                            # Raw key presses (no typing into chat)
                            timer.timeout.connect(lambda k=key: pyautogui.press(k))
                        timer.start(interval)
                        self.automation_timers[key] = timer
                    except ValueError:
                        QMessageBox.warning(self, "Invalid interval", f"Interval for '{key}' must be a number in ms.")
            # Custom Action timer
            if self.custom_action_btn.isChecked():
                interval_text = self.custom_action_edit1.text().strip()
                if interval_text:
                    try:
                        interval = int(interval_text)
                        message = self.custom_action_edit2.text()
                        timer = QTimer(self)
                        timer.timeout.connect(lambda msg=message: self.run_custom_action(msg))
                        timer.start(interval)
                        self.automation_timers["custom"] = timer
                    except ValueError:
                        QMessageBox.warning(self, "Invalid interval", "Interval for 'Custom Action' must be a number in ms.")
        else:
            self.start_automation_btn.setText("Start (F5)")
            self._reset_automation_button_style()
            for timer in self.automation_timers.values():
                timer.stop(); timer.deleteLater()
            self.automation_timers.clear()

    def reset_automation_settings(self, confirm=True):
        """Resets all automation settings in the UI to their defaults."""
        do_reset = False
        if not confirm:
            do_reset = True
        elif QMessageBox.question(self, "Confirm Reset", "Are you sure you want to reset all automation settings to their defaults?") == QMessageBox.StandardButton.Yes:
            do_reset = True
        if do_reset:
            # Reset key automation
            for key, ctrls in self.automation_key_ctrls.items():
                ctrls["chk"].setChecked(False)
                default_interval = "15000" if key == "Complete Quest" else "500"
                ctrls["edit"].setText(default_interval)
            # Reset custom action
            self.custom_action_btn.setChecked(False)
            self.custom_action_edit1.setText("30000")
            self.custom_action_edit2.setText("-save x")
    def register_global_hotkeys(self):
        """Registers all hotkeys, including global controls and custom messages."""
        keyboard.unhook_all()
        self.hotkey_ids.clear()

        # Register global F5 for automation toggle
        try:
            f5_id = keyboard.add_hotkey('f5', self.toggle_automation, suppress=True)
            self.hotkey_ids['f5'] = f5_id
        except Exception as e:
            print(f"Failed to register F5 hotkey: {e}")

        # Register all custom message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            self.register_single_hotkey(hotkey, message)

    def register_single_hotkey(self, hotkey: str, message: str):
        """Helper to register a single message hotkey."""
        try:
            hk_id = keyboard.add_hotkey(hotkey, lambda h=hotkey, msg=message: self.send_chat_message(h, msg), suppress=True)
            self.hotkey_ids[hotkey] = hk_id
        except (ValueError, ImportError) as e:
            print(f"Failed to register hotkey '{hotkey}': {e}")

    def play_notification_sound(self):
        """Plays a custom sound file (ping.mp3), with fallback to a system beep."""
        try:
            sound_file_path = os.path.join(get_base_path(), "contents", "ping.mp3")
            if os.path.exists(sound_file_path):
                self.player.setSource(QUrl.fromLocalFile(sound_file_path))
                self.player.play()
            else:
                QApplication.beep() # Fallback if ping.mp3 is missing
        except Exception:
            QApplication.beep()

    # Ensure timers are cleaned up on exit
    def closeEvent(self, event):
        self.save_settings() # Save all settings on exit
        try:
            for timer in self.automation_timers.values():
                timer.stop(); timer.deleteLater()
            self.automation_timers.clear()
        except Exception:
            pass
        keyboard.unhook_all() # Clean up all global listeners
        event.accept()


if __name__ == "__main__":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())