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

        # --- Color Definitions ---
        # We define the R, G, B components once for both Tkinter and the Windows API.
        self.R, self.G, self.B = (171, 205, 239) # Corresponds to #abcdef
        self.transparent_color_hex = f'#{self.R:02x}{self.G:02x}{self.B:02x}'
        
        # --- Transparency & Click-Through Setup (Tkinter Part) ---
        # 1. CRITICAL VISUAL FIX: Use Tkinter's transparency attribute for the key color.
        self.window.wm_attributes("-transparentcolor", self.transparent_color_hex)
        
        # 2. Set the background color of the window to the key color.
        self.window.config(bg=self.transparent_color_hex)

        # --- Click-Through (Windows only) ---
        if WIN32_AVAILABLE:
            self.window.after(10, self._make_click_through) 

        # --- Content ---
        # Use a Canvas for image display control.
        self.canvas = tk.Canvas(
            self.window, 
            # The canvas background MUST be the key color for visual transparency.
            bg=self.transparent_color_hex, 
            highlightthickness=0 
        )
        self.canvas.pack(fill="both", expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW) 
        self.tk_image = None
        
        # 3. CRITICAL CLICK-THROUGH FIX: Bindings to stop the Canvas from capturing mouse events.
        self.canvas.bind("<Button>", lambda e: "break")
        self.canvas.bind("<ButtonRelease>", lambda e: "break")


    def _make_click_through(self):
        """
        [DEFINITIVE FIX] Uses Color Key + WS_EX_TRANSPARENT.
        LWA_COLORKEY handles visual transparency of the background.
        WS_EX_TRANSPARENT ensures the visible (opaque) cursor circle is click-through.
        """
        if not self.window.winfo_exists(): return

        try:
            hwnd = self.window.winfo_id()
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # 1. Add WS_EX_LAYERED (required for LWA_COLORKEY) AND WS_EX_TRANSPARENT (for click-through)
            styles |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT 
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
            
            # 2. Apply LWA_COLORKEY. This makes the background color (#abcdef) visually transparent.
            color_key = win32api.RGB(self.R, self.G, self.B)
            win32gui.SetLayeredWindowAttributes(hwnd, color_key, 0, win32con.LWA_COLORKEY)
            
            print("[INFO] Custom cursor window is now fully click-through (Color Key + WS_EX_TRANSPARENT).")
        except Exception as e:
            print(f"[ERROR] Could not set click-through property on cursor window: {e}")

    def set_image(self, pil_image):
        """Updates the image displayed in the cursor window."""
        if pil_image:
            self.tk_image = ImageTk.PhotoImage(pil_image)
            
            w, h = pil_image.width, pil_image.height
            
            # 1. Resize the Toplevel window to match the image size
            self.window.geometry(f"{w}x{h}+{self.window.winfo_x()}+{self.window.winfo_y()}")

            # 2. Update and center the image on the Canvas
            self.canvas.config(width=w, height=h) # Also resize the canvas
            self.canvas.coords(self.image_id, w // 2, h // 2)
            self.canvas.itemconfig(self.image_id, image=self.tk_image, anchor=tk.CENTER, state='normal')
        else:
            self.canvas.itemconfig(self.image_id, state='hidden')
            self.tk_image = None

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