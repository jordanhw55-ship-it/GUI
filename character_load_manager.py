import os
from PySide6.QtWidgets import QFileDialog, QMessageBox, QListWidgetItem
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
import re

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

        # Connect the new placeholder button to the existing load function
        self.load_tab.placeholder_btn_1.clicked.connect(self.load_selected_character)
        
        # Connect the second placeholder button to the new code-based load function
        self.load_tab.placeholder_btn_2.clicked.connect(self.load_character_with_codes)

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
        file_content = ""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
                self.load_tab.char_content_box.setText(file_content)
        except (IOError, OSError) as e:
            file_content = f"Error reading file: {e}"
            self.load_tab.char_content_box.setText(file_content)
        finally:
            self._update_command_preview(file_content)

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
            
            # Paste the command instead of typing it for speed
            command_to_paste = f"-load {char_name}"
            clipboard = QApplication.clipboard()
            clipboard.setText(command_to_paste)
            pyautogui.press('enter'); pyautogui.hotkey('ctrl', 'v'); pyautogui.press('enter')
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to send command to game: {e}")

    def load_character_with_codes(self):
        """
        Parses the selected character file for Preload() codes and sends them
        sequentially to the game.
        """
        if not self.load_tab.char_list_box.currentItem() and self.load_tab.char_list_box.count() > 0:
            self.load_tab.char_list_box.setCurrentRow(0)
        
        if not self.load_tab.char_list_box.currentItem():
            QMessageBox.warning(self.main_window, "No Character Selected", "Please select a character from the list.")
            return

        file_content = self.load_tab.char_content_box.toPlainText()
        if not file_content:
            QMessageBox.warning(self.main_window, "Empty File", "The selected character file appears to be empty.")
            return

        # Find all content within `call Preload(...)`
        preload_contents = re.findall(r'call Preload\(\s*\"(.+?)\"\s*\)', file_content)

        if not preload_contents:
            QMessageBox.warning(self.main_window, "No Codes Found", "Could not find any 'Preload' codes in the selected file.")
            return

        # --- REVISED LOGIC to handle all cases robustly ---
        commands = []
        # Check if the file uses the multi-part "Code1:", "Code2:" format
        is_multipart_code_format = any(re.search(r'Code\d+:', content) for content in preload_contents)

        if is_multipart_code_format:
            # Scenario: Multiple codes that need to be sent after a single "-load"
            commands.append("-load")
            for content in preload_contents:
                match = re.search(r'Code\d+:\s*([^\s"]+)', content)
                if match:
                    commands.append(match.group(1))
        else:
            # Scenario: Each Preload line is a self-contained command (e.g., "-load ...")
            for content in preload_contents:
                # Find the "-load" command, ignoring surrounding characters like '|'
                match = re.search(r'(-load\s+[^\s"]+)', content)
                if match:
                    commands.append(match.group(1))

        if not commands:
            QMessageBox.warning(self.main_window, "Unsupported Format", "Could not recognize the 'Preload' format in the selected file.")
            return
        
        self._send_command_sequence(commands)

    def _send_command_sequence(self, commands: list):
        """Sends a list of commands to the game with a delay between each."""
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                QMessageBox.critical(self.main_window, "Error", f"'{self.game_title}' window not found.")
                return
            win32gui.SetForegroundWindow(hwnd)

            clipboard = QApplication.clipboard()
            original_clipboard = clipboard.text()

            for i, command in enumerate(commands):
                # Use a lambda with a default argument to capture the current command
                QTimer.singleShot(i * 300, lambda cmd=command: (clipboard.setText(cmd), pyautogui.press('enter'), pyautogui.hotkey('ctrl', 'v'), pyautogui.press('enter')))
            
            # Schedule clipboard restoration after the last command is sent
            QTimer.singleShot(len(commands) * 300, lambda: clipboard.setText(original_clipboard))

        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to send command sequence to game: {e}")

    def _update_command_preview(self, file_content: str):
        """Parses the file content and updates the command preview box."""
        preview_box = self.load_tab.command_preview_box
        preview_box.clear()

        preload_contents = re.findall(r'call Preload\(\s*\"(.+?)\"\s*\)', file_content)
        if not preload_contents:
            preview_box.setText("(No multi-part load codes found)")
            return

        commands = []
        is_multipart_code_format = any(re.search(r'Code\d+:', content) for content in preload_contents)

        if is_multipart_code_format:
            commands.append("-load")
            for content in preload_contents:
                match = re.search(r'Code\d+:\s*([^\s"]+)', content)
                if match:
                    commands.append(match.group(1))
        else:
            for content in preload_contents:
                match = re.search(r'(-load\s+[^\s"]+)', content)
                if match:
                    commands.append(match.group(1))
        
        preview_box.setText("\n\n".join(commands))