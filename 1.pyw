import sys
import requests
import json
import os
import re
from datetime import datetime
from typing import List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog, QTextEdit,
    QListWidgetItem
)
from PySide6.QtCore import Signal, Qt, QObject, QThread, QTimer
from PySide6.QtGui import QMouseEvent, QColor

import keyboard
import pyautogui  # type: ignore
import win32gui   # type: ignore


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
    hotkey_captured = Signal(str)
    def run(self):
        try:
            # Capture a single hotkey string, suppress so it doesn't leak into GUI
            hotkey = keyboard.read_hotkey(suppress=True)
            self.hotkey_captured.emit(hotkey)
        except Exception as e:
            print(f"Error capturing hotkey: {e}")


class AutomationWorker(QObject):
    finished = Signal()
    error = Signal(str)
    def __init__(self, game_title: str, action: str, message: str = ""):
        super().__init__()
        self.game_title = game_title
        self.action = action
        self.message = message
    def run(self):
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                print(f"'{self.game_title}' window not found.")
                return
            pyautogui.press('enter')
            pyautogui.write(self.message if self.action == "chat" else self.action, interval=0.05)
            pyautogui.press('enter')
        finally:
            self.finished.emit()


class ChatMessageWorker(QObject):
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
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
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
        self.setWindowTitle("Hellfire Helper")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(700, 800)

        self.current_theme_index = 0
        self.old_pos = None
        self.all_lobbies = []
        self.thread = None
        self.watchlist_file = "watchlist.json"
        self.watchlist = self.load_watchlist()
        self.character_path = ""
        self.previous_watched_lobbies = set()
        self.theme_previews = []
        self.message_hotkeys = {}       # {hotkey_str: message_str}
        self.hotkey_ids = {}            # {hotkey_str: id from keyboard.add_hotkey}
        self.is_sending_message = False
        self.game_title = "Warcraft III"

        self.themes = [
            {"name": "Black/Orange", "style": DARK_STYLE, "preview_color": "#FF7F50", "is_dark": True},
            {"name": "White/Pink", "style": LIGHT_STYLE, "preview_color": "#FFC0CB", "is_dark": False},
            {"name": "Black/Blue", "style": FOREST_STYLE, "preview_color": "#1E90FF", "is_dark": True},
            {"name": "White/Blue", "style": OCEAN_STYLE, "preview_color": "#87CEEB", "is_dark": False},
        ]

        self.load_settings()

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
        self.load_path_edit.setText(self.character_path); self.load_characters()
        self.stacked_widget.addWidget(load_tab_content)

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
        add_remove_layout.addWidget(add_recipe_btn); add_remove_layout.addWidget(remove_recipe_btn); add_remove_layout.addStretch()
        self.in_progress_recipes_list = QListWidget()
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
        self.automation_timers = {}
        self.is_automation_running = False
        automation_tab_content = QWidget()
        automation_main_layout = QHBoxLayout(automation_tab_content)

        left_panel = QWidget(); left_layout = QVBoxLayout(left_panel)
        automation_keys_group = QGroupBox("Key Automation"); automation_grid = QGridLayout()
        automationKeys = ["q", "w", "e", "r", "d", "f", "t", "z", "x", "Complete Quest"]
        self.automation_key_ctrls = {}; row, col = 0, 0
        for key in automationKeys:
            btn = QPushButton(key.upper() if key != "Complete Quest" else "Complete Quest"); btn.setCheckable(True)
            edit = QLineEdit("15000" if key == "Complete Quest" else "500"); edit.setFixedWidth(60)
            automation_grid.addWidget(btn, row, col * 2); automation_grid.addWidget(edit, row, col * 2 + 1)
            self.automation_key_ctrls[key] = {"btn": btn, "edit": edit}
            col += 1
            if col > 1: col = 0; row += 1
        self.custom_action_btn = QPushButton("Custom Action"); self.custom_action_btn.setCheckable(True)
        self.custom_action_edit1 = QLineEdit("30000"); self.custom_action_edit1.setFixedWidth(60)
        self.custom_action_edit2 = QLineEdit("-save x")
        custom_action_layout = QHBoxLayout()
        custom_action_layout.addWidget(self.custom_action_btn); custom_action_layout.addWidget(self.custom_action_edit1); custom_action_layout.addWidget(self.custom_action_edit2)
        automation_grid.addLayout(custom_action_layout, row, 0, 1, 4); row += 1
        automation_keys_group.setLayout(automation_grid); left_layout.addWidget(automation_keys_group)
        self.start_automation_btn = QPushButton("Start (F5)"); self.start_automation_btn.clicked.connect(self.toggle_automation)
        left_layout.addWidget(self.start_automation_btn)
        interval_note = QLabel("Interval delay default 0.5 seconds (500ms)"); left_layout.addWidget(interval_note); left_layout.addStretch()

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
        watchlist_controls_layout.addWidget(remove_watchlist_button); watchlist_controls_layout.addStretch()
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

        # Settings tab
        settings_tab_content = QWidget()
        settings_layout = QGridLayout(settings_tab_content)
        self.create_theme_grid(settings_layout)
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
        self.label = QLabel("This is a placeholder label.")

        self.custom_tab_bar.tab_selected.connect(self.on_main_tab_selected)

        # Initial setup
        self.load_message_hotkeys()
        self.on_main_tab_selected(0)
        self.apply_theme(self.current_theme_index)
        self.refresh_lobbies()
        self.refresh_timer = QTimer(self); self.refresh_timer.setInterval(30000); self.refresh_timer.timeout.connect(self.refresh_lobbies); self.refresh_timer.start()

        # Global hotkey for automation toggle
        self.register_global_hotkeys()

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

    # Themes
    def apply_theme(self, theme_index: int):
        self.current_theme_index = theme_index
        theme = self.themes[theme_index]
        self.dark_mode = theme["is_dark"]
        self.setStyleSheet(theme["style"])
        self.custom_tab_bar.apply_style(theme['name'], self.dark_mode)
        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid #FF7F50;" if i == theme_index else "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}")
        self.save_settings()
        self.update_materials_table_colors()

    def update_materials_table_colors(self):
        self.materials_table.itemChanged.disconnect(self.on_material_checked)
        for row in range(self.materials_table.rowCount()):
            is_checked = self.materials_table.item(row, 4).text() == "1"
            if not is_checked:
                new_color = self.palette().color(self.foregroundRole())
                for col in range(self.materials_table.columnCount()):
                    itm = self.materials_table.item(row, col)
                    if itm:
                        itm.setForeground(new_color)
        self.materials_table.itemChanged.connect(self.on_material_checked)

    def confirm_reset(self):
        confirm_box = QMessageBox(self); confirm_box.setWindowTitle("Confirm Reset")
        confirm_box.setText("Are you sure you want to reset the application?\nAll settings will be returned to their defaults.")
        confirm_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_box.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm_box.exec() == QMessageBox.StandardButton.Yes:
            self.reset_state()

    def reset_state(self):
        self.resize(700, 800)
        self.label.setText("Hello! Click the button.")
        self.apply_theme(0)
        self.custom_tab_bar._on_button_clicked(0)
        self.watchlist = self.load_watchlist()
        self.watchlist_widget.clear(); self.watchlist_widget.addItems(self.watchlist)
        self.save_settings()

    # Settings persistence
    def load_settings(self):
        try:
            if os.path.exists("settings.json"):
                with open("settings.json", 'r') as f:
                    settings = json.load(f)
                    self.current_theme_index = settings.get("theme_index", 0)
                    self.character_path = settings.get("character_path", "")
                    self.message_hotkeys = settings.get("message_hotkeys", {})
        except (IOError, json.JSONDecodeError):
            self.current_theme_index = 0
            self.character_path = ""
            self.message_hotkeys = {}
    def save_settings(self):
        settings = {
            "theme_index": self.current_theme_index,
            "character_path": self.character_path,
            "message_hotkeys": self.message_hotkeys
        }
        with open("settings.json", 'w') as f:
            json.dump(settings, f, indent=4)

    # Watchlist
    def load_watchlist(self):
        try:
            if os.path.exists(self.watchlist_file):
                with open(self.watchlist_file, 'r') as f:
                    return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading watchlist: {e}")
        return ["legion", "hellgate"]
    def save_watchlist(self):
        with open(self.watchlist_file, 'w') as f:
            json.dump(self.watchlist, f, indent=4)
    def add_to_watchlist(self):
        keyword = self.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.watchlist_widget.addItem(keyword)
            self.watchlist_input.clear()
            self.save_watchlist()
            self.filter_lobbies(self.lobby_search_bar.text())
    def remove_from_watchlist(self):
        selected_items = self.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.watchlist_widget.takeItem(self.watchlist_widget.row(item))
        self.save_watchlist()
        self.filter_lobbies(self.lobby_search_bar.text())

    # Recipes
    def filter_recipes_list(self):
        query = self.recipe_search_box.text().lower()
        self.available_recipes_list.clear()
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                item.setData(Qt.ItemDataRole.UserRole, recipe)
                self.available_recipes_list.addItem(item)
    def add_recipe_to_progress(self):
        selected_item = self.available_recipes_list.currentItem()
        if not selected_item: return
        recipe = selected_item.data(Qt.ItemDataRole.UserRole)
        recipe_name = recipe["name"]
        if recipe_name in self.in_progress_recipes:
            QMessageBox.information(self, "Duplicate", "This recipe is already in the 'In Progress' list.")
            return
        self.in_progress_recipes[recipe_name] = recipe
        self.in_progress_recipes_list.addItem(recipe_name)
        for component_str in recipe["components"]:
            self._add_component_to_materials(component_str)
        self._rebuild_materials_table()
    def remove_recipe_from_progress(self):
        selected_item = self.in_progress_recipes_list.currentItem()
        if not selected_item: return
        recipe_name = selected_item.text()
        recipe = self.in_progress_recipes.pop(recipe_name, None)
        if recipe:
            for component_str in recipe["components"]:
                self._remove_component_from_materials(component_str)
        self.in_progress_recipes_list.takeItem(self.in_progress_recipes_list.row(selected_item))
        self._rebuild_materials_table()
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
        self.materials_table.setSortingEnabled(False)
        self.materials_table.setRowCount(0)
        for row, item_data in enumerate(self.material_list_data.values()):
            self._add_row_to_materials_table(row, item_data)
    def _add_row_to_materials_table(self, row_num, item_data):
        self.materials_table.insertRow(row_num)
        material_item = QTableWidgetItem(item_data["Material"])
        material_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        material_item.setCheckState(Qt.CheckState.Unchecked)
        self.materials_table.setItem(row_num, 0, material_item)
        quantity_item = AlignedTableWidgetItem(str(item_data["#"]))
        self.materials_table.setItem(row_num, 1, quantity_item)
        self.materials_table.setItem(row_num, 2, QTableWidgetItem(item_data["Unit"]))
        self.materials_table.setItem(row_num, 3, QTableWidgetItem(item_data["Location"]))
        checked_item = QTableWidgetItem("0")
        self.materials_table.setItem(row_num, 4, checked_item)
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

    # Character loading
    def on_path_changed(self, new_path: str):
        self.character_path = new_path; self.save_settings()
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
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    current_watched_lobbies.add(lobby.get('name')); break
        newly_found = current_watched_lobbies - self.previous_watched_lobbies
        if newly_found: QApplication.beep()
        self.previous_watched_lobbies = current_watched_lobbies
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobby_search_bar.text())
    def on_lobbies_fetch_error(self, error_message: str):
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
        if self.tab_names[index] == "Items" and not self.item_database.all_items_data:
            self.switch_items_sub_tab(0)
        elif self.tab_names[index] == "Lobbies":
            self.refresh_lobbies()
        elif self.tab_names[index] == "Recipes" and not self.item_database.recipes_data:
            self.item_database.load_recipes(); self.filter_recipes_list()
        elif self.tab_names[index] == "Automation":
            self.load_message_hotkeys()

    # Automation helpers
    def _run_automation_action(self, action, message=""):
        worker = AutomationWorker(self.game_title, action, message)
        thread = QThread(); worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        if self.is_automation_running:
            self.start_automation_btn.setText("Stop (F5)")
            self.start_automation_btn.setStyleSheet("background-color: #B00000;")
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
            self.start_automation_btn.setText("Start (F5)"); self.start_automation_btn.setStyleSheet("")
            for timer in self.automation_timers.values():
                timer.stop(); timer.deleteLater()
            self.automation_timers.clear()

    # Hotkey capture and registration
    def capture_message_hotkey(self):
        # Disable message input during capture
        self.message_edit.setEnabled(False)
        self.hotkey_capture_btn.setText("[Press a key...]")
        self.hotkey_capture_btn.setEnabled(False)

        # Clear hooks to ensure clean capture
        keyboard.unhook_all()

        self.capture_thread = QThread()
        self.capture_worker = HotkeyCaptureWorker()
        self.capture_worker.moveToThread(self.capture_thread)
        self.capture_thread.started.connect(self.capture_worker.run)
        self.capture_worker.hotkey_captured.connect(self.on_hotkey_captured)
        self.capture_thread.start()

    def on_hotkey_captured(self, hotkey: str):
        # Validate combos: modifiers + key; avoid nonsense combos like "2+3"
        is_valid = True
        if '+' in hotkey:
            parts = hotkey.split('+')
            for part in parts[:-1]:
                if part.strip().lower() not in keyboard.all_modifiers:
                    is_valid = False
                    break

        # Re-enable message input
        self.message_edit.setEnabled(True)

        if not is_valid or hotkey == 'esc':
            # Reset capture button on invalid or Escape
            self.hotkey_capture_btn.setText("Click to set")
            self.hotkey_capture_btn.setEnabled(True)
        else:
            self.hotkey_capture_btn.setText(hotkey)
            self.hotkey_capture_btn.setEnabled(True)

        # Stop capture thread and re-register saved hotkeys
        self.capture_thread.quit()
        self.capture_thread.wait()
        self.register_all_message_hotkeys()

    def load_message_hotkeys(self):
        self.msg_hotkey_table.setRowCount(0)
        if not isinstance(self.message_hotkeys, dict):
            self.message_hotkeys = {}
        for hotkey, message in self.message_hotkeys.items():
            row_position = self.msg_hotkey_table.rowCount()
            self.msg_hotkey_table.insertRow(row_position)
            self.msg_hotkey_table.setItem(row_position, 0, QTableWidgetItem(hotkey))
            self.msg_hotkey_table.setItem(row_position, 1, QTableWidgetItem(message))
        self.register_all_message_hotkeys()

    def add_message_hotkey(self):
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

        # Reset capture UI so it doesn't reuse the previous hotkey (e.g., "2+3")
        self.hotkey_capture_btn.setText("Click to set")
        self.hotkey_capture_btn.setEnabled(True)
        self.message_edit.clear()

    def update_message_hotkey(self):
        selected_items = self.msg_hotkey_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to update.")
            return
        selected_row = selected_items[0].row()
        old_hotkey = self.msg_hotkey_table.item(selected_row, 0).text()

        new_hotkey = self.hotkey_capture_btn.text()
        new_message = self.message_edit.text()

        if new_hotkey == "Click to set" or not new_message:
            QMessageBox.warning(self, "Input Error", "Please set a hotkey and enter a message.")
            return
        if new_hotkey != old_hotkey and new_hotkey in self.message_hotkeys:
            QMessageBox.warning(self, "Duplicate Hotkey", "The new hotkey is already in use.")
            return

        # Remove old binding
        if old_hotkey in self.hotkey_ids:
            try:
                keyboard.remove_hotkey(self.hotkey_ids[old_hotkey])
            except Exception:
                pass
            self.hotkey_ids.pop(old_hotkey, None)

        # Update store
        self.message_hotkeys.pop(old_hotkey, None)
        self.message_hotkeys[new_hotkey] = new_message
        self.save_settings()
        self.load_message_hotkeys()

        # Reset capture button
        self.hotkey_capture_btn.setText("Click to set")
        self.hotkey_capture_btn.setEnabled(True)
        self.message_edit.clear()

    def delete_message_hotkey(self):
        selected_items = self.msg_hotkey_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to delete.")
            return
        selected_row = selected_items[0].row()
        hotkey_to_delete = self.msg_hotkey_table.item(selected_row, 0).text()

        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the hotkey '{hotkey_to_delete}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            if hotkey_to_delete in self.hotkey_ids:
                try:
                    keyboard.remove_hotkey(self.hotkey_ids[hotkey_to_delete])
                except Exception:
                    pass
                self.hotkey_ids.pop(hotkey_to_delete, None)
            self.message_hotkeys.pop(hotkey_to_delete, None)
            self.save_settings()
            self.msg_hotkey_table.removeRow(selected_row)

            # Reset capture button
            self.hotkey_capture_btn.setText("Click to set")
            self.hotkey_capture_btn.setEnabled(True)
            self.message_edit.clear()

    def register_global_hotkeys(self):
        try:
            f5_id = keyboard.add_hotkey('f5', self.toggle_automation, suppress=True)
            self.hotkey_ids['f5'] = f5_id
        except Exception as e:
            print(f"Failed to register F5 hotkey: {e}")

    def register_all_message_hotkeys(self):
        # Remove previous message hotkeys only (preserve global F5)
        for hk, hk_id in list(self.hotkey_ids.items()):
            if hk != 'f5':
                try: keyboard.remove_hotkey(hk_id)
                except Exception: pass
                self.hotkey_ids.pop(hk, None)

        # Register all message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            def callback(h=hotkey, msg=message):
                self.send_chat_message(h, msg)
            try:
                hk_id = keyboard.add_hotkey(hotkey, callback, suppress=True)
                self.hotkey_ids[hotkey] = hk_id
            except Exception as e:
                print(f"Failed to register hotkey '{hotkey}': {e}")

    def send_chat_message(self, hotkey_pressed: str, message: str):
        # If game not active, forward the key back to the OS
        try:
            game_hwnd = win32gui.FindWindow(None, self.game_title)
            is_game_active = (win32gui.GetForegroundWindow() == game_hwnd)
        except Exception:
            is_game_active = False

        if not is_game_active:
            try: keyboard.send(hotkey_pressed)
            except Exception: pass
            return

        if self.is_sending_message:
            return
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
        try: worker.deleteLater()
        except Exception: pass
        try:
            thread.quit(); thread.wait(); thread.deleteLater()
        except Exception: pass


if __name__ == "__main__":
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())