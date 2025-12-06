import os
import subprocess
from PySide6.QtWidgets import QMessageBox, QPushButton
from PySide6.QtCore import QUrl, QObject
from PySide6.QtGui import QDesktopServices

from key_translator import to_ahk_hotkey, to_ahk_send, normalize_to_canonical, to_keyboard_lib
import keyboard

class QuickcastManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.ahk_process = None
        self.is_toggling_ahk = False # Debounce flag for F2 spam

    def reset_keybinds(self):
        """Resets all keybinds and quickcast settings to their default state."""
        if QMessageBox.question(self.main_window, "Confirm Reset", "Are you sure you want to reset all keybinds to their defaults?") == QMessageBox.StandardButton.Yes:
            # First, ensure any running AHK script is stopped.
            self.deactivate_ahk_script_if_running(inform_user=False)
            
            # Then, clear the data model and UI
            self.main_window.keybinds.clear()
            self.apply_keybind_settings() # This will reset the UI to defaults
            
            # Re-register all hotkeys, which will clear the old keybinds
            self.register_all_hotkeys()


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
            # Use the button's default text if no hotkey is saved
            raw_default_key = name.split('_')[-1] if '_' in name else button.text()
            
            # Normalize the default key to the canonical format (e.g., "Numpad7" -> "7")
            canonical_default = normalize_to_canonical(raw_default_key, "numpad" in name.lower())
            
            hotkey = key_info.get("hotkey", canonical_default)
            quickcast = key_info.get("quickcast", False)

            button.setText(hotkey.upper())
            button.setProperty("quickcast", quickcast)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

        # If AHK is not running, register hotkeys with Python
        if not (hasattr(self, 'ahk_process') and self.ahk_process and self.ahk_process.poll() is None):
            self.register_all_hotkeys()

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
        self.register_all_hotkeys()

    def toggle_quickcast(self, name: str):
        """Toggles quickcast for a given keybind."""
        self.deactivate_ahk_script_if_running()
        current_state = self.main_window.keybinds.get(name, {}).get("quickcast", False)
        new_state = not current_state

        if name not in self.main_window.keybinds:
            self.main_window.keybinds[name] = {}
        self.main_window.keybinds[name]["quickcast"] = new_state

        # CRITICAL FIX: If a hotkey isn't set, assign the default to ensure it's generated in AHK.
        if "hotkey" not in self.main_window.keybinds[name]:
            raw_default_key = name.split('_')[-1]
            is_numpad = "numpad" in name.lower()
            canonical_default = normalize_to_canonical(raw_default_key, is_numpad)
            self.main_window.keybinds[name]["hotkey"] = canonical_default

        button = self.main_window.quickcast_tab.key_buttons[name]
        button.setProperty("quickcast", new_state)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

        self.register_all_hotkeys()
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
                self.ahk_process.wait(timeout=1)
            except Exception as e:
                print(f"[WARNING] Graceful AHK exit failed: {e}. Forcefully terminating.")
                try:
                    # Explicitly use taskkill to stop AHK process and its children cleanly
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.ahk_process.pid)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception as e_kill:
                    print(f"[ERROR] taskkill failed: {e_kill}")
                    self.ahk_process.terminate()
                
            self.ahk_process = None
            self.main_window.quickcast_tab.activate_quickcast_btn.setText("Activate Quickcast (F2)")
            self.main_window.quickcast_tab.activate_quickcast_btn.setStyleSheet("background-color: #228B22; color: white;")
            
            # Re-register Python hotkeys now that AHK is off
            self.register_all_hotkeys()
            
            self.main_window.status_overlay.hide()
            print("[INFO] AHK Quickcast script deactivated.")
            return True
        return False

    def toggle_ahk_quickcast(self):
        """Toggles the activation of the dynamically generated AHK quickcast script."""
        if self.is_toggling_ahk:
            return

        self.is_toggling_ahk = True
        try:
            is_running = hasattr(self, 'ahk_process') and self.ahk_process and self.ahk_process.poll() is None
            if is_running:
                self.deactivate_ahk_script_if_running(inform_user=True)
            else:
                if self.generate_and_run_ahk_script():
                    self.main_window.quickcast_tab.activate_quickcast_btn.setText("Deactivate Quickcast (F2)")
                    self.main_window.quickcast_tab.activate_quickcast_btn.setStyleSheet("background-color: #B22222; color: white;")
                    self.unregister_python_hotkeys()
        finally:
            self.is_toggling_ahk = False

    def _find_ahk_path(self) -> str | None:
        """Finds the path to the AutoHotkey v2 executable."""
        # Check common installation paths first for speed
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        possible_paths = [
            os.path.join(program_files, "AutoHotkey", "v2", "AutoHotkey.exe"),
            os.path.join(program_files, "AutoHotkey", "AutoHotkey.exe"),
            os.path.join(program_files, "AutoHotkey", "UX", "AutoHotkey.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        # Fallback to 'where' command if not found in common locations
        try:
            result = subprocess.run(['where', 'AutoHotkey.exe'], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            # The 'where' command can return multiple paths, we prefer one with 'v2' in it
            paths = result.stdout.strip().split('\n')
            for path in paths:
                if 'v2' in path.lower():
                    return path
            return paths[0] if paths else None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def generate_and_run_ahk_script(self):
        """Generates a complete AHK script from the current keybinds and runs it."""
        ahk_path = self._find_ahk_path()
        if not ahk_path:
            QMessageBox.critical(self.main_window, "AutoHotkey Not Found", "Could not find AutoHotkey v2. Please ensure it is installed and accessible.")
            return False

        lock_file_path = os.path.join(os.path.dirname(__file__), "ahk.lock")

        # This static block contains the core logic: pausing and remapping functions.
        # It uses f-string formatting, so all literal braces must be doubled ({{ or }}).
        static_block = f"""#Requires AutoHotkey v2.0
#SingleInstance Force
ProcessSetPriority("High")

; This lock file allows the Python GUI to gracefully terminate the script.
lock_file := "{lock_file_path.replace('\\', '/')}"
FileAppend("locked", lock_file)
SetTimer(() => !FileExist(lock_file) ? ExitApp() : "", 250)

; --- State flag for pausing ---
global is_paused := false

; --- Functions ---
remapSpellwQC(originalKey) {{
    ; Send Ctrl+90 (for game-specific quickcast logic)
    SendInput("{{Ctrl Down}}90{{Ctrl Up}}")
    ; Send the original key down/up (to trigger the spell)
    SendInput "{{" originalKey " Down}}"
    SendInput "{{" originalKey " Up}}"
    ; Send the mouse click (for quickcast)
    MouseClick("Left")
    ; Send 90 to complete the quickcast sequence 
    SendInput "90" 
}}

remapSpellwoQC(originalKey) {{
    ; Standard keypress for non-quickcast ability
    SendInput "{{" originalKey " Down}}"
    SendInput "{{" originalKey " Up}}"
}}

; --- Pause toggle hotkeys ---
; These are always active to allow pausing/unpausing.
; The '~' prefix allows the keypress to pass through to the game (e.g., to open the chat box).
~$Enter::togglePause()
~$NumpadEnter::togglePause()
~$LButton::closePause()
~$Esc::closePause()

togglePause() {{
    global is_paused
    is_paused := !is_paused
}}

closePause() {{
    global is_paused
    if (is_paused) {{
        is_paused := false
    }}
}}

; --- Hotkeys only active if NOT paused and game is active ---
#HotIf !is_paused and WinActive("{self.main_window.game_title}")
"""
        
        script_content = static_block
        
        # FIX: Revert to storing a list of actions for each hotkey (chaining)
        # This allows multiple actions (e.g., Q and W) to be executed sequentially 
        # when mapped to the same key (e.g., '2').
        hotkey_actions = {} 

        # Dynamically generate the keybinds based on UI settings
        for name, key_info in self.main_window.keybinds.items():
            hotkey = key_info.get("hotkey")
            if not hotkey or "button" in hotkey: continue
            
            category = name.split("_")[0]
            if category == "inv": category = "inventory"
            is_enabled = self.main_window.keybinds.get("settings", {}).get(category, True)
            if not is_enabled: continue

            original_key = ""
            if name.startswith("spell_"):
                # The original key is part of the name, e.g., "spell_Numpad7"
                original_key_part = name.split("_")[1]
                # Translate the original key to the format AHK's SendInput needs ("Numpad7")
                original_key = to_ahk_send(original_key_part)
            
            if not original_key: continue
            
            quickcast = key_info.get("quickcast", False)

            # Determine if the key has been remapped from its default
            raw_default_key = name.split('_')[-1]
            is_numpad_control = "numpad" in name.lower()
            canonical_default = normalize_to_canonical(raw_default_key, is_numpad_control)
            is_remapped = hotkey != canonical_default

            if not is_remapped and not quickcast: continue # Only skip if nothing has changed
            
            function_call = f'remapSpellwQC("{original_key}")' if quickcast else f'remapSpellwoQC("{original_key}")'
            
            # Group actions by the remapped hotkey (this list creation enables chaining)
            ahk_hotkey = to_ahk_hotkey(hotkey)

            if ahk_hotkey not in hotkey_actions:
                hotkey_actions[ahk_hotkey] = []
                
            hotkey_actions[ahk_hotkey].append(function_call)
            print(f"[DEBUG] AHK Gen - Added action for '{name}' to hotkey '{ahk_hotkey}'.")


        # Generate the AHK hotkey definitions from the grouped actions
        for ahk_hotkey, actions in hotkey_actions.items():
            # Check if chaining is required (more than one action mapped to the same key)
            if len(actions) > 1:
                # Actions list is joined by Sleep 50 to allow the game engine time to process the first command
                separator = "\n \tSleep 50\n \t"
                action_block = separator.join(actions)
            else:
                action_block = actions[0] # Single action
                
            script_content += f"\n${ahk_hotkey}:: {{\n \t{action_block}\n}}"
        
        # Add a closing #HotIf to end the conditional block
        script_content += "\n#HotIf"
        
        print("--- AHK SCRIPT CONTENT ---")
        print(script_content)
        print("--------------------------")

        script_path = os.path.join(os.path.dirname(__file__), "generated_quickcast.ahk")
        try:
            with open(script_path, "w", encoding='utf-8') as f:
                f.write(script_content)
            
            self.ahk_process = subprocess.Popen([ahk_path, script_path])
            print(f"[INFO] AHK Quickcast script activated. Process ID: {self.ahk_process.pid}")
            self.main_window.status_overlay.show_persistent_message("Quickcast Enabled", "#B22222")
            return True
        except Exception as e:
            QMessageBox.critical(self.main_window, "Script Error", f"Failed to generate or run AHK script: {e}")
            return False

    def unregister_python_hotkeys(self, unregister_globals=False):
        """
        Unregisters hotkeys. If unregister_globals is False, it only unregisters
        the remappable keybinds, leaving F-keys and message hotkeys active.
        """
        print(f"[INFO] Unregistering Python hotkeys. Globals: {not unregister_globals}")
        if unregister_globals:
            keyboard.unhook_all()
            self.main_window.hotkey_ids.clear()
        else:
            # Selectively unregister only keybinds
            global_hotkeys = ['f2', 'f3', 'f5', 'f6'] + list(self.main_window.message_hotkeys.keys())
            for hotkey_str, hk_id in list(self.main_window.hotkey_ids.items()):
                # The hotkey_str for keybinds is the keyboard-lib format, not canonical.
                # We can rely on the fact that keybinds won't be F-keys.
                is_global_or_message = hotkey_str in global_hotkeys
                if not is_global_or_message:
                    try:
                        keyboard.remove_hotkey(hk_id)
                        del self.main_window.hotkey_ids[hotkey_str]
                    except (KeyError, ValueError):
                        pass # Already removed

    def register_all_hotkeys(self, re_register_globals=True):
        """
        Centralized function to register all Python-based hotkeys.
        It unhooks previous keys to prevent duplicates.
        """
        # Unhook all existing hotkeys to ensure a clean slate.
        self.unregister_python_hotkeys(unregister_globals=re_register_globals)

        if re_register_globals:
            # --- Register Global Hotkeys (F-keys, messages) ---
            print("[INFO] Registering global hotkeys...")
            try:
                self.main_window.hotkey_ids['f5'] = keyboard.add_hotkey('f5', lambda: self.main_window.start_automation_signal.emit(), suppress=True)
                self.main_window.hotkey_ids['f6'] = keyboard.add_hotkey('f6', lambda: self.main_window.stop_automation_signal.emit(), suppress=True)
                self.main_window.hotkey_ids['f3'] = keyboard.add_hotkey('f3', lambda: self.main_window.load_character_signal.emit(), suppress=True)

                def on_f2_press(e):
                    if e.event_type == keyboard.KEY_DOWN and not self.main_window.f2_key_down:
                        self.main_window.f2_key_down = True
                        self.main_window.quickcast_toggle_signal.emit()
                    elif e.event_type == keyboard.KEY_UP:
                        self.main_window.f2_key_down = False
                self.main_window.hotkey_ids['f2'] = keyboard.hook_key('f2', on_f2_press, suppress=True)

            except Exception as e:
                print(f"[ERROR] Failed to register global F-key: {e}")

            for hotkey, message in self.main_window.message_hotkeys.items():
                try:
                    # Use a lambda with default arguments to capture current values
                    hk_id = keyboard.add_hotkey(hotkey, lambda h=hotkey, msg=message: self.main_window.send_chat_message(h, msg), suppress=False)
                    self.main_window.hotkey_ids[hotkey] = hk_id
                except (ValueError, ImportError) as e:
                    print(f"Failed to register message hotkey '{hotkey}': {e}")

        # --- Register Remappable Keybinds ---
        print("[INFO] Registering remappable keybinds...")
        for name, key_info in self.main_window.keybinds.items():
            hotkey = key_info.get("hotkey")
            if not hotkey or "button" in hotkey.lower():
                continue

            try:
                lib_hotkey = to_keyboard_lib(hotkey)
                # Check for duplicates before adding
                if lib_hotkey in self.main_window.hotkey_ids:
                    continue
                hk_id = keyboard.add_hotkey(lib_hotkey, lambda n=name, h=hotkey: self.main_window.execute_keybind(n, h), suppress=False)
                self.main_window.hotkey_ids[lib_hotkey] = hk_id
            except (ValueError, ImportError, KeyError) as e:
                print(f"Failed to register keybind '{hotkey}' for '{name}': ({e.__class__.__name__}, {e})")