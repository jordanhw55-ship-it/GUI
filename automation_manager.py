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
        self.automation_timers = {}
        self.is_automation_running = False
        self.custom_action_running = False
        self.game_title = "Warcraft III"

    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        if self.is_automation_running:
            self.parent.automation_tab.start_automation_btn.setText("Stop (F5)")
            self.parent.automation_tab.start_automation_btn.setStyleSheet("background-color: #B00000;")
            self._start_timers()
        else:
            self.parent.automation_tab.start_automation_btn.setText("Start (F5)")
            self.parent._reset_automation_button_style()
            self._stop_timers()

    def _start_timers(self):
        # Start timers for key automation
        for key, ctrls in self.parent.automation_tab.automation_key_ctrls.items():
            if ctrls["chk"].isChecked():
                try:
                    interval = int(ctrls["edit"].text().strip())
                    timer = QTimer(self.parent)
                    if key == "Complete Quest":
                        timer.timeout.connect(self.run_complete_quest)
                    else:
                        timer.timeout.connect(lambda k=key: self.control_send_key(k))
                    timer.start(interval)
                    self.automation_timers[key] = timer
                except ValueError:
                    QMessageBox.warning(self.parent, "Invalid interval", f"Interval for '{key}' must be a number in ms.")

        # Start timer for custom action
        if self.parent.automation_tab.custom_action_btn.isChecked():
            try:
                interval = int(self.parent.automation_tab.custom_action_edit1.text().strip())
                message = self.parent.automation_tab.custom_action_edit2.text()
                timer = QTimer(self.parent)
                timer.timeout.connect(lambda msg=message: self.run_custom_action(msg))
                timer.start(interval)
                self.automation_timers["custom"] = timer
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid interval", "Interval for 'Custom Action' must be a number in ms.")

    def _stop_timers(self):
        for timer in self.automation_timers.values():
            timer.stop()
            timer.deleteLater()
        self.automation_timers.clear()

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

    def pause_all_automation(self):
        for hk, hk_id in list(self.parent.hotkey_ids.items()):
            if hk not in ['f5']:
                try:
                    import keyboard
                    keyboard.remove_hotkey(hk_id)
                except Exception:
                    pass
        for timer in self.automation_timers.values():
            timer.stop()

    def resume_all_automation(self):
        for hotkey, message in self.parent.message_hotkeys.items():
            if hotkey not in self.parent.hotkey_ids:
                self.parent.register_single_hotkey(hotkey, message)
        for timer in self.automation_timers.values():
            timer.start()

    def run_complete_quest(self):
        if self.custom_action_running:
            QTimer.singleShot(2500, self.run_complete_quest)
            return
        self.pause_all_automation()
        self.control_send_key('y')
        QTimer.singleShot(100, lambda: self.control_send_key('e'))
        QTimer.singleShot(200, lambda: self.control_send_key('esc'))
        QTimer.singleShot(2100, self.resume_all_automation)

    def run_custom_action(self, message: str):
        self.custom_action_running = True
        self.pause_all_automation()
        def type_message():
            pyautogui.press('enter')
            pyautogui.write(message, interval=0.03)
            pyautogui.press('enter')
        QTimer.singleShot(2000, type_message)
        QTimer.singleShot(4000, self._end_custom_action)

    def _end_custom_action(self):
        self.custom_action_running = False
        self.resume_all_automation()

    def reset_settings(self, confirm=True):
        """Resets all automation settings in the UI to their defaults."""
        do_reset = False
        if not confirm:
            do_reset = True
        elif QMessageBox.question(self.parent, "Confirm Reset", "Are you sure you want to reset all automation settings to their defaults?") == QMessageBox.StandardButton.Yes:
            do_reset = True
        if do_reset:
            for key, ctrls in self.parent.automation_tab.automation_key_ctrls.items():
                ctrls["chk"].setChecked(False)
                default_interval = "15000" if key == "Complete Quest" else "500"
                ctrls["edit"].setText(default_interval)
            self.parent.automation_tab.custom_action_btn.setChecked(False)
            self.parent.automation_tab.custom_action_edit1.setText("30000")
            self.parent.automation_tab.custom_action_edit2.setText("-save x")