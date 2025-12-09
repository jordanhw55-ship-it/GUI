import time
from PySide6.QtCore import QTimer, QObject, Signal
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QApplication

try:
    import win32gui
    import win32api
    import win32con
    import pyautogui
except ImportError:
    win32gui = None
    win32api = None
    win32con = None
    pyautogui = None


class AutomationManager(QObject):
    log_message = Signal(str)
    status_changed = Signal(bool)
    automation_state_changed = Signal(bool)

    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window
        self.automation_tab = parent_window.automation_tab

        # Debug toggle
        self.debug = True

        # State
        self.is_automation_running = False
        self.custom_action_running = False
        self.sequence_lock = False

        # Intervals (ms)
        self.quest_interval_ms = 5000
        self.custom_interval_ms = 10000

        # Next due times
        self.next_quest_due = None
        self.next_custom_due = None
        self.next_key_due = {}  # {key: next_due_time}

        # Scheduler tick
        self.scheduler = QTimer(self)
        self.scheduler.setInterval(100)  # 100ms tick
        self.scheduler.timeout.connect(self._tick)

        # Game target
        self.game_title = "Warcraft III"

        # Cached message
        self.custom_message = ""

        # Message Hotkeys
        self.message_hotkeys = self.parent.settings_manager.get("message_hotkeys", {})
        self.is_capturing_hotkey = False

        self._connect_signals()
        self.load_message_hotkeys()

        # Chat Worker
        self.is_sending_message = False

    def _log(self, *args):
        if self.debug:
            message = " ".join(map(str, args))
            print("[DEBUG]", message)
            self.log_message.emit(message)

    def _fmt_due(self, due):
        return "None" if due is None else f"{due:.3f}"

    def _connect_signals(self):
        """Connects UI signals for the automation tab to this manager."""
        self.automation_tab.start_automation_btn.clicked.connect(self.start_automation)
        self.automation_tab.stop_automation_btn.clicked.connect(self.stop_automation)
        self.automation_tab.reset_automation_btn.clicked.connect(lambda: self.reset_settings(confirm=True))
        self.automation_tab.hotkey_capture_btn.clicked.connect(self.parent.capture_message_hotkey)
        self.automation_tab.add_msg_btn.clicked.connect(self.add_message_hotkey)
        self.automation_tab.delete_msg_btn.clicked.connect(self.delete_message_hotkey)

        self.log_message.connect(self.update_log)
    # -------------------------
    # Public control
    # -------------------------
    def toggle_automation(self):
        if self.is_automation_running:
            self.stop_automation()
        else:
            self.start_automation()

    def start_automation(self):
        if self.is_automation_running:
            self._log("start_automation ignored (already running)")
            return

        self.is_automation_running = True
        self.status_changed.emit(True)
        self.automation_state_changed.emit(True)
        self._log("start_automation -> True")

        try:
            self.quest_interval_ms = int(self.automation_tab.automation_key_ctrls["Complete Quest"]["edit"].text().strip())
            if self.quest_interval_ms < 50: self.quest_interval_ms = 50
        except Exception:
            self.quest_interval_ms = 15000

        try:
            self.custom_interval_ms = int(self.automation_tab.custom_action_edit1.text().strip())
            if self.custom_interval_ms < 50: self.custom_interval_ms = 50
        except Exception:
            self.custom_interval_ms = 30000

        self.custom_message = self.automation_tab.custom_action_edit2.text().strip()
        custom_enabled = self.automation_tab.custom_action_btn.isChecked() and bool(self.custom_message)

        if self.parent.automation_tab.custom_action_btn.isChecked() and not self.custom_message:
            QMessageBox.warning(self.parent, "Invalid message", "Custom action message cannot be empty.")
            custom_enabled = False

        now = time.monotonic()
        quest_checked = self.parent.automation_tab.automation_key_ctrls["Complete Quest"]["chk"].isChecked()
        self.next_quest_due = (now + self.quest_interval_ms / 1000.0) if quest_checked else None # type: ignore
        self.next_custom_due = (now + self.custom_interval_ms / 1000.0) if custom_enabled else None

        # Set up all other keys
        self.next_key_due = {}
        for key, ctrls in self.automation_tab.automation_key_ctrls.items():
            if key == "Complete Quest":
                continue
            if ctrls["chk"].isChecked():
                try:
                    interval = int(ctrls["edit"].text().strip())
                    if interval < 50: interval = 50
                except Exception:
                    interval = 500
                # Standardize the key name for the scheduler and vk_map lookup.
                normalized_key = key.lower().replace(" ", "").replace("num", "")
                self.next_key_due[normalized_key] = now + interval / 1000.0
            else:
                self.next_key_due[key] = None

        self._log("Start automation")
        self._log(f"Intervals: quest={self.quest_interval_ms}ms custom={self.custom_interval_ms}ms")
        self._log(f"Initial due: quest={self._fmt_due(self.next_quest_due)} custom={self._fmt_due(self.next_custom_due)}")
        self._log(f"Key schedule: {self.next_key_due}")

        self.scheduler.start()

    def stop_automation(self):
        if not self.is_automation_running:
            self._log("stop_automation ignored (not running)")
            return

        self.is_automation_running = False
        self.status_changed.emit(False)
        self.automation_state_changed.emit(False)
        self.scheduler.stop()
        self.custom_action_running = False
        self.sequence_lock = False
        self.next_quest_due = None
        self.next_custom_due = None
        self.next_key_due = {}
        self._log("stop_automation -> False")

    def reset_settings(self, confirm=True):
        """Resets all automation settings in the UI to their defaults."""
        do_reset = False
        if not confirm:
            do_reset = True
        elif QMessageBox.question(self.parent, "Confirm Reset", "Are you sure you want to reset all automation settings to their defaults?") == QMessageBox.StandardButton.Yes:
            do_reset = True

        if do_reset:
            self.stop_automation()
            # Reset key automation UI
            for key, ctrls in self.automation_tab.automation_key_ctrls.items():
                ctrls["chk"].setChecked(False)
                ctrls["edit"].setText("15000" if key == "Complete Quest" else "500")
            # Reset custom action UI
            self.automation_tab.custom_action_btn.setChecked(False)
            self.automation_tab.custom_action_edit1.setText("30000")
            self.automation_tab.custom_action_edit2.setText("-save x")

    # -------------------------
    # Message Hotkeys
    # -------------------------
    def load_message_hotkeys(self):
        """Populates the hotkey table from the manager's data."""
        table = self.automation_tab.msg_hotkey_table
        table.setRowCount(0)
        if not isinstance(self.message_hotkeys, dict):
            self.message_hotkeys = {}
        for hotkey, message in self.message_hotkeys.items():
            row_position = table.rowCount()
            table.insertRow(row_position)
            table.setItem(row_position, 0, QTableWidgetItem(hotkey))
            table.setItem(row_position, 1, QTableWidgetItem(message))

    def add_message_hotkey(self):
        """Adds a new hotkey and message to the system."""
        hotkey = self.automation_tab.hotkey_capture_btn.text()
        message = self.automation_tab.message_edit.text()

        if hotkey == "Click to set" or not message or hotkey == 'esc':
            QMessageBox.warning(self.parent, "Input Error", "Please set a hotkey and enter a message.")
            return

        if hotkey in self.message_hotkeys:
            QMessageBox.warning(self.parent, "Duplicate Hotkey", "This hotkey is already in use. Delete the old one first.")
            return

        self.message_hotkeys[hotkey] = message
        self.load_message_hotkeys()
        self.parent.register_global_hotkeys() # Re-register all hotkeys

        self.automation_tab.hotkey_capture_btn.setText("Click to set")
        self.automation_tab.message_edit.clear()

    def delete_message_hotkey(self):
        """Deletes a selected hotkey."""
        table = self.automation_tab.msg_hotkey_table
        selected_items = table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self.parent, "Selection Error", "Please select a hotkey from the list to delete.")
            return

        selected_row = selected_items[0].row()
        hotkey_to_delete = table.item(selected_row, 0).text()

        if QMessageBox.question(self.parent, "Confirm Delete", f"Are you sure you want to delete the hotkey '{hotkey_to_delete}'?") == QMessageBox.StandardButton.Yes:
            self.message_hotkeys.pop(hotkey_to_delete, None)
            table.removeRow(selected_row)
            self.parent.register_global_hotkeys()

    def update_log(self, message: str):
        """Appends a message to the automation log text box, capping the log size."""
        log_box = self.automation_tab.automation_log_box
        log_box.append(message)

        # To prevent performance issues, cap the number of lines in the log.
        if log_box.document().blockCount() > 2000:
            cursor = log_box.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()

    # -------------------------
    # Scheduler
    # -------------------------
    def _tick(self):
        if not self.is_automation_running:
            return

        now = time.monotonic()
        quest_due = self.next_quest_due is not None and now >= self.next_quest_due
        custom_due = self.next_custom_due is not None and now >= self.next_custom_due

        if self.custom_action_running or self.sequence_lock:
            return

        if quest_due and custom_due:
            self._log("Both due -> CUSTOM replaces QUEST")
            self._run_custom_action(self.custom_message)
            self.next_custom_due += self.custom_interval_ms / 1000.0
            self.next_quest_due += self.quest_interval_ms / 1000.0
            return

        if custom_due:
            self._log("Custom due -> run CUSTOM")
            self._run_custom_action(self.custom_message)
            self.next_custom_due += self.custom_interval_ms / 1000.0
            return

        if quest_due:
            self._log("Quest due -> run QUEST")
            self._run_complete_quest()
            self.next_quest_due += self.quest_interval_ms / 1000.0
            return

        # Check all other keys
        for key, due in self.next_key_due.items():
            if due is not None and now >= due:
                self._log(f"{key.upper()} due -> send")
                self._send_key(key)
                try:
                    # Find the original key name to get the interval from the UI control
                    original_key_name = next((k for k in self.automation_tab.automation_key_ctrls if k.lower().replace(" ", "").replace("num", "") == key), key)
                    interval = int(self.automation_tab.automation_key_ctrls[original_key_name]["edit"].text().strip())
                    if interval < 50: interval = 50
                except Exception:
                    interval = 500
                self.next_key_due[key] += interval / 1000.0

    # -------------------------
    # Sequences
    # -------------------------
    def _run_complete_quest(self):
        self.sequence_lock = True
        self._log("QUEST start")

        self._send_key('y')
        QTimer.singleShot(100, lambda: self._send_key('e'))
        QTimer.singleShot(200, lambda: self._send_key('esc'))
        QTimer.singleShot(400, self._end_complete_quest)

    def _end_complete_quest(self):
        self.sequence_lock = False
        self._log("QUEST end")

    def _run_custom_action(self, message: str):
        self.custom_action_running = True
        self.sequence_lock = True
        self._log(f"CUSTOM start (msg='{message}')")

        def type_message():
            self._send_key('enter')
            for ch in message:
                self._send_char(ch)
            self._send_key('enter')
            self._log("CUSTOM typed")

        QTimer.singleShot(200, type_message)
        QTimer.singleShot(1200, self._end_custom_action)

    def _end_custom_action(self):
        self.custom_action_running = False
        self.sequence_lock = False
        self._log("CUSTOM end")

    # -------------------------
    # Low-level send to WC3
    # -------------------------
    def _send_key(self, key: str):
        if not win32gui or not win32api or not win32con:
            self._log(f"send_key '{key}' skipped: Windows API unavailable")
            return

        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd == 0:
            self._log(f"send_key '{key}' skipped: window not found")
            return

        vk_map = {
            'q': 0x51, 'w': 0x57, 'e': 0x45, 'r': 0x52,
            'd': 0x44, 'f': 0x46, 't': 0x54, 'z': 0x5A, 'x': 0x58,
            'y': 0x59, 's': 0x53, 'h': 0x48, 'a': 0x41, 'p': 0x50,
            'esc': win32con.VK_ESCAPE, 'enter': win32con.VK_RETURN,
            '1': 0x61, '2': 0x62, '3': 0x63, # Numpad
            '4': 0x64, '5': 0x65, '6': 0x66,
            '7': 0x67, '8': 0x68, '9': 0x69,
            '0': 0x60,
        }
        vk_code = vk_map.get(key.lower())
        if vk_code is None:
            self._log(f"send_key '{key}' skipped: VK code not found")
            return

        # Send down
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)

        # For letters, also send WM_CHAR so WC3 sees it even backgrounded
        if key.lower() in ['q','w','e','r','d','f','t','y','a','s','z','x']:
            win32api.PostMessage(hwnd, win32con.WM_CHAR, ord(key.lower()), 0)

        # Send up
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)

        self._log(f"send_key '{key}' sent")

    def _send_char(self, ch: str):
        if not win32gui or not win32api or not win32con:
            self._log(f"send_char '{ch}' skipped: Windows API unavailable")
            return

        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd == 0:
            self._log(f"send_char '{ch}' skipped: window not found")
            return

        # Send the character as WM_CHAR
        win32api.PostMessage(hwnd, win32con.WM_CHAR, ord(ch), 0)
        self._log(f"send_char '{ch}' sent")