from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QMessageBox
import pyautogui

try:
    import win32gui
    import win32api
    import win32con
except ImportError:
    win32gui = None
    win32api = None
    win32con = None


class AutomationManager(QObject):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window
        self.automation_timers = {}          # {name: QTimer}
        self.is_automation_running = False
        self.custom_action_running = False   # True when the custom action sequence is in progress
        self.custom_action_pending = False   # True when a custom action is scheduled by its timer
        self.sequence_lock = False           # Prevents overlapping sequences
        self.game_title = "Warcraft III"

    # -------------------------
    # Public control
    # -------------------------
    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        if self.is_automation_running:
            self.parent.automation_tab.start_automation_btn.setText("Stop (F5)")
            self.parent.automation_tab.start_automation_btn.setStyleSheet("background-color: #B00000;")
            self._start_timers()
        else:
            self.parent.automation_tab.start_automation_btn.setText("Start (F5)")
            self.parent._reset_automation_button_style()
            self.custom_action_pending = False
            self._stop_timers()

    def reset_settings(self, confirm=True):
        do_reset = False
        if not confirm:
            do_reset = True
        elif QMessageBox.question(
            self.parent,
            "Confirm Reset",
            "Are you sure you want to reset all automation settings to their defaults?"
        ) == QMessageBox.StandardButton.Yes:
            do_reset = True

        if do_reset:
            for key, ctrls in self.parent.automation_tab.automation_key_ctrls.items():
                ctrls["chk"].setChecked(False)
                default_interval = "15000" if key == "Complete Quest" else "500"
                ctrls["edit"].setText(default_interval)

            self.parent.automation_tab.custom_action_btn.setChecked(False)
            self.parent.automation_tab.custom_action_edit1.setText("30000")
            self.parent.automation_tab.custom_action_edit2.setText("-save x")

            # Also stop any active timers immediately
            self._stop_timers()
            self.custom_action_running = False
            self.custom_action_pending = False
            self.sequence_lock = False

    # -------------------------
    # Timers
    # -------------------------
    def _start_timers(self):
        # Key automation timers
        for key, ctrls in self.parent.automation_tab.automation_key_ctrls.items():
            if ctrls["chk"].isChecked():
                try:
                    interval = int(ctrls["edit"].text().strip())
                    timer = QTimer(self.parent)
                    if key == "Complete Quest":
                        timer.timeout.connect(self.run_complete_quest)
                        self.automation_timers["Complete Quest"] = timer
                    else:
                        timer.timeout.connect(lambda k=key: self.control_send_key(k))
                        self.automation_timers[key] = timer
                    timer.start(interval)
                except ValueError:
                    QMessageBox.warning(self.parent, "Invalid interval", f"Interval for '{key}' must be a number in ms.")

        # Custom action timer
        if self.parent.automation_tab.custom_action_btn.isChecked():
            try:
                interval = int(self.parent.automation_tab.custom_action_edit1.text().strip())
                message = self.parent.automation_tab.custom_action_edit2.text()
                # Guard: empty message isn't useful
                if not message.strip():
                    QMessageBox.warning(self.parent, "Invalid message", "Custom action message cannot be empty.")
                else:
                    self.custom_action_pending = True
                    timer = QTimer(self.parent)
                    timer.timeout.connect(lambda msg=message: self.run_custom_action(msg))
                    timer.start(interval)
                    self.automation_timers["custom"] = timer
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid interval", "Interval for 'Custom Action' must be a number in ms.")

    def _stop_timers(self):
        for timer in list(self.automation_timers.values()):
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass
        self.automation_timers.clear()

    # -------------------------
    # Priority management
    # -------------------------
    def pause_all_automation(self):
        # Temporarily unhook message hotkeys (except F5)
        for hk, hk_id in list(self.parent.hotkey_ids.items()):
            if hk not in ['f5']:
                try:
                    import keyboard
                    keyboard.remove_hotkey(hk_id)
                except Exception:
                    pass

        # Stop all running timers but keep references so we can resume later
        for name, timer in self.automation_timers.items():
            try:
                timer.stop()
            except Exception:
                pass

    def resume_all_automation(self):
        # Re-register message hotkeys
        for hotkey, message in self.parent.message_hotkeys.items():
            if hotkey not in self.parent.hotkey_ids:
                self.parent.register_single_hotkey(hotkey, message)

        # Restart timers (respect existing intervals)
        for name, timer in self.automation_timers.items():
            try:
                timer.start()
            except Exception:
                pass

    # -------------------------
    # Sequences
    # -------------------------
    def run_complete_quest(self):
        # Hard priority rules:
        # - If custom action is running or pending, or another sequence holds the lock, skip.
        if self.custom_action_running or self.custom_action_pending or self.sequence_lock:
            return

        self.sequence_lock = True
        self.pause_all_automation()

        # Sequence: y -> 100ms -> e -> 100ms -> esc
        self.control_send_key('y')
        QTimer.singleShot(100, lambda: self.control_send_key('e'))
        QTimer.singleShot(200, lambda: self.control_send_key('esc'))

        # Release quickly to keep UI responsive, then resume
        QTimer.singleShot(400, self._end_complete_quest)

    def _end_complete_quest(self):
        self.sequence_lock = False
        self.resume_all_automation()

    def run_custom_action(self, message: str):
        # Elevate custom action priority immediately
        self.custom_action_pending = False
        self.custom_action_running = True
        self.sequence_lock = True

        # Pause all other automation for exclusivity
        self.pause_all_automation()

        def type_message():
            pyautogui.press('enter')
            pyautogui.write(message, interval=0.03)
            pyautogui.press('enter')

        # Small delay for reliability, then send message; end after a short window
        QTimer.singleShot(500, type_message)
        QTimer.singleShot(2500, self._end_custom_action)

    def _end_custom_action(self):
        self.custom_action_running = False
        self.sequence_lock = False
        self.resume_all_automation()

    # -------------------------
    # Low-level key send
    # -------------------------
    def control_send_key(self, key: str):
        """Sends a key press to the game window without activating it."""
        if not win32gui or not win32api or not win32con:
            return

        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd == 0:
            return

        vk_code = {
            'q': 0x51, 'w': 0x57, 'e': 0x45, 'r': 0x52, 'd': 0x44, 'f': 0x46,
            't': 0x54, 'z': 0x5A, 'x': 0x58, 'y': 0x59, 'esc': win32con.VK_ESCAPE
        }.get(key.lower())

        if vk_code is None:
            return

        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
        QTimer.singleShot(50, lambda: self._control_send_key_up(hwnd, vk_code))

    def _control_send_key_up(self, hwnd, vk_code):
        if not win32api or not win32con:
            return
        lparam = (1 << 31) | (1 << 30)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lparam)