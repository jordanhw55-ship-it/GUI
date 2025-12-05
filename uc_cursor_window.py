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
            # INCREASED DELAY to ensure window is fully mapped before setting styles
            self.window.after(50, self._make_click_through) 

        # --- Content ---
        # Use a Canvas for image display control.
        self.canvas = tk.Canvas(
            self.window, 
            # The canvas background MUST be the key color for visual transparency.
            bg=self.transparent_color_hex, 
            highlightthickness=0,
            # AGGRESSIVE FIX: Explicitly disable the canvas to prevent event capturing
            state='disabled' 
        )
        self.canvas.pack(fill="both", expand=True)
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW) 
        self.tk_image = None
        
        # 3. CRITICAL CLICK-THROUGH FIX: Bindings to stop the Canvas/Window from capturing mouse events.
        # Stop internal Canvas events (May be redundant with state='disabled', but safer to keep)
        self.canvas.bind("<Button>", lambda e: "break")
        self.canvas.bind("<ButtonRelease>", lambda e: "break")
        
        # Stop internal Toplevel window events as a final safety measure
        self.window.bind("<Button>", lambda e: "break")
        self.window.bind("<ButtonRelease>", lambda e: "break")


    def _make_click_through(self):
        """
        [ULTIMATE FIX ATTEMPT] Reintroducing LWA_ALPHA to restore visibility while maintaining WS_EX_TRANSPARENT.
        """
        if not self.window.winfo_exists(): return

        try:
            hwnd = self.window.winfo_id()
            
            # --- DEBUG STEP 1: Log initial style ---
            styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            print(f"[DEBUG] Initial EXSTYLE: {hex(styles)}")
            
            # 1. Add WS_EX_LAYERED (required for LWA flags) AND WS_EX_TRANSPARENT (for click-through)
            TARGET_STYLES = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            styles |= TARGET_STYLES
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, styles)
            
            # --- DEBUG STEP 2: Log style after setting ---
            new_styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            print(f"[DEBUG] New EXSTYLE: {hex(new_styles)}")
            if (new_styles & TARGET_STYLES) == TARGET_STYLES:
                print(f"[DEBUG] Successfully set WS_EX_LAYERED and WS_EX_TRANSPARENT.")
            else:
                print(f"[ERROR] Failed to set all target styles! Missing: {hex(TARGET_STYLES & ~new_styles)}")

            # 2. RE-ADDED: Set LWA_ALPHA to 255 (fully opaque). This is often necessary for 
            # the window to render its contents (the cursor image) while the WS_EX_TRANSPARENT 
            # style handles the click-through functionality.
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)

            print("[INFO] Custom cursor window is now click-through (WS_EX_TRANSPARENT) and visually opaque (LWA_ALPHA).")
            
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
            # We must temporarily enable the canvas to update the image before setting it back to disabled.
            current_state = self.canvas.cget('state')
            if current_state == 'disabled':
                self.canvas.config(state='normal')

            self.canvas.config(width=w, height=h) # Also resize the canvas
            self.canvas.coords(self.image_id, w // 2, h // 2)
            self.canvas.itemconfig(self.image_id, image=self.tk_image, anchor=tk.CENTER, state='normal')

            # Revert state to disabled to prevent interaction
            if current_state == 'disabled':
                self.canvas.config(state='disabled')
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