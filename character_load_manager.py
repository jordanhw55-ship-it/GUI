import os
from PySide6.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem

try:
    import win32gui
    import pyautogui
except ImportError:
    win32gui = None
    pyautogui = None

class CharacterLoadManager:
    """Manages all logic for the Character Load tab."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.load_tab = main_window.load_tab
        self.game_title = main_window.game_title

        # The character path is now managed here
        self.character_path = self.main_window.settings_manager.get("character_path")
        if not self.character_path:
            self.character_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")

        self._connect_signals()
        self.load_tab.load_path_edit.setText(self.character_path)
        self.load_characters()

    def _connect_signals(self):
        """Connects all UI signals for the load tab to the manager's methods."""
        self.load_tab.load_path_edit.textChanged.connect(self.on_path_changed)
        self.load_tab.browse_btn.clicked.connect(self.select_character_path)
        self.load_tab.reset_path_btn.clicked.connect(self.reset_character_path)
        self.load_tab.load_char_btn.clicked.connect(self.load_selected_character)
        self.load_tab.refresh_chars_btn.clicked.connect(self.load_characters)
        self.load_tab.char_list_box.currentItemChanged.connect(self.show_character_file_contents)

    def on_path_changed(self, new_path: str):
        """Updates the character path when the user edits the line edit."""
        self.character_path = new_path

    def select_character_path(self):
        """Opens a dialog to select the character data folder."""
        default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData")
        new_path = QFileDialog.getExistingDirectory(self.main_window, "Select the character data folder", dir=default_path)
        if new_path:
            self.load_tab.load_path_edit.setText(new_path)
            self.load_characters()

    def reset_character_path(self):
        """Resets the character path to its default location."""
        confirm_box = QMessageBox.question(self.main_window, "Confirm Reset", "Reset character path to default?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)
        if confirm_box == QMessageBox.StandardButton.Yes:
            default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
            self.load_tab.load_path_edit.setText(default_path)
            self.load_characters()

    def load_characters(self):
        """Loads and displays character files from the set path."""
        self.load_tab.char_list_box.clear()
        self.load_tab.char_content_box.clear()
        if not self.character_path or not os.path.isdir(self.character_path):
            if self.character_path:
                QMessageBox.warning(self.main_window, "Error", f"Character save directory not found:\n{self.character_path}")
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
            self.load_tab.char_list_box.addItem(item)
        if self.load_tab.char_list_box.count() > 0:
            self.load_tab.char_list_box.setCurrentRow(0)

    def show_character_file_contents(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        """Displays the content of the selected character file."""
        if not current_item:
            self.load_tab.char_content_box.clear()
            return
        file_path = current_item.data(Qt.ItemDataRole.UserRole)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.load_tab.char_content_box.setText(f.read())
        except (IOError, OSError) as e:
            self.load_tab.char_content_box.setText(f"Error reading file: {e}")

    def load_selected_character(self):
        """Sends the '-load' command for the selected character to the game."""
        if not self.load_tab.char_list_box.currentItem() and self.load_tab.char_list_box.count() > 0:
            self.load_tab.char_list_box.setCurrentRow(0)
        current_item = self.load_tab.char_list_box.currentItem()
        if not current_item:
            QMessageBox.warning(self.main_window, "No Character Selected", "Please select a character from the list.")
            return
        char_name = current_item.text()
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                QMessageBox.critical(self.main_window, "Error", f"'{self.game_title}' window not found.")
                return
            win32gui.SetForegroundWindow(hwnd)
            pyautogui.press('enter'); pyautogui.write(f"-load {char_name}", interval=0.05); pyautogui.press('enter')
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to send command to game: {e}")