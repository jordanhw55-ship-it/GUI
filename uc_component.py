from PIL import Image, ImageTk
import os

class DraggableComponent:
    """
    A data class to represent the state of a draggable element.
    It holds data but does not interact directly with the canvas.
    """
    def __init__(self, tag, x1, y1, x2, y2, color, text, is_dock_asset=False):
        self.tag = tag
        self.last_x = 0
        self.last_y = 0
        self.tk_image = None # Reference to the PhotoImage object
        self.preview_pil_image = None # For dock previews
        self.pil_image = None # Reference to the PIL Image object
        self.border_pil_image = None # For storing the border image
        self.original_pil_image = None # For storing the pristine decal image
        self.rect_id = None
        self.text_id = None
        self.is_draggable = True # Control whether the component can be dragged
        self.is_decal = False # To identify temporary decals
        self.is_border_asset = False # To identify border assets
        self.is_dock_asset = is_dock_asset

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
        print(f"[DEBUG] Applying image to '{self.tag}'.")
        self.pil_image = pil_image.copy() if pil_image else None
        print(f"[DEBUG] AFTER image set: World Coords=({int(self.world_x1)}, {int(self.world_y1)})")
        print("-" * 20)