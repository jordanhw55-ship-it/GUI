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


class AutomationManager(QObject):
    def __init__(self, parent_window):
        super().__init__()
        self.parent = parent_window

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

        # Scheduler tick
        self.scheduler = QTimer(self)
        self.scheduler.setInterval(100)  # 100ms tick
        self.scheduler.timeout.connect(self._tick)

        # Game target
        self.game_title = "Warcraft III"

        # Cached message
        self.custom_message = ""

    def _log(self, *args):
        if self.debug:
            print("[DEBUG]", *args)

    def _fmt_due(self, due):
        return "None" if due is None else f"{due:.3f}"

    # -------------------------
    # Public control
    # -------------------------
    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        self._log("toggle_automation ->", self.is_automation_running)

        if self.is_automation_running:
            try:
                self.quest_interval_ms = int(self.parent.automation_tab.automation_key_ctrls["Complete Quest"]["edit"].text().strip())
            except Exception:
                self.quest_interval_ms = 15000

            try:
                self.custom_interval_ms = int(self.parent.automation_tab.custom_action_edit1.text().strip())
            except Exception:
                self.custom_interval_ms = 30000

            self.custom_message = self.parent.automation_tab.custom_action_edit2.text().strip()
            custom_enabled = self.parent.automation_tab.custom_action_btn.isChecked() and bool(self.custom_message)

            if self.parent.automation_tab.custom_action_btn.isChecked() and not self.custom_message:
                QMessageBox.warning(self.parent, "Invalid message", "Custom action message cannot be empty.")
                custom_enabled = False

            now = time.monotonic()
            quest_checked = self.parent.automation_tab.automation_key_ctrls["Complete Quest"]["chk"].isChecked()
            self.next_quest_due = (now + self.quest_interval_ms / 1000.0) if quest_checked else None
            self.next_custom_due = (now + self.custom_interval_ms / 1000.0) if custom_enabled else None

            self._log("Start automation")
            self._log(f"Intervals: quest={self.quest_interval_ms}ms custom={self.custom_interval_ms}ms")
            self._log(f"Initial due: quest={self._fmt_due(self.next_quest_due)} custom={self._fmt_due(self.next_custom_due)}")

            self.scheduler.start()
        else:
            self.scheduler.stop()
            self.custom_action_running = False
            self.sequence_lock = False
            self.next_quest_due = None
            self.next_custom_due = None
            self._log("Stop automation")

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

        # Both due -> custom replaces quest
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

        # Ensure window is foreground
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            self._log("SetForegroundWindow failed:", e)

        vk_code = {
            'q': 0x51, 'w': 0x57, 'e': 0x45, 'r': 0x52, 'd': 0x44, 'f': 0x46,
            't': 0x54, 'z': 0x5A, 'x': 0x58, 'y': 0x59, 'esc': win32con.VK_ESCAPE
        }.get(key.lower())

        if vk_code is None:
            self._log(f"send_key '{key}' skipped: VK code not found")
            return

        try:
            win32api.SendMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            QTimer.singleShot(50, lambda: win32api.SendMessage(hwnd, win32con.WM_KEYUP, vk_code, 0))
            self._log(f"send_key '{key}' sent")
        except Exception as e:
            self._log(f"send_key '{key}' error:", e)