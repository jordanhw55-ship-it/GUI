import requests
import keyboard   # type: ignore
import pyautogui  # type: ignore

from PySide6.QtCore import QObject, Signal

try:
    import win32gui # type: ignore
except ImportError:
    win32gui = None

class LobbyFetcher(QObject):
    finished = Signal(list)
    error = Signal(str)
    def run(self):
        try:
            response = requests.get("https://api.wc3stats.com/gamelist", timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "OK":
                self.finished.emit(data.get("body", []))
            else:
                self.error.emit("API returned an unexpected status.")
        except requests.exceptions.JSONDecodeError:
            self.error.emit("Failed to parse server response.")
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {e}")

class LobbyHeartbeatChecker(QObject):
    """Checks if the wc3stats gamelist has been updated since the last check."""
    update_required = Signal()
    error = Signal(str)
    finished = Signal()

    def __init__(self, last_seen_id: int):
        super().__init__()
        self.last_seen_id = last_seen_id

    def run(self):
        try:
            response = requests.get(f"https://api.wc3stats.com/uptodate?id={self.last_seen_id}", timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "OK" and data.get("body") is False:
                self.update_required.emit()
        except requests.RequestException as e:
            self.error.emit(f"Heartbeat check failed: {e}")
        finally:
            self.finished.emit()

class ChatMessageWorker(QObject):
    """Runs in a separate thread to send a chat message without freezing the GUI."""
    finished = Signal()
    error = Signal(str) 

    def __init__(self, game_title: str):
        super().__init__()
        self.game_title = game_title

    def sendMessage(self, message: str):
        """This slot receives the message and performs the blocking IO."""
        print(f"[DEBUG] ChatMessageWorker (id: {id(self)}) received message: '{message}'")
        if not win32gui:
            self.error.emit("win32gui not available on this system.")
            return
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                # This is not a fatal error for the worker, just for this message attempt.
                print(f"[DEBUG] ChatMessageWorker: Window '{self.game_title}' not found. Skipping message.")
                return
            pyautogui.press('enter')
            pyautogui.write(message, interval=0.01)
            pyautogui.press('enter')
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()