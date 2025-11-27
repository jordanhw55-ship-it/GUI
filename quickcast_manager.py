import os
import subprocess
from PySide6.QtWidgets import QMessageBox, QPushButton
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

class QuickcastManager:
    def __init__(self, main_window):
        import keyboard
        self.main_window = main_window
        self.ahk_process = None
        self.is_toggling_ahk = False # Debounce flag for F2 spam

    def reset_keybinds(self):
        """Resets all keybinds and quickcast settings to their default state."""
        if QMessageBox.question(self.main_window, "Confirm Reset", "Are you sure you want to reset all keybinds to their defaults?") == QMessageBox.StandardButton.Yes:
            import keyboard
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
            self.main_window.register_global_hotkeys() # This is crucial to re-enable F2
            # Hide the overlay when the script is deactivated
            self.main_window.status_overlay.hide()
            print("[INFO] Quickcast overlay hidden.")
            return True
        return False

    def toggle_ahk_quickcast(self):
        """Toggles the activation of the dynamically generated AHK quickcast script."""
        if self.is_toggling_ahk:
            print("[DEBUG] AHK toggle already in progress. Ignoring F2 spam.")
            return

        self.is_toggling_ahk = True
        try:
            is_running = hasattr(self, 'ahk_process') and self.ahk_process and self.ahk_process.poll() is None
            print(f"\n[DEBUG] toggle_ahk_quickcast called. AHK script is currently {'running' if is_running else 'not running'}.")
            if is_running:
                print("[DEBUG] --> Deactivating AHK script.")
                self.deactivate_ahk_script_if_running(inform_user=True)
            else:
                print("[DEBUG] --> Activating AHK script.")
                if self.generate_and_run_ahk_script():
                    self.main_window.quickcast_tab.activate_quickcast_btn.setText("Deactivate Quickcast (F2)")
                    self.main_window.quickcast_tab.activate_quickcast_btn.setStyleSheet("background-color: #B22222; color: white;")
                    self.unregister_python_hotkeys()
        finally:
            # Always reset the flag after the operation is complete
            self.is_toggling_ahk = False

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
        print("[DEBUG] ----- Generating AHK Script -----")
        ahk_path = self._find_ahk_path()
        if not ahk_path:
            QMessageBox.critical(self.main_window, "AutoHotkey Not Found", "Could not find AutoHotkey.exe. Please ensure it is installed and in your system's PATH.")
            self.is_toggling_ahk = False
            return False

        lock_file_path = os.path.join(os.path.dirname(__file__), "ahk.lock")
lock_file := "{lock_file_path.replace('\\', '/')}"
FileAppend("locked", lock_file)
SetTimer(() => FileExist(lock_file) ? "" : ExitApp(), 250)

; --- State flag for pausing ---
global is_paused := false

; --- Functions ---
remapSpellwQC(originalKey) {{
    SendInput("{{Ctrl Down}}{{9}}{{0}}{{Ctrl Up}}")
    SendInput("{{{" . originalKey . "}}}")
    MouseClick("Left")
    SendInput("{{9}}{{0}}")
}}

remapSpellwoQC(originalKey) {{
    SendInput("{{{" . originalKey . "}}}")
}}

remapMouse(button) {{
    MouseClick(button)
}}

; --- Pause toggle hotkeys ---
~$Enter::
~$NumpadEnter::
{{
    is_paused := !is_paused
    ToolTip(is_paused ? "Quickcast Paused" : "")
}}

~$LButton::
~$Esc::
{{
    if (is_paused) {{
        is_paused := false
        ToolTip("")
    }}
}}

; --- Hotkeys only active if NOT paused and game is active ---
#HotIf !is_paused and WinActive("{self.main_window.game_title}")
"""
        # Append the rest of the script. The f-string requires doubling the braces {{ and }}
        # to escape them for the final AHK script.
        script_content += f"""
; --- State flag for pausing ---
global is_paused := false

; --- Functions ---
remapSpellwQC(originalKey) {{
    SendInput("{{Ctrl Down}}{{9}}{{0}}{{Ctrl Up}}")
    SendInput("{{{" . originalKey . "}}}")
    MouseClick("Left")
    SendInput("{{9}}{{0}}")
}}

remapSpellwoQC(originalKey) {{
    SendInput("{{{" . originalKey . "}}}")
}}

remapMouse(button) {{
    MouseClick(button)
}}

; --- Pause toggle hotkeys ---
$Enter::togglePause()
$NumpadEnter::togglePause()
$LButton::closePause()
$Esc::closePause()

togglePause() {{
    global is_paused
    is_paused := !is_paused
    ToolTip(is_paused ? "Quickcast Paused" : "")
}}

closePause() {{
    global is_paused
    is_paused := false
    ToolTip("")
}}

; --- Hotkeys only active if NOT paused and game is active ---
#HotIf !is_paused and WinActive("{self.main_window.game_title}")
"""
        defined_hotkeys = set()
        for name, key_info in self.main_window.keybinds.items():
            hotkey = key_info.get("hotkey")

            quickcast = key_info.get("quickcast", False)
            function_call = f"remapSpellwQC('{original_key}')" if quickcast else f"remapSpellwoQC('{original_key}')"
            
            script_content += f'\nhotkey_map["{name}"] := new RegisterHotkey("{hotkey}", {function_object_str}, "{self.main_window.game_title}")'

            script_content += f"\n${hotkey}:: {function_call}"
            defined_hotkeys.add(hotkey)
        
        print("--- AHK SCRIPT CONTENT ---")
        print(script_content)
        print("--------------------------")

        script_path = os.path.join(os.path.dirname(__file__), "generated_quickcast.ahk")
        try:
            with open(script_path, "w") as f:
                f.write(script_content)
            print(f"[DEBUG] AHK script written to {script_path}")
            
            print(f"[DEBUG] Launching AHK process with path: {ahk_path}")
            self.ahk_process = subprocess.Popen([ahk_path, script_path])
            print(f"[INFO] AHK Quickcast script generated and activated. Process ID: {self.ahk_process.pid}")
            # Show a persistent overlay when the script is activated
            self.main_window.status_overlay.show_persistent_message("Quickcast Enabled", "#B22222")
            print("[INFO] Quickcast overlay shown.")
            return True
        except Exception as e:
            QMessageBox.critical(self.main_window, "Script Error", f"Failed to generate or run AHK script: {e}")
            return False

    def unregister_python_hotkeys(self):
        """Unregisters all hotkeys managed by the 'keyboard' library, except F2."""
        print("[DEBUG] Unregistering Python hotkeys (except F2)...")
        import keyboard
        for hotkey_str, hk_id in list(self.main_window.hotkey_ids.items()):
            if hotkey_str != 'f2':
                try:
                    keyboard.remove_hotkey(hk_id)
                    print(f"[DEBUG]   - Removed '{hotkey_str}'")
                    del self.main_window.hotkey_ids[hotkey_str]
                except (KeyError, ValueError):
                    print(f"[Warning] Failed to remove hotkey '{hotkey_str}', it might have been already unregistered.")

    def register_keybind_hotkeys(self):
        """Safely unregisters and re-registers all keybind-specific hotkeys."""
        print("[DEBUG] Registering Python keybind hotkeys...")
        import keyboard
        for hotkey_str, hk_id in list(self.main_window.hotkey_ids.items()):
            if hotkey_str not in ['f2', 'f3', 'f5', 'f6'] and hotkey_str not in self.main_window.message_hotkeys:
                try:
                    keyboard.remove_hotkey(hk_id)
                    print(f"[DEBUG]   - Unregistered old keybind: '{hotkey_str}'")
                    del self.main_window.hotkey_ids[hotkey_str]
                except (KeyError, ValueError):
                    print(f"[Warning] Failed to remove hotkey '{hotkey_str}', it might have been already unregistered.")

        for name, key_info in self.main_window.keybinds.items():
            if "hotkey" in key_info and key_info["hotkey"]:
                print(f"[DEBUG]   + Registering new keybind: '{key_info['hotkey']}' for '{name}'")
                self.main_window.register_single_keybind(name, key_info["hotkey"])