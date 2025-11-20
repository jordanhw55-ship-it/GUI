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
                    # keyboard.get_hotkey_name() correctly formats combinations with modifiers.
                    # It can return an empty string if only a modifier is pressed.
                    hotkey_name = keyboard.get_hotkey_name()
                    if hotkey_name: # Ensure we don't emit an empty string
                        self.hotkey_captured.emit(hotkey_name)
                        break
                    # If hotkey_name is empty, loop continues to wait for a valid key.
        except Exception as e:
            print(f"Error capturing hotkey: {e}")
            self.hotkey_captured.emit("esc") # Emit 'esc' on error to cancel capture
        finally:
            # Crucially, unhook all keyboard listeners here to reset the state
            # before the main thread tries to re-register its own hotkeys.
            keyboard.unhook_all()


class ChatMessageWorker(QObject):
    """Runs in a separate thread to send a chat message without freezing the GUI."""
    finished = Signal()
    error = Signal(str)
    def __init__(self, game_title: str, hotkey_pressed: str, message: str):
        super().__init__()
        self.game_title = game_title
        self.hotkey_pressed = hotkey_pressed
        self.message = message
    def run(self):
        if not win32gui:
            self.error.emit("win32gui not available on this system.")
            return
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                self.error.emit(f"Window '{self.game_title}' not found")
                return
            # No need to set foreground, pyautogui handles it
            pyautogui.press('enter')
            pyautogui.write(self.message, interval=0.01)
            pyautogui.press('enter')
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()