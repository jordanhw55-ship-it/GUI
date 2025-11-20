import time
import pyautogui
from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QMessageBox

try:
    import win32gui
    import win32api
    import win32con
except ImportError:
    win32gui = None
    win32api = None
    win32con = None


def ts():
    # Short timestamp for readable logs
    return f"{time.monotonic():.3f}"


class AutomationManager(QObject):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window

        # Debug
        self.debug = False  # toggle this on/off
        # Use a dedicated method to log
        self._log = lambda *args: print(f"[{ts()}] ", *args) if self.debug else None

        # State
        self.is_automation_running = False
        self.custom_action_running = False
        self.sequence_lock = False

        # Intervals (ms)
        self.quest_interval_ms = 5000
        self.custom_interval_ms = 10000

        # Next due (monotonic seconds)
        self.next_quest_due = None
        self.next_custom_due = None

        # Scheduler tick
        self.scheduler = QTimer(self)
        self.scheduler.setInterval(100)  # 100 ms tick
        self.scheduler.timeout.connect(self._tick)

        # Game target
        self.game_title = "Warcraft III"

        # Cached message string
        self.custom_message = ""

    # -------------------------
    # Debug control
    # -------------------------
    def set_debug(self, enabled: bool):
        self.debug = bool(enabled)
        self._log("Debug mode:", self.debug)

    # -------------------------
    # Public control
    # -------------------------
    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        self._log("toggle_automation ->", self.is_automation_running)

        if self.is_automation_running:
            # Read intervals
            try:
                self.quest_interval_ms = int(self.parent.automation_tab.automation_key_ctrls["Complete Quest"]["edit"].text().strip())
            except Exception:
                self.quest_interval_ms = 15000

            try:
                self.custom_interval_ms = int(self.parent.automation_tab.custom_action_edit1.text().strip())
            except Exception:
                self.custom_interval_ms = 30000

            message = self.parent.automation_tab.custom_action_edit2.text().strip()
            custom_enabled = self.parent.automation_tab.custom_action_btn.isChecked() and bool(message)
            if self.parent.automation_tab.custom_action_btn.isChecked() and not message:
                QMessageBox.warning(self.parent, "Invalid message", "Custom action message cannot be empty.")
                custom_enabled = False

            # UI
            self.parent.automation_tab.start_automation_btn.setText("Stop (F5)")
            self.parent.automation_tab.start_automation_btn.setStyleSheet("background-color: #B00000;")

            # Initialize schedule aligned to start
            now = time.monotonic()
            quest_checked = self.parent.automation_tab.automation_key_ctrls["Complete Quest"]["chk"].isChecked()
            self.next_quest_due = (now + self.quest_interval_ms / 1000.0) if quest_checked else None
            self.next_custom_due = (now + self.custom_interval_ms / 1000.0) if custom_enabled else None
            self.custom_message = message

            self._log("Start automation")
            self._log(f"Intervals: quest={self.quest_interval_ms}ms custom={self.custom_interval_ms}ms")
            self._log(f"Initial due: quest={self._fmt_due(self.next_quest_due)} custom={self._fmt_due(self.next_custom_due)}")

            self.scheduler.start()
        else:
            self.parent.automation_tab.start_automation_btn.setText("Start (F5)")
            self._reset_automation_button_style()
            self.scheduler.stop()
            self.custom_action_running = False
            self.sequence_lock = False
            self._log("Stop automation")
            self.next_quest_due = None
            self.next_custom_due = None

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

            if self.is_automation_running:
                self.toggle_automation()

            self._log("Settings reset")

    def _reset_automation_button_style(self):
        accent_color = self.parent.custom_theme.get("accent", "#FF7F50")
        text_color = self.parent.custom_theme.get("bg", "#121212")
        self.parent.automation_tab.start_automation_btn.setStyleSheet(f"background-color: {accent_color}; color: {text_color};")

    # -------------------------
    # Scheduler
    # -------------------------
    def _tick(self):
        if not self.is_automation_running:
            return

        now = time.monotonic()

        # Periodic state snapshot (every ~1s)
        if int(now * 10) % 10 == 0:
            self._log(f"Tick: now={now:.3f} nextQuest={self._fmt_due(self.next_quest_due)} nextCustom={self._fmt_due(self.next_custom_due)} "
                      f"running(custom={self.custom_action_running}, lock={self.sequence_lock})")

        if self.custom_action_running or self.sequence_lock:
            return

        quest_due = self.next_quest_due is not None and now >= self.next_quest_due
        custom_due = self.next_custom_due is not None and now >= self.next_custom_due

        # Both due -> custom replaces quest
        if quest_due and custom_due:
            self._log("Both due -> run CUSTOM, advance both")
            self._run_custom_action(self.custom_message)
            # Advance both schedules (keep phase alignment)
            self.next_custom_due += self.custom_interval_ms / 1000.0
            self.next_quest_due += self.quest_interval_ms / 1000.0
            self._drift_snapshot(now, "both")
            return

        if custom_due:
            self._log("Custom due -> run CUSTOM, advance custom")
            self._run_custom_action(self.custom_message)
            self.next_custom_due += self.custom_interval_ms / 1000.0
            self._drift_snapshot(now, "custom")
            return

        if quest_due:
            self._log("Quest due -> run QUEST, advance quest")
            self._run_complete_quest()
            self.next_quest_due += self.quest_interval_ms / 1000.0
            self._drift_snapshot(now, "quest")
            return

    def _fmt_due(self, due):
        if due is None:
            return "None"
        return f"{due:.3f}"

    def _drift_snapshot(self, now, label):
        # Show how far after due we executed (drift)
        q_drift = (now - self.next_quest_due) if self.next_quest_due else None
        c_drift = (now - self.next_custom_due) if self.next_custom_due else None
        def fmt(x):
            return "None" if x is None else f"{x:.3f}s"
        self._log(f"After {label}: drift quest={fmt(q_drift)} custom={fmt(c_drift)} | nextQuest={self._fmt_due(self.next_quest_due)} nextCustom={self._fmt_due(self.next_custom_due)}")

    # -------------------------
    # Sequences
    # -------------------------
    def _run_complete_quest(self):
        if not win32gui or not win32api or not win32con:
            self._log("Quest skipped: Windows API unavailable")
            return

        self.sequence_lock = True
        self._log("QUEST start")

        self.control_send_key('y')
        QTimer.singleShot(100, lambda: self.control_send_key('e'))
        QTimer.singleShot(200, lambda: self.control_send_key('esc'))
        QTimer.singleShot(400, self._end_complete_quest)

    def _end_complete_quest(self):
        self.sequence_lock = False
        self._log("QUEST end")

    def _run_custom_action(self, message: str):
        self.custom_action_running = True
        self.sequence_lock = True
        self._log(f"CUSTOM start (msg='{message}')")

        def type_message():
            pyautogui.press('enter')
            pyautogui.write(message, interval=0.03)
            pyautogui.press('enter')
            self._log("CUSTOM typed")

        QTimer.singleShot(200, type_message)
        QTimer.singleShot(1200, self._end_custom_action)

    def _end_custom_action(self):
        self.custom_action_running = False
        self.sequence_lock = False
        self._log("CUSTOM end")

    # -------------------------
    # Low-level key send
    # -------------------------
    def control_send_key(self, key: str):
        if not win32gui or not win32api or not win32con:
            self._log(f"send_key '{key}' skipped: Windows API unavailable")
            return

        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd == 0:
            self._log(f"send_key '{key}' skipped: window not found")
            return

        vk_code = {
            'q': 0x51, 'w': 0x57, 'e': 0x45, 'r': 0x52, 'd': 0x44, 'f': 0x46,
            't': 0x54, 'z': 0x5A, 'x': 0x58, 'y': 0x59, 'esc': win32con.VK_ESCAPE
        }.get(key.lower())

        if vk_code is None:
            self._log(f"send_key '{key}' skipped: VK code not found")
            return

        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            QTimer.singleShot(50, lambda: self._control_send_key_up(hwnd, vk_code))
            self._log(f"send_key '{key}' posted")
        except Exception as e:
            self._log(f"send_key '{key}' error:", e)

    def _control_send_key_up(self, hwnd, vk_code):
        if not win32api or not win32con:
            return
        lparam = (1 << 31) | (1 << 30)
        try:
            win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lparam)
        except Exception as e:
            self._log("key_up error:", e)