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
    
from uc_border_manager2 import PresetBorderManager
from uc_border_manager3 import SmartBorderManager

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

        # Instantiate the sub-managers
        self.preset_manager = PresetBorderManager(app, self)
        self.smart_manager = SmartBorderManager(app, self)

        self.next_border_id = 0

        self.preview_rect_ids = [] # DEFINITIVE FIX: Track multiple preview items
        self.preview_tk_images = [] # DEFINITIVE FIX: Hold multiple PhotoImage objects

        # --- UI-related state variables ---
        self.selected_preset = tk.StringVar()
        self.selected_style = tk.StringVar()
        self.border_thickness = tk.IntVar(value=10)
        self.border_width = tk.IntVar(value=100)
        self.border_feather = tk.IntVar(value=0)
        self.border_growth_direction = tk.StringVar(value="in")

        # --- Texture Loading ---
        self.border_textures = {}
        self._load_border_textures()
        self._create_procedural_textures()

        # Set default selections for the UI
        # --- FIX: Default to "None" to prevent an initial preview ---
        if self.border_textures:
            self.selected_style.set(list(self.border_textures.keys())[0])

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

    def apply_preset_border(self):
        self.preset_manager.apply_preset_border()

    def show_preset_preview(self, event=None):
        self.preset_manager.show_preset_preview(event)

    def apply_border_to_selection(self):
        pass # This method is now handled by the decal system

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, logical_size, render_size, shape_form="rect", path_data=None, is_segmented=False, relative_to=(0,0)):
        """Renders the selected border style onto a PIL image."""
        logical_w, logical_h = int(logical_size[0]), int(logical_size[1])
        render_w, render_h = int(render_size[0]), int(render_size[1])
        style = self.selected_style.get()
        texture = self.border_textures.get(style)

        if not texture or (logical_w <= 0 and logical_h <= 0):
            messagebox.showwarning("Render Error", f"Could not render border. Style '{style}' not found or size is invalid.")
            return None

        final_image = Image.new("RGBA", (render_w, render_h), (0,0,0,0))
        thickness = self.border_thickness.get()
        growth_direction = self.border_growth_direction.get()

        # --- DEFINITIVE FIX: Create a mask that grows inward ---
        # 1. Create a mask for the border by drawing a filled rectangle and then
        #    drawing a smaller, empty rectangle inside it.
        mask = Image.new("L", (render_w, render_h), 0)
        draw = ImageDraw.Draw(mask)

        # --- NEW: Handle path drawing ---

        # --- NEW: Adjust mask based on growth direction ---
        if growth_direction == 'in':
            if shape_form == "circle":
                draw.ellipse([0, 0, logical_w, logical_h], fill=255)
                if logical_w > thickness * 2 and logical_h > thickness * 2:
                    draw.ellipse([thickness, thickness, logical_w - thickness, logical_h - thickness], fill=0)
            elif shape_form == "rect":
                draw.rectangle([0, 0, logical_w, logical_h], fill=255)
                if logical_w > thickness * 2 and logical_h > thickness * 2:
                    draw.rectangle([thickness, thickness, logical_w - thickness, logical_h - thickness], fill=0)
            elif shape_form == "path" and path_data:
                # --- DEFINITIVE FIX: Draw lines for a solid border ---
                if is_segmented:
                    # Draw each segment as a line
                    for segment in path_data:
                        if len(segment) > 1:
                            # Adjust points to be relative to the component's top-left corner
                            relative_segment = [(p[0] - relative_to[0], p[1] - relative_to[1]) for p in segment]
                            draw.line(relative_segment, fill=255, width=1, joint='curve')
                else: # Original point-drawing logic for presets
                    min_x, min_y = min(p[0] for p in path_data), min(p[1] for p in path_data)
                    for p_x, p_y in path_data: # Draw points relative to their own bounding box
                        draw.point((p_x - min_x, p_y - min_y), fill=255)

        else: # 'out'
            if shape_form == "circle":
                draw.ellipse([0, 0, render_w, render_h], fill=255)
                if render_w > thickness * 2 and render_h > thickness * 2:
                    # The inner cutout is inset by the thickness.
                    draw.ellipse([thickness, thickness, render_w - thickness, render_h - thickness], fill=0)
            else: # Default to rectangle
                # Only draw the rectangle if it's not a path, to avoid overwriting the path mask
                if shape_form == "rect":
                    draw.rectangle([0, 0, render_w, render_h], fill=255)
                    if render_w > thickness * 2 and render_h > thickness * 2:
                        draw.rectangle([thickness, thickness, render_w - thickness, render_h - thickness], fill=0)
                elif shape_form == "path" and path_data:
                    if is_segmented:
                        for segment in path_data:
                            if len(segment) > 1:
                                relative_segment = [(p[0] - relative_to[0], p[1] - relative_to[1]) for p in segment]
                                draw.line(relative_segment, fill=255, width=1, joint='curve')
                    else:
                        # For outward growth, the points are drawn with an offset equal to the thickness
                        # inside the larger mask to create the padded effect.
                        min_x, min_y = min(p[0] for p in path_data), min(p[1] for p in path_data)
                        for p_x, p_y in path_data:
                            draw.point((p_x - min_x + thickness, p_y - min_y + thickness), fill=255)

        # --- NEW: Apply feathering if requested ---
        feather_amount = self.border_feather.get()
        if feather_amount > 0:
            # Use GaussianBlur for a smooth, high-quality feathering effect.
            mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_amount))

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
        self.preset_manager.clear_preset_preview()

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