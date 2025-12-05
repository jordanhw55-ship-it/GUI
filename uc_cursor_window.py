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
        # We define a neutral background color. This color is NO LONGER THE TRANSPARENCY KEY.
        # We will rely on Tkinter's built-in transparency for the window background.
        self.R, self.G, self.B = (171, 205, 239) 
        self.transparent_color_hex = f'#{self.R:02x}{self.G:02x}{self.B:02x}'
        
        # --- Transparency & Click-Through Setup (Tkinter Part) ---
        # 1. Use Tkinter's built-in opacity control (0.0 fully transparent, 1.0 fully opaque).
        # We set it to near-opaque but rely on Win32 styles for full click-through.
        self.window.wm_attributes("-alpha", 1.0) 
        
        # 2. Set the background color. We still need this for the Canvas widget.
        self.window.config(bg='white') # Use a simple background color

        # --- Click-Through (Windows only) ---
        if WIN32_AVAILABLE:
            # We call this immediately, but only set the styles after the window exists.
            self.window.after(10, self._make_click_through) 

        # --- Content ---
        # Use a Canvas for image display control.
        self.canvas = tk.Canvas(
            self.window, 
            # The canvas background MUST be transparent for PIL PNG alpha to work.
            bg=self.transparent_color_hex, 
            highlightthickness=0 
        )
        self.canvas.pack(fill="both", expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW) 
        self.tk_image = None
        
        # CRITICAL TKINTER FIX: Add a binding to the Canvas to ignore all mouse events.
        # This prevents the Canvas widget from capturing the click before the Windows API 
        # has a chance to pass it through. This is redundant with WS_EX_TRANSPARENT 
        # but provides a safety mechanism.
        self.canvas.bind("<Button>", lambda e: "break")
        self.canvas.bind("<ButtonRelease>", lambda e: "break")


    def _make_click_through(self):
        """
        [DEFINITIVE FIX] Uses Alpha Blend + WS_EX_TRANSPARENT.
        The combination of WS_EX_LAYERED + LWA_ALPHA + WS_EX_TRANSPARENT is the only
        reliable way to make an irregular-shaped window (like a circular cursor) fully
        click-through, including the opaque pixels.
        """
        if not self.window.winfo_exists(): return

        try:
            hwnd = self.window.winfo_id()
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # 1. Add WS_EX_LAYERED (required for LWA_ALPHA) and WS_EX_TRANSPARENT (for click-through)
            # NOTE: We are intentionally REMOVING any old WS_EX_TRANSPARENT if it was set alone,
            # but usually, we just rely on the |=
            styles |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
            
            # 2. Apply Alpha Blend (opacity=255, no color key).
            # This makes the window a layered window, allowing the OS to pass clicks
            # through based on the WS_EX_TRANSPARENT style.
            # 255 is fully opaque.
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
            
            print("[INFO] Custom cursor window is now fully click-through (Alpha Blend method).")
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