import os
import subprocess
from PySide6.QtWidgets import QMessageBox, QPushButton
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
import keyboard

class QuickcastManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.ahk_process = None

    def reset_keybinds(self):
        """Resets all keybinds and quickcast settings to their default state."""
        if QMessageBox.question(self.main_window, "Confirm Reset", "Are you sure you want to reset all keybinds to their defaults?") == QMessageBox.StandardButton.Yes:
            for hotkey_str, hk_id in list(self.main_window.hotkey_ids.items()):
                if hotkey_str not in ['f2', 'f3', 'f5', 'f6'] and hotkey_str not in self.main_window.message_hotkeys:
                    try:
                        keyboard.remove_hotkey(hk_id)
                        del self.main_window.hotkey_ids[hotkey_str]
                    except (KeyError, ValueError):
                        print(f"[Warning] Tried to remove a keybind hotkey ('{hotkey_str}') that was already unregistered.")

            self.main_window.keybinds.clear()
            self.apply_keybind_settings()

    def open_ahk_website(self):
        """Opens the AutoHotkey download page in the default web browser."""
        url = QUrl("https://www.autohotkey.com/")
        QDesktopServices.openUrl(url)

    def show_ahk_install_cmd(self):
        """Shows a message box with the winget command to install AHK."""
        QMessageBox.information(
            self.main_window,
            "Install via Command Prompt",
            "1. Open Command Prompt or PowerShell.\n"
            "2. Copy and paste the following command:\n\n"
            "winget install AutoHotkey.AutoHotkey"
        )

    def apply_keybind_settings(self):
        """Applies loaded keybind settings to the UI and registers hotkeys."""
        for name, checkbox in self.main_window.quickcast_tab.setting_checkboxes.items():
            is_enabled = self.main_window.keybinds.get("settings", {}).get(name, True)
            checkbox.setChecked(is_enabled)

        for name, button in self.main_window.quickcast_tab.key_buttons.items():
            key_info = self.main_window.keybinds.get(name, {})
            hotkey = key_info.get("hotkey", button.text())
            quickcast = key_info.get("quickcast", False)

            button.setText(hotkey.upper())
            button.setProperty("quickcast", quickcast)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        self.register_keybind_hotkeys()

    def on_keybind_button_clicked(self, button: QPushButton, name: str):
        """Handles left-click on a keybind button to start capture."""
        self.deactivate_ahk_script_if_running()
        if self.main_window.is_capturing_hotkey:
            return

        self.main_window.capturing_for_control = name
        button.setText("...")
        button.setChecked(True)
        self.main_window.capture_message_hotkey()

    def on_keybind_setting_changed(self, setting_name: str):
        """Handles when a keybind setting checkbox is changed."""
        self.deactivate_ahk_script_if_running()
        if "settings" not in self.main_window.keybinds:
            self.main_window.keybinds["settings"] = {}
        
        is_enabled = self.main_window.quickcast_tab.setting_checkboxes[setting_name].isChecked()
        self.main_window.keybinds["settings"][setting_name] = is_enabled
        self.register_keybind_hotkeys()

    def toggle_quickcast(self, name: str):
        """Toggles quickcast for a given keybind."""
        self.deactivate_ahk_script_if_running()
        current_state = self.main_window.keybinds.get(name, {}).get("quickcast", False)
        new_state = not current_state

        if name not in self.main_window.keybinds:
            self.main_window.keybinds[name] = {}
        self.main_window.keybinds[name]["quickcast"] = new_state

        button = self.main_window.quickcast_tab.key_buttons[name]
        button.setProperty("quickcast", new_state)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

        self.register_keybind_hotkeys()
        print(f"[DEBUG] {name} quickcast toggled to {new_state}")

    def get_keybind_settings_from_ui(self):
        """Gathers keybind settings from the UI controls for saving."""
        for name, button in self.main_window.quickcast_tab.key_buttons.items():
            if name not in self.main_window.keybinds:
                self.main_window.keybinds[name] = {}
            self.main_window.keybinds[name]["hotkey"] = button.text().lower()
        return self.main_window.keybinds

    def deactivate_ahk_script_if_running(self, inform_user=True):
        """Checks if the AHK script is running and deactivates it."""
        if hasattr(self, 'ahk_process') and self.ahk_process and self.ahk_process.poll() is None:
            lock_file_path = os.path.join(os.path.dirname(__file__), "ahk.lock")
            try:
                if os.path.exists(lock_file_path):
                    os.remove(lock_file_path)
                    print("[INFO] Sent graceful exit signal to AHK script by deleting lock file.")
                self.ahk_process.wait(timeout=2)
            except Exception as e:
                print(f"[WARNING] Graceful exit failed: {e}. Falling back to forceful termination.")
                try:
                    pid = self.ahk_process.pid
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e_kill:
                    print(f"[WARNING] taskkill also failed: {e_kill}")
                    self.ahk_process.terminate()
            
            self.ahk_process = None
            self.main_window.quickcast_tab.activate_quickcast_btn.setText("Activate Quickcast (F2)")
            self.main_window.quickcast_tab.activate_quickcast_btn.setStyleSheet("background-color: #228B22; color: white;")
            self.register_keybind_hotkeys()
            self.main_window.register_global_hotkeys()
            return True
        return False

    def toggle_ahk_quickcast(self):
        """Toggles the activation of the dynamically generated AHK quickcast script."""
        if hasattr(self, 'ahk_process') and self.ahk_process and self.ahk_process.poll() is None:
            self.deactivate_ahk_script_if_running(inform_user=True)
        else:
            if self.generate_and_run_ahk_script():
                self.main_window.quickcast_tab.activate_quickcast_btn.setText("Deactivate Quickcast (F2)")
                self.main_window.quickcast_tab.activate_quickcast_btn.setStyleSheet("background-color: #B22222; color: white;")
                self.unregister_python_hotkeys()
                
    def _find_ahk_path(self) -> str | None:
        """Finds the path to the AutoHotkey executable."""
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        possible_paths = [
            os.path.join(program_files, "AutoHotkey", "AutoHotkey.exe"),
            os.path.join(program_files, "AutoHotkey", "v2", "AutoHotkey.exe"),
            os.path.join(program_files, "AutoHotkey", "UX", "AutoHotkey.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        try:
            result = subprocess.run(['where', 'AutoHotkey.exe'], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.stdout.strip().split('\n')[0]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def generate_and_run_ahk_script(self):
        """Generates a complete AHK script from the current keybinds and runs it."""
        ahk_path = self._find_ahk_path()
        if not ahk_path:
            QMessageBox.critical(self.main_window, "AutoHotkey Not Found", "Could not find AutoHotkey.exe. Please ensure it is installed and in your system's PATH.")
            return False

        lock_file_path = os.path.join(os.path.dirname(__file__), "ahk.lock")

        script_content = f"""#Requires AutoHotkey v2.0
#SingleInstance Force
ProcessSetPriority("High")

lock_file := "{lock_file_path.replace(os.sep, '/')}"
FileAppend("locked", lock_file)
SetTimer(() => FileExist(lock_file) ? "" : ExitApp(), 250)

HotIfWinActive("{self.main_window.game_title}")

remapSpellwQC(originalKey) {{
    SendInput("{{Ctrl Down}}{{9}}{{0}}{{Ctrl Up}}")
    SendInput("{{{" originalKey "}}}")
    MouseClick("Left")
    SendInput("{{9}}{{0}}")
}}

remapSpellwoQC(originalKey) {{
    SendInput("{{{" originalKey "}}}")
}}

remapMouse(button) {{
    MouseClick(button)
}}
"""
        defined_hotkeys = set()
        for name, key_info in self.main_window.keybinds.items():
            hotkey = key_info.get("hotkey")
            if not hotkey or "button" in hotkey: continue

            if hotkey in defined_hotkeys:
                print(f"[WARNING] Duplicate hotkey '{hotkey}' found for '{name}'. Skipping.")
                continue

            category = name.split("_")[0]
            if category == "inv": category = "inventory"
            is_enabled = self.main_window.keybinds.get("settings", {}).get(category, True)
            if not is_enabled: continue

            original_key = ""
            if name.startswith("spell_"):
                original_key = name.split("_")[1].lower()
            elif name.startswith("inv_"):
                inv_map = ["numpad7", "numpad8", "numpad4", "numpad5", "numpad1", "numpad2"]
                inv_index = int(name.split("_")[1]) - 1
                original_key = inv_map[inv_index]

            if not original_key: continue

            quickcast = key_info.get("quickcast", False)
            function_call = f"remapSpellwQC('{original_key}')" if quickcast else f"remapSpellwoQC('{original_key}')"
            
            script_content += f"\n${hotkey}:: {function_call}"
            defined_hotkeys.add(hotkey)

        script_path = os.path.join(os.path.dirname(__file__), "generated_quickcast.ahk")
        try:
            with open(script_path, "w") as f:
                f.write(script_content)
            
            self.ahk_process = subprocess.Popen([ahk_path, script_path])
            print(f"[INFO] AHK Quickcast script generated and activated. Process ID: {self.ahk_process.pid}")
            return True
        except Exception as e:
            QMessageBox.critical(self.main_window, "Script Error", f"Failed to generate or run AHK script: {e}")
            return False

    def unregister_python_hotkeys(self):
        """Unregisters all hotkeys managed by the 'keyboard' library, except F2."""
        for hotkey_str, hk_id in list(self.main_window.hotkey_ids.items()):
            if hotkey_str != 'f2':
                try:
                    keyboard.remove_hotkey(hk_id)
                    del self.main_window.hotkey_ids[hotkey_str]
                except (KeyError, ValueError):
                    print(f"[Warning] Failed to remove hotkey '{hotkey_str}', it might have been already unregistered.")

    def register_keybind_hotkeys(self):
        """Safely unregisters and re-registers all keybind-specific hotkeys."""
        for hotkey_str, hk_id in list(self.main_window.hotkey_ids.items()):
            if hotkey_str not in ['f2', 'f3', 'f5', 'f6'] and hotkey_str not in self.main_window.message_hotkeys:
                try:
                    keyboard.remove_hotkey(hk_id)
                    del self.main_window.hotkey_ids[hotkey_str]
                except (KeyError, ValueError):
                    print(f"[Warning] Failed to remove hotkey '{hotkey_str}', it might have been already unregistered.")

        for name, key_info in self.main_window.keybinds.items():
            if "hotkey" in key_info and key_info["hotkey"]:
                self.main_window.register_single_keybind(name, key_info["hotkey"])