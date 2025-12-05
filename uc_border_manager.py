import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import math
import os
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[WARNING] NumPy not found. Smart Border tool performance will be significantly degraded.")
    
from uc_border_manager2 import SmartBorderManager

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

        # Instantiate the sub-managers
        self.smart_manager = SmartBorderManager(app, self)

        self.next_border_id = 0

        self.preview_rect_ids = [] # DEFINITIVE FIX: Track multiple preview items
        self.preview_tk_images = [] # DEFINITIVE FIX: Hold multiple PhotoImage objects

        # --- Texture Loading ---
        self.border_textures = {}
        self._load_border_textures()
        self._create_procedural_textures()

        # Set default selections for the UI

    def _load_border_textures(self):
        """Loads default border textures into memory from the images directory."""
        # In a real app, this could scan a specific 'border_textures' folder.
        # For now, we'll explicitly load a known texture.
        try:
            brick_path = os.path.join(self.app.image_base_dir, "brick.png")
            if os.path.exists(brick_path):
                self.border_textures["Brick"] = Image.open(brick_path).convert("RGBA")
                print("Loaded 'Brick' border texture.")
            # Add more textures here, e.g., "stone.png" # type: ignore
        except Exception as e:
            print(f"Could not load default border textures: {e}")

    def _create_procedural_textures(self):
        """Creates simple, built-in border textures programmatically to offer more default options."""
        try:
            # Checkerboard
            size = 16
            c1 = (60, 60, 60, 255)  # Dark gray
            c2 = (80, 80, 80, 255)  # Lighter gray
            checker_img = Image.new("RGBA", (size, size), (0,0,0,0))
            draw = ImageDraw.Draw(checker_img)
            for y in range(0, size, size // 2):
                for x in range(0, size, size // 2):
                    color = c1 if (x // (size // 2) + y // (size // 2)) % 2 == 0 else c2
                    draw.rectangle([x, y, x + size // 2, y + size // 2], fill=color)
            self.border_textures["Checkerboard"] = checker_img

            # Diagonal Lines
            diag_img = Image.new("RGBA", (size, size), (0,0,0,0))
            draw = ImageDraw.Draw(diag_img)
            line_color = (100, 100, 100, 255)
            for i in range(-size, size, 4):
                draw.line([(i, 0), (i + size, size)], fill=line_color, width=1)
            self.border_textures["Diagonal Lines"] = diag_img

            # Vertical Stripes
            v_stripes_img = Image.new("RGBA", (size, size), c1)
            draw = ImageDraw.Draw(v_stripes_img)
            draw.rectangle([size // 2, 0, size, size], fill=c2)
            self.border_textures["Vertical Stripes"] = v_stripes_img
            print("Created procedural border textures.")
        except Exception as e:
            print(f"Could not create procedural textures: {e}")

    # --- Method Delegation ---

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, logical_size, render_size, shape_form="rect", path_data=None, is_segmented=False, relative_to=(0,0)):
        """Renders the selected border style onto a PIL image."""
        logical_w, logical_h = int(logical_size[0]), int(logical_size[1])
        render_w, render_h = int(render_size[0]), int(render_size[1])
        texture = list(self.border_textures.values())[0] if self.border_textures else None

        if not texture or (logical_w <= 0 and logical_h <= 0):
            messagebox.showwarning("Render Error", f"Could not render border. No texture found or size is invalid.")
            return None

        final_image = Image.new("RGBA", (render_w, render_h), (0,0,0,0))

        # --- DEFINITIVE FIX: Create a mask that grows inward ---
        # 1. Create a mask for the border by drawing a filled rectangle and then
        #    drawing a smaller, empty rectangle inside it.
        mask = Image.new("L", (render_w, render_h), 0)
        draw = ImageDraw.Draw(mask)

        # --- NEW: Handle path drawing ---

        # --- NEW: Adjust mask based on growth direction ---
        if shape_form == "path" and path_data:
            if is_segmented:
                for segment in path_data:
                    if len(segment) > 1:
                        relative_segment = [(p[0] - relative_to[0], p[1] - relative_to[1]) for p in segment]
                        draw.line(relative_segment, fill=255, width=1, joint='curve')

        # 2. Create a layer with the tiled texture
        tiled_texture_layer = Image.new("RGBA", (render_w, render_h))
        for y in range(0, render_h, texture.height):
            for x in range(0, render_w, texture.width):
                tiled_texture_layer.paste(texture, (x, y))

        # 3. Composite the tiled texture onto the final image using the mask
        final_image.paste(tiled_texture_layer, (0, 0), mask)
        return final_image

    def clear_preset_preview(self):
        """Removes the preset preview rectangle from the canvas if it exists."""
        pass

    # --- NEW: Smart Border Tool Methods ---

    def toggle_smart_border_mode(self):
        self.smart_manager.toggle_smart_border_mode()

    def start_drawing_stroke(self, event):
        self.smart_manager.start_drawing_stroke(event)

    def on_mouse_drag(self, event):
        self.smart_manager.on_mouse_drag(event)

    def on_mouse_up(self, event):
        self.smart_manager.on_mouse_up(event)

    # --- NEW: Preview Canvas Event Handlers ---
    def on_preview_down(self, event):
        self.smart_manager.on_preview_down(event)

    def on_preview_drag(self, event):
        self.smart_manager.on_preview_drag(event)

    def on_preview_up(self, event):
        self.smart_manager.on_preview_up(event)

    def on_preview_leave(self, event):
        self.smart_manager.on_preview_leave(event)

    def on_preview_move(self, event):
        self.smart_manager.on_preview_move(event)

    def update_preview_canvas(self, *args):
        self.smart_manager.update_preview_canvas(*args)

    def clear_detected_points(self):
        self.smart_manager.clear_detected_points()

    def on_erase_mode_toggle(self):
        self.smart_manager.on_erase_mode_toggle()

    def _update_canvas_brush_size(self, event=None):
        self.smart_manager._update_canvas_brush_size(event)

    # --- NEW: Preview Area Selection Methods ---
    def toggle_preview_selection_mode(self):
        self.smart_manager.toggle_preview_selection_mode()

    def finalize_border(self):
        self.smart_manager.finalize_border()