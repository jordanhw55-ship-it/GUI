import requests
import keyboard   # type: ignore

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


class HotkeyCaptureWorker(QObject):
    """Runs in a separate thread to capture a hotkey without freezing the GUI."""
    hotkey_captured = Signal(str)

    def run(self):
        try:
            # Wait for a single key down event. This prevents combinations like "2+3".
            # It will correctly handle modifier combinations like "ctrl+s".
            while True:
                event = keyboard.read_event(suppress=True)
                if event.event_type == keyboard.KEY_DOWN:
                    # Use the event’s key name directly
                    hotkey_name = event.name
                    self.hotkey_captured.emit(hotkey_name)
                    break
        except Exception as e:
            print(f"Error capturing hotkey: {e}")
            self.hotkey_captured.emit("esc") # Emit 'esc' on error to cancel capture