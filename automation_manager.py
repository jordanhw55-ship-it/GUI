import time
import pyautogui
import traceback
from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QMessageBox


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
    def start_automation(self):
        if self.is_automation_running:
            self._log("start_automation ignored (already running)")
            return

        self.is_automation_running = True
        self._log("start_automation -> True")

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

    def stop_automation(self):
        if not self.is_automation_running:
            self._log("stop_automation ignored (not running)")
            return

        self.is_automation_running = False
        self.scheduler.stop()
        self.custom_action_running = False
        self.sequence_lock = False
        self.next_quest_due = None
        self.next_custom_due = None
        self._log("stop_automation -> False")

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

    # -------------------------
    # Sequences
    # -------------------------
    def _run_complete_quest(self):
        self.sequence_lock = True
        self._log("QUEST start")

        pyautogui.press('y')
        QTimer.singleShot(100, lambda: pyautogui.press('e'))
        QTimer.singleShot(200, lambda: pyautogui.press('esc'))
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