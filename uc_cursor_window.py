import tkinter as tk
from PIL import ImageTk

try:
    import win32gui
    import win32con
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[WARNING] win32gui not found. The custom cursor window will not be click-through and may have a background.")

class CursorWindow:
    """
    Manages a transparent, click-through, top-level window to act as a custom cursor.
    This is significantly more performant than drawing and moving a cursor on the main canvas.
    """
    def __init__(self, master):
        self.master = master
        self.window = tk.Toplevel(master)
        self.window.withdraw() # Hide initially

        # --- Window Attributes ---
        self.window.overrideredirect(True) # No title bar, borders, etc.
        self.window.wm_attributes("-topmost", True) # Always on top

        # --- DEFINITIVE FIX: Define color components once to ensure consistency ---
        # We define the R, G, B components and use them to build the hex string for Tkinter
        # and the COLORREF for the Windows API.
        self.R, self.G, self.B = (171, 205, 239) # Corresponds to #abcdef
        self.transparent_color_hex = f'#{self.R:02x}{self.G:02x}{self.B:02x}'

        # Set the background color of the window that we will make transparent.
        self.window.config(bg=self.transparent_color_hex)

        # --- Click-Through (Windows only) ---
        if WIN32_AVAILABLE:
            self.window.after(10, self._make_click_through) # Delay to ensure window handle exists

        # --- Content ---
        self.label = tk.Label(self.window, bg=self.transparent_color_hex)
        self.label.pack()
        self.tk_image = None # To hold a reference to the PhotoImage

    def _make_click_through(self):
        """
        Uses the win32gui library to set the WS_EX_LAYERED style and LWA_COLORKEY.
        The LWA_COLORKEY setting makes the transparent regions automatically click-through.
        """
        if not self.window.winfo_exists(): return

        try:
            hwnd = self.window.winfo_id()
            # Get the current window style
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            # Only add the WS_EX_LAYERED style.
            # We omit WS_EX_TRANSPARENT to avoid conflicts and enable click-through.
            styles |= win32con.WS_EX_LAYERED
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
            # Use LWA_COLORKEY with the defined R,G,B components.
            color_key = win32api.RGB(self.R, self.G, self.B)
            win32gui.SetLayeredWindowAttributes(hwnd, color_key, 0, win32con.LWA_COLORKEY)
            print("[INFO] Custom cursor window is now click-through.")
        except Exception as e:
            print(f"[ERROR] Could not set click-through property on cursor window: {e}")

    def set_image(self, pil_image):
        """Updates the image displayed in the cursor window."""
        if pil_image:
            self.tk_image = ImageTk.PhotoImage(pil_image)
            self.label.config(image=self.tk_image)
            self.window.geometry(f"{pil_image.width}x{pil_image.height}+{self.window.winfo_x()}+{self.window.winfo_y()}")
        else:
            self.label.config(image=None)

    def move(self, x, y):
        """Moves the top-left corner of the cursor window to the specified screen coordinates."""
        self.window.geometry(f"+{x}+{y}")

    def show(self):
        """Makes the cursor window visible."""
        self.window.deiconify()

    def hide(self):
        """Hides the cursor window."""
        self.window.withdraw()

    def destroy(self):
        """Destroys the cursor window."""
        self.window.destroy()