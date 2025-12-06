from PIL import Image, ImageTk
import os

class DraggableComponent:
    """
    A data class to represent the state of a draggable element.
    It holds data but does not interact directly with the canvas.
    """
    def __init__(self, app, tag, x1, y1, x2, y2, color, text, is_dock_asset=False):
        self.tag = tag
        self.app = app # Reference to the main application instance
        self.last_x = 0
        self.last_y = 0
        self.tk_image = None # Reference to the PhotoImage object
        self.preview_pil_image = None # For dock previews
        self.pil_image = None # Reference to the PIL Image object
        self.display_pil_image = None # For temporary on-canvas display (e.g., transparent decal)
        self.border_pil_image = None # For storing the border image
        self.original_pil_image = None # For storing the pristine decal image
        self.image_path = None # NEW: To store the original file path for saving/reloading
        self.rect_id = None
        self.text_id = None
        self.is_draggable = True # Control whether the component can be dragged
        self.is_decal = False # To identify temporary decals
        self.is_border_asset = False # To identify border assets
        self.is_dock_asset = is_dock_asset
        self.parent_tag = None # To link components, e.g., a border to its tile

        # --- NEW: For accurate border positioning ---
        self.relative_x = 0
        self.relative_y = 0

        # World coordinates
        self.world_x1, self.world_y1, self.world_x2, self.world_y2 = x1, y1, x2, y2

        # Placeholder attributes
        self.placeholder_color = color
        self.placeholder_text = text

        # Caching for Performance
        self._cached_screen_w = -1
        self._cached_screen_h = -1

    def set_image(self, pil_image):
        """Sets the internal PIL image for this component."""
        print("-" * 20)
        print(f"[DEBUG] Setting image for '{self.tag}'.")
        self.pil_image = pil_image.copy() if pil_image else None

        # If this is the first time an image is set, replace the placeholder
        if self.pil_image and self.text_id:
            self.app.canvas.delete(self.rect_id)
            self.app.canvas.delete(self.text_id)
            self.rect_id = None
            self.text_id = None
            self.tk_image = None # Force redraw to create a new image item

        # --- DEFINITIVE FIX: Reset the cache to force a visual update ---
        # This ensures that even if the component's size hasn't changed, the new image data will be rendered.
        self._cached_screen_w, self._cached_screen_h = -1, -1

        # The manager that calls this method is responsible for redrawing.
        self.app.redraw_all_zoomable()
        print(f"[DEBUG] AFTER image set: World Coords=({int(self.world_x1)}, {int(self.world_y1)})")
        print("-" * 20)