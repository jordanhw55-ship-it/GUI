import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import math
import os
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[WARNING] NumPy not found. Smart Border tool performance will be significantly degraded.")
    

from uc_component import DraggableComponent

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.next_border_id = 0

        self.is_drawing = False # Flag for active mouse drag
        self.is_erasing_points = tk.BooleanVar(value=False)
        self.raw_border_points = set() # DEFINITIVE FIX: Use a set for faster lookups and automatic duplicate removal
        self.highlight_oval_ids = [] # Stores canvas IDs for the highlight points
        self.last_drawn_x = -1
        self.last_drawn_y = -1
        self.redraw_scheduled = False
        self.smart_brush_radius = tk.IntVar(value=15)
        self.smart_diff_threshold = tk.IntVar(value=50)
        self.smart_draw_skip = tk.IntVar(value=5)
        self.active_detection_image = None # The PIL image being processed
        self.active_detection_component = None # NEW: The component being analyzed
        self.cursor_circle_id = None # NEW: For the brush preview cursor
        # --- NEW: For composite image detection ---
        self.composite_x_offset = 0
        self.composite_y_offset = 0

        self.preview_scale_var = tk.DoubleVar(value=1.0) # NEW: For preview zoom
        self.preview_cursor_circle_id = None # NEW: For preview canvas cursor

        # --- NEW: Highlight Layer for Performance ---
        self.highlight_layer_image = None
        self.highlight_layer_tk = None
        self.highlight_layer_id = None
        self.highlight_color = (0, 255, 255, 255) # Cyan with full alpha

        self.preview_rect_ids = [] # DEFINITIVE FIX: Track multiple preview items

        # --- UI-related state variables ---
        self.selected_preset = tk.StringVar()
        self.selected_style = tk.StringVar()
        self.border_thickness = tk.IntVar(value=10)
        self.border_width = tk.IntVar(value=100) # NEW: For adjusting border component width as a percentage
        self.border_feather = tk.IntVar(value=0)
        self.preview_tk_images = [] # DEFINITIVE FIX: Hold multiple PhotoImage objects
        self.border_growth_direction = tk.StringVar(value="in") # NEW: 'in' or 'out'
        self.REDRAW_THROTTLE_MS = 50 # For smart border tool

        # --- Preset Definitions ---
        # A dictionary where each key is a preset name.
        # 'target_tile': The component tag the border is relative to.
        # 'shape_data': A list of ratios [x_offset, y_offset, width, height]
        #               relative to the target tile's dimensions.
        self.border_presets = {
            "Minimap Border": {
                "target_tile": "humanuitile01",
                "shape_type": "relative_rect",
                "shape_data": [0.0390625, 0.431640625, 0.5390625, 0.5390625]
            },
            "Action Bar Top Edge": {
                "target_tile": "humanuitile02",
                "shape_type": "relative_rect",
                "shape_data": [0.0, 0.0, 1.0, 0.05] # Thin bar across the top
            },
            # --- DEFINITIVE FIX: Expand "Top Border" to a multi-rect preset ---
            "Top Border": {
                "shape_type": "multi_rect",
                "shapes": [
                    { 
                        "target_tile": "humanuitile05", "shape_form": "rect", 
                        "shape_data": [0.0, 0.0859, 1.0, 0] # FIX: Span full width
                    },
                    { 
                        "target_tile": "humanuitile01", "shape_form": "rect", 
                        "shape_data": [0.0, 0.0859, 1.0, 0] # FIX: Span full width
                    },
                    { 
                        "target_tile": "humanuitile02", "shape_form": "rect", 
                        "shape_data": [0.0, 0.0859, 0.4238, 0] # FIX: 0 to 217
                    },
                    { 
                        "target_tile": "humanuitile02", "shape_form": "rect", 
                        # DEFINITIVE FIX: Use a more precise width to close the preview gap.
                        "shape_data": [0.701171875, 0.0859, 0.298828125, 0] # x=359/512, w=(512-359)/512
                    },
                    { 
                        "target_tile": "humanuitile03", "shape_form": "rect", 
                        "shape_data": [0.0, 0.0859, 1.0, 0] # FIX: Span full width
                    },
                    { 
                        "target_tile": "humanuitile04", "shape_form": "rect", 
                        # DEFINITIVE FIX: Correct relative width for the narrow tile04.
                        # The border (1 to 63) is wider than the tile (width 30).
                        "shape_data": [0.0, 0.0859, 2.1, 0] # FIX: 0 to 63
                    },
                    { 
                        "target_tile": "humanuitile06", "shape_form": "rect", 
                        "shape_data": [0.0, 0.0859, 1.0, 0] # FIX: Span full width
                    }
                ]
            },
            # --- FIX: I'm removing the duplicate "Top Border" and "HP Frame" definitions
            # to avoid conflicts and keep the preset list clean. The multi-span and span_rect
            # versions are the correct ones to use.
            # "Top Border": {
            #     "target_tile": "humanuitile05", "shape_type": "relative_rect", "shape_data": [0.0, 0.0, 1.0, 0.08]
            # },
            # "HP Frame": { # Spans from humanuitile01 to humanuitile02
            #     "target_tile": "humanuitile01", "shape_type": "relative_rect", "shape_data": [0.83984375, 0.888671875, 1.255859375, 0.046875]
            # },
            "Bottom Border": {
                "shape_type": "multi_rect",
                "shapes": [
                    # --- Side Frame components ---
                    {
                        "target_tile": "humanuitile05", "shape_form": "rect",
                        "shape_data": [0.9355, 0.3808, 0, 0.6172] # x=479, y=195, w=0 (thickness), h=316
                    },
                    {
                        "target_tile": "humanuitile01", "shape_form": "rect",
                        "shape_data": [0.7773, 0.3808, 0, 0.1055] # x=398, y=195, w=0 (thickness), h=54
                    },
                    {
                        "target_tile": "humanuitile02", "shape_form": "rect",
                        "shape_data": [0.9726, 0.4843, 0, 0] # x=498, y=249, w=0, h=0 (diagonal)
                    },
                    {
                        "target_tile": "humanuitile03", "shape_form": "rect",
                        "shape_data": [0.3339, 0.4004, 0, 0.0605] # x=171, y=205, w=0 (thickness), h=31
                    },
                    {
                        "target_tile": "humanuitile06", "shape_form": "rect",
                        "shape_data": [0.0605, 0.4004, 0, 0.6055] # x=31, y=205, w=0 (thickness), h=310
                    },
                    # --- Original Bottom Border component ---
                    {
                        "target_tile": "humanuitile05", "shape_form": "rect",
                        "shape_data": [0.0, 0.92, 1.0, 0.08]
                    }
                ]
            },
            "Side Frame": {
                "shape_type": "multi_span_path",
                "segments": [
                    { "type": "path", "path_coords": [(479, 511), (479, 186), (512, 186)] }
                ]
            },
            "Minimap Buttons": {
                "target_tile": "humanuitile01",
                "shape_type": "multi_rect",
                "shapes": [
                    { "shape_form": "rect", "shape_data": [0.6035, 0.4375, 0.0898, 0.0801] }, # Button 1
                    { "shape_form": "rect", "shape_data": [0.6035, 0.5234, 0.0898, 0.0781] }, # Button 2
                    { "shape_form": "rect", "shape_data": [0.6035, 0.6094, 0.0898, 0.0781] }, # Button 3
                    { "shape_form": "rect", "shape_data": [0.6035, 0.6953, 0.0898, 0.0781] }, # Button 4
                    { "shape_form": "circle", "shape_data": [0.6055, 0.8027, 0.0859, 0.0801] }  # Button 5 (Circle)
                ]
            },
            "Character Frame": {
                "target_tile": "humanuitile05", "shape_type": "relative_rect", "shape_data": [0.05, 0.1, 0.9, 0.15]
            },
            "Character Hub Frame": {
                "target_tile": "humanuitile06", "shape_type": "relative_rect", "shape_data": [0.0, 0.0, 1.0, 1.0]
            },
            "HP Frame": {
                "shape_type": "span_rect",
                "start_tile": "humanuitile01", "end_tile": "humanuitile02",
                "shape_data": [430, 455, 69, 24] # [start_x_offset, start_y_offset, end_x_offset, height_px]
            },
            "Mana Frame": {
                "shape_type": "span_rect",
                "start_tile": "humanuitile01", "end_tile": "humanuitile02",
                "shape_data": [430, 484, 69, 24] # [start_x_offset, start_y_offset, end_x_offset, height_px]
            },
            "Inventory Title": {
                "target_tile": "humanuitile-inventorycover", "shape_type": "relative_rect", "shape_data": [0.1, 0.05, 0.8, 0.1]
            },
            "Inventory Slots": {
                "target_tile": "humanuitile-inventorycover", "shape_type": "relative_rect", "shape_data": [0.1, 0.2, 0.8, 0.75]
            },
            "Spells Slots": {
                "target_tile": "humanuitile02", "shape_type": "relative_rect", "shape_data": [0.05, 0.1, 0.9, 0.8]
            },
            "Time Indicator Border": {
                "target_tile": "humanuitile-timeindicatorframe", "shape_type": "relative_rect", "shape_data": [0.0, 0.0, 1.0, 1.0]
            }
        }
        # --- Texture Loading ---
        self.border_textures = {}
        self._load_border_textures()
        self._create_procedural_textures()

        # Set default selections for the UI
        # --- FIX: Default to "None" to prevent an initial preview ---
        self.selected_preset.set("None")
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

    def apply_preset_border(self):
        """Applies the selected border preset to the canvas."""
        preset_name = self.selected_preset.get()
        # --- NEW: Clear the preview when applying the border ---
        self.clear_preset_preview()

        if not preset_name:
            messagebox.showwarning("Preset Required", "Please select a border preset.")
            return

        preset = self.border_presets[preset_name]

        # --- NEW: Handle multi-shape presets ---
        if preset.get("shape_type") == "multi_rect":
            shapes_to_create = preset.get("shapes", [])
        elif preset.get("shape_type") == "relative_rect":
            # For backward compatibility, treat single presets as a list with one item
            shapes_to_create = [{"shape_data": preset.get("shape_data")}]
        elif preset.get("shape_type") == "multi_span_path":
            # For the new complex path type, we create one component per segment
            shapes_to_create = preset.get("segments", [])
        else:
            shapes_to_create = []

        for shape in shapes_to_create:
            # --- NEW: Handle different shape data structures ---
            shape_data = shape.get("shape_data")
            shape_type = preset.get("shape_type")

            if shape_type == "multi_span_path":
                # For paths, the logic is different. We'll handle it inside the loop.
                pass
            elif not shape_data:
                continue

            thickness = self.border_thickness.get()
            growth_direction = self.border_growth_direction.get()

            if shape_type == "multi_span_path":
                segment_type = shape.get("type")
                if segment_type == "line":
                    start_tile = self.app.components.get(shape["start_tile"])
                    end_tile = self.app.components.get(shape["end_tile"])
                    if not start_tile or not end_tile: continue

                    # --- DEFINITIVE FIX: Use absolute coordinates within the tile's space ---
                    start_x_world = start_tile.world_x1 + shape["start_coords"][0]
                    start_y_world = start_tile.world_y1 + shape["start_coords"][1]
                    end_x_world = end_tile.world_x1 + shape["end_coords"][0]
                    end_y_world = end_tile.world_y1 + shape["end_coords"][1]

                    # --- DEFINITIVE FIX: Correctly calculate the world Y position ---
                    border_x = min(start_x_world, end_x_world)
                    border_y = min(start_y_world, end_y_world) # Use the calculated world Y
                    border_w = abs(end_x_world - start_x_world)
                    border_h = abs(end_y_world - start_y_world) if abs(end_y_world - start_y_world) > 0 else thickness
                    render_w, render_h = border_w, border_h
                    shape_form = "rect"

                elif segment_type == "path":
                    path_coords = shape["path_coords"]
                    path_tile = self.app.components.get(shape.get("target_tile"))
                    if not path_coords: continue

                    # If a target tile is specified, treat coords as relative. Otherwise, treat as absolute world coords.
                    offset_x = path_tile.world_x1 if path_tile else 0
                    offset_y = path_tile.world_y1 if path_tile else 0
                    world_path = [(offset_x + x, offset_y + y) for x, y in path_coords]

                    min_x = min(p[0] for p in world_path)
                    max_x = max(p[0] for p in world_path)
                    max_y = max(p[1] for p in world_path)
                    min_y = min(p[1] for p in world_path)

                    border_x, border_y = min_x, min_y
                    border_w, border_h = max_x - min_x, max_y - min_y
                    render_w, render_h = border_w, border_h
                    shape_form = "path"
                    target_comp = path_tile # Can be None, which is correct
            else: # Existing rect/circle logic for multi_rect and relative_rect
                # --- NEW: Target validation moved here, as it's only relevant for relative presets ---
                target_tile_name = shape.get("target_tile") or preset.get("target_tile")
                target_comp = self.app.components.get(target_tile_name)

                if not target_comp:
                    messagebox.showerror("Error", f"Target tile '{target_tile_name}' for preset not found on canvas.")
                    continue

                rel_x, rel_y, rel_w, rel_h = shape["shape_data"]
                parent_w = target_comp.world_x2 - target_comp.world_x1
                parent_h = target_comp.world_y2 - target_comp.world_y1
                width_multiplier = self.border_width.get() / 100.0
                # --- DEFINITIVE FIX: Use thickness slider if relative width is 0 ---
                border_w = (parent_w * rel_w) * width_multiplier if rel_w > 0 else self.border_thickness.get()
                # --- DEFINITIVE FIX: Use thickness slider if relative height is 0 ---
                border_h = (parent_h * rel_h) if rel_h > 0 else self.border_thickness.get()
                border_x = target_comp.world_x1 + (parent_w * rel_x)
                border_y = target_comp.world_y1 + (parent_h * rel_y)
                render_w, render_h = border_w, border_h
                shape_form = shape.get("shape_form", "rect")

            if growth_direction == 'out':
                border_x -= thickness; border_y -= thickness
                render_w += thickness * 2; render_h += thickness * 2

            border_tag = f"preset_border_{self.next_border_id}"
            self.next_border_id += 1
            border_comp = DraggableComponent(self.app, border_tag, border_x, border_y, border_x + render_w, border_y + render_h, "blue", "BORDER")
            border_comp.is_draggable = False
            if target_comp: border_comp.parent_tag = target_comp.tag # Assign parent if one exists

            # --- FIX: Use the determined shape_form, not the one from the shape dictionary ---
            border_image = self._render_border_image((border_w, border_h), (render_w, render_h), shape_form, path_data=world_path if shape_form == 'path' else None)
            if not border_image: continue

            border_comp.set_image(border_image)
            self.app.components[border_tag] = border_comp
            self.app.canvas.tag_lower(border_tag, "draggable")
            self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        self.app.redraw_all_zoomable()
        print(f"Applied preset '{preset_name}'.")

    def _get_shapes_from_preset(self, preset):
        """Helper to return a list of shapes from a preset, handling single and multi-shape types."""
        return preset.get("shapes", [{"shape_form": "rect", "shape_data": preset.get("shape_data")}])

    def show_preset_preview(self, event=None):
        """Draws a temporary, semi-transparent rectangle to preview the preset border."""
        # --- FIX: Do not show preview if the border tab is not the active context ---
        # This prevents the preview from appearing unexpectedly during startup or tab switching.
        if not self.app.is_border_tab_active():
            return

        # First, clear any existing preview
        self.clear_preset_preview()

        preset_name = self.selected_preset.get()
        if not preset_name:
            return

        preset = self.border_presets.get(preset_name)
        if not preset:
            return

        shapes_to_preview = []

        # --- DEFINITIVE FIX: Restructure logic to handle each shape type explicitly ---
        shape_type = preset.get("shape_type")

        if shape_type == "multi_span_path":
            for segment in preset.get("segments", []):
                thickness = self.border_thickness.get()
                if segment["type"] == "line":
                    start_tile = self.app.components.get(segment["start_tile"])
                    end_tile = self.app.components.get(segment["end_tile"])
                    if not start_tile or not end_tile: continue

                    # --- DEFINITIVE FIX: Use absolute coordinates for preview as well ---
                    start_x_world = start_tile.world_x1 + segment["start_coords"][0]
                    start_y_world = start_tile.world_y1 + segment["start_coords"][1]
                    end_x_world = end_tile.world_x1 + segment["end_coords"][0]
                    end_y_world = end_tile.world_y1 + segment["end_coords"][1]

                    # --- DEFINITIVE FIX: Correctly calculate the world Y position for the preview ---
                    shapes_to_preview.append({
                        'x': min(start_x_world, end_x_world), 'y': min(start_y_world, end_y_world),
                        'w': abs(end_x_world - start_x_world), 'h': abs(end_y_world - start_y_world) if abs(end_y_world - start_y_world) > 0 else thickness,
                        'form': 'rect'
                    })
                elif segment["type"] == "path":
                    path_tile = self.app.components.get(segment.get("target_tile"))
                    if not segment.get("path_coords"): continue

                    # If a target tile is specified, treat coords as relative. Otherwise, treat as absolute world coords.
                    offset_x = path_tile.world_x1 if path_tile else 0
                    offset_y = path_tile.world_y1 if path_tile else 0
                    world_path = [(offset_x + x, offset_y + y) for x, y in segment["path_coords"]]
                    
                    min_x, max_x = min(p[0] for p in world_path), max(p[0] for p in world_path)
                    min_y, max_y = min(p[1] for p in world_path), max(p[1] for p in world_path)
                    
                    shapes_to_preview.append({
                        'x': min_x, 'y': min_y, 'w': max_x - min_x, 'h': max_y - min_y,
                        'form': 'path', 'path_data': world_path
                    })
        # --- DEFINITIVE FIX: Handle the new "span_rect" shape type ---
        elif shape_type == "span_rect":
            start_tile = self.app.components.get(preset["start_tile"])
            end_tile = self.app.components.get(preset["end_tile"])
            if not start_tile or not end_tile: return

            start_x_offset, start_y_offset, end_x_offset, height_px = preset["shape_data"]

            # --- LOGIC FIX: Correctly scale pixel offsets to world coordinates ---
            # Calculate scale factor based on the tile's original image size (e.g., 512x512) vs its current world size.
            start_tile_world_w = start_tile.world_x2 - start_tile.world_x1
            start_tile_world_h = start_tile.world_y2 - start_tile.world_y1
            start_scale_w = start_tile_world_w / (start_tile.original_pil_image.width if start_tile.original_pil_image else 512.0)
            start_scale_h = start_tile_world_h / (start_tile.original_pil_image.height if start_tile.original_pil_image else 512.0)

            end_tile_world_w = end_tile.world_x2 - end_tile.world_x1
            end_tile_world_h = end_tile.world_y2 - end_tile.world_y1
            end_scale_w = end_tile_world_w / (end_tile.original_pil_image.width if end_tile.original_pil_image else 512.0)
            end_scale_h = end_tile_world_h / (end_tile.original_pil_image.height if end_tile.original_pil_image else 512.0)

            # Calculate the final world coordinates using the scaled offsets
            border_x1 = start_tile.world_x1 + (start_x_offset * start_scale_w)
            border_y1 = start_tile.world_y1 + (start_y_offset * start_scale_h)
            border_x2 = end_tile.world_x1 + (end_x_offset * end_scale_w)
            border_y2 = border_y1 + (height_px * start_scale_h)

            border_w = (border_x2 - border_x1) + 1 # Add 1px to fix off-by-one rendering error
            border_h = border_y2 - border_y1
            
            # Since span_rect is a single shape, we wrap it in a list to use the common render logic below
            shapes_to_preview.append({'x': border_x1, 'y': border_y1, 'w': border_w, 'h': border_h, 'form': 'rect'})

        elif shape_type == "multi_rect":
            shapes_to_preview = []
            width_multiplier = self.border_width.get() / 100.0

            # --- DEFINITIVE FIX: Get the global target, but don't fail if it's not there ---
            global_target_comp = self.app.components.get(preset.get("target_tile"))

            for i, shape in enumerate(preset.get("shapes", [])):
                if not shape.get("shape_data"): continue

                # --- DEFINITIVE FIX: Allow per-shape target_tile in multi_rect ---
                # If the shape has its own target, use it. Otherwise, use the preset's global target.
                shape_target_comp = self.app.components.get(shape.get("target_tile")) or global_target_comp
                if not shape_target_comp: continue

                shape_parent_w = shape_target_comp.world_x2 - shape_target_comp.world_x1
                shape_parent_h = shape_target_comp.world_y2 - shape_target_comp.world_y1

                rel_x, rel_y, rel_w, rel_h = shape["shape_data"]

                border_w = (shape_parent_w * rel_w) * width_multiplier
                # --- DEFINITIVE FIX: Use thickness for width/height if relative value is 0 ---
                border_w = (shape_parent_w * rel_w) * width_multiplier if rel_w > 0 else self.border_thickness.get()
                border_h = (shape_parent_h * rel_h) if rel_h > 0 else self.border_thickness.get()
                border_x1 = shape_target_comp.world_x1 + (shape_parent_w * rel_x)
                border_y1 = shape_target_comp.world_y1 + (shape_parent_h * rel_y)
                
                shapes_to_preview.append({
                    'x': border_x1, 'y': border_y1,
                    'w': border_w, 'h': border_h,
                    'form': shape.get("shape_form", "rect") # Pass the shape form to the preview
                })
            
            if not shapes_to_preview: return # No valid shapes found

        elif shape_type == "relative_rect": # Handle the original "relative_rect"
            target_comp = self.app.components.get(preset["target_tile"])
            if not target_comp:
                return

            # Calculate absolute coordinates from relative data
            parent_w = target_comp.world_x2 - target_comp.world_x1
            parent_h = target_comp.world_y2 - target_comp.world_y1
            rel_x, rel_y, rel_w, rel_h = preset["shape_data"]

            width_multiplier = self.border_width.get() / 100.0
            # --- DEFINITIVE FIX: Use thickness for width if relative value is 0 ---
            border_w = (parent_w * rel_w) * width_multiplier if rel_w > 0 else self.border_thickness.get()
            # --- DEFINITIVE FIX: Use thickness slider if relative height is 0 for preview ---
            border_h = (parent_h * rel_h) if rel_h > 0 else self.border_thickness.get()

            border_x1 = target_comp.world_x1 + (parent_w * rel_x)
            border_y1 = target_comp.world_y1 + (parent_h * rel_y)
            border_x2 = border_x1 + border_w
            border_y2 = border_y1 + border_h
            
            # Also wrap single rects in a list to use the common render logic
            shapes_to_preview.append({'x': border_x1, 'y': border_y1, 'w': border_w, 'h': border_h, 'form': 'rect'})

        # --- DEFINITIVE FIX: Render the actual border for the preview ---
        # This now loops through all shapes calculated above (even if it's just one)
        for shape_coords in shapes_to_preview:
            border_x1, border_y1, border_w, border_h, shape_form = shape_coords['x'], shape_coords['y'], shape_coords['w'], shape_coords['h'], shape_coords['form']
            
            growth_direction = self.border_growth_direction.get()
            thickness = self.border_thickness.get()
            
            render_w_world, render_h_world = border_w, border_h
            preview_x1, preview_y1 = border_x1, border_y1
            if growth_direction == 'out':
                preview_x1 -= thickness
                preview_y1 -= thickness
                render_w_world += thickness * 2
                render_h_world += thickness * 2

            preview_image = self._render_border_image((border_w, border_h), (render_w_world, render_h_world), shape_form, shape_coords.get('path_data'))
            if not preview_image: continue

            self.preview_tk_image = ImageTk.PhotoImage(preview_image)
            self.preview_tk_images.append(ImageTk.PhotoImage(preview_image))

            sx1, sy1 = self.app.camera.world_to_screen(preview_x1, preview_y1)
            preview_id = self.canvas.create_image(
                sx1, sy1,
                anchor=tk.NW,
                image=self.preview_tk_images[-1], # Use the most recently added image
                tags=("border_preview",)
            )
            self.preview_rect_ids.append(preview_id)

        # --- FIX: Ensure the preview is always drawn on top of other items ---
        self.canvas.tag_raise("border_preview")

    def apply_border_to_selection(self):
        pass # This method is now handled by the decal system

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, logical_size, render_size, shape_form="rect", path_data=None):
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
                # For smart borders, path_data is a list of points. We draw them individually.
                # The path_data is in world coordinates. We need to make it relative to the render box.
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
        if self.preview_rect_ids:
            self.canvas.delete("border_preview")
            self.preview_rect_ids.clear()
            self.preview_tk_images.clear()

    # --- NEW: Smart Border Tool Methods ---

    def toggle_smart_border_mode(self):
        """Activates or deactivates the smart border detection tool."""
        if not NUMPY_AVAILABLE:
            messagebox.showerror("Dependency Missing", "The Smart Border tool requires the 'numpy' library for performance. Please install it by running:\npip install numpy")
            self.app.smart_border_mode_active = False # Ensure it's off
            return

        self.app.smart_border_mode_active = not self.app.smart_border_mode_active

        if self.app.smart_border_mode_active:
            # --- DEFINITIVE REWRITE: Create a composite image from all main tiles ---
            # 1. Find all main tile components with images.
            tile_components = [
                c for c in self.app.components.values() 
                if c.original_pil_image and not c.is_decal and not c.is_dock_asset
            ]
            if not tile_components:
                messagebox.showwarning("No Images", "No image tiles found to analyze.")
                self.app.smart_border_mode_active = False
                return

            # 2. Calculate the overall bounding box in world coordinates.
            min_x = min(c.world_x1 for c in tile_components)
            min_y = min(c.world_y1 for c in tile_components)
            max_x = max(c.world_x2 for c in tile_components)
            max_y = max(c.world_y2 for c in tile_components)

            # 3. Store the top-left corner as the world offset.
            self.composite_x_offset = min_x
            self.composite_y_offset = min_y

            # 4. Create a new composite image.
            composite_width = int(max_x - min_x)
            composite_height = int(max_y - min_y)
            self.active_detection_image = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))

            # 5. Paste each tile's image onto the composite.
            for comp in tile_components:
                # We need to resize the component's original image to its current world dimensions
                # before pasting to handle any resizing that has occurred.
                world_w = int(comp.world_x2 - comp.world_x1)
                world_h = int(comp.world_y2 - comp.world_y1)
                if world_w <= 0 or world_h <= 0: continue
                
                resized_img = comp.original_pil_image.resize((world_w, world_h), Image.Resampling.LANCZOS)
                paste_x = int(comp.world_x1 - self.composite_x_offset)
                paste_y = int(comp.world_y1 - self.composite_y_offset)
                self.active_detection_image.paste(resized_img, (paste_x, paste_y), resized_img)

            self.app.ui_manager.smart_border_btn.config(text="Smart Border (Active)", relief='sunken', bg='#ef4444')
            self.canvas.config(cursor="crosshair")
            
            if self.highlight_layer_id is None:
                self.highlight_layer_id = self.canvas.create_image(0, 0, anchor=tk.NW, state='normal', tags="smart_border_highlight_layer")

            print(f"Smart Border mode ENABLED. Analyzing composite image of {len(tile_components)} tiles.")
        else:
            self.active_detection_image = None
            self.clear_detected_points()
            self.active_detection_component = None # Clear the component reference
            self.app.ui_manager.smart_border_btn.config(text="Smart Border Tool", relief='flat', bg='#0e7490')
            self.canvas.config(cursor="")
            print("Smart Border mode DISABLED.")
            # Reset offsets
            self.composite_x_offset = 0
            self.composite_y_offset = 0

            # --- FIX: Hide the highlight layer when the tool is deactivated ---
            if self.highlight_layer_id:
                self.canvas.itemconfig(self.highlight_layer_id, state='hidden')
            
            # --- DEFINITIVE FIX for crash on finalize ---
            # Explicitly clear references to the large image objects to allow garbage collection.
            self.highlight_layer_image = None
            self.highlight_layer_tk = None


            self._hide_brush_cursor() # NEW: Hide the cursor when disabling

    def _find_image_for_detection(self):
        """Finds a suitable component to use for border detection."""
        # --- DEFINITIVE FIX: Prioritize the component under the mouse cursor ---
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        
        items_under_cursor = self.canvas.find_overlapping(x-1, y-1, x+1, y+1)
        for item_id in reversed(items_under_cursor):
            tags = self.canvas.gettags(item_id)
            if not tags: continue
            # --- DEFINITIVE FIX: Ignore the highlight layer itself during detection ---
            if "smart_border_highlight_layer" in tags:
                continue

            comp = self.app.components.get(tags[0])
            if comp and comp.original_pil_image and not comp.is_decal and not comp.is_dock_asset:
                return comp # Found a valid component under the mouse, use it.

        # Fallback: If no component was found under the mouse, use the currently selected one.
        if self.app.selected_component_tag:
            comp = self.app.components.get(self.app.selected_component_tag)
            if comp and comp.original_pil_image:
                return comp
        return None

    def on_mouse_down(self, event):
        """Handles the start of a drawing or erasing stroke."""
        if not self.app.smart_border_mode_active or not self.active_detection_image:
            return

        self.is_drawing = True
        self.last_drawn_x, self.last_drawn_y = event.x, event.y
        self._update_brush_cursor(event) # NEW: Update cursor on mouse down

        if self.is_erasing_points.get():
            self._process_erasure_at_point(event)
        else:
            self._process_detection_at_point(event)

    def on_mouse_drag(self, event):
        """Handles continuous drawing or erasing."""
        if not self.is_drawing: return
        self._update_brush_cursor(event) # NEW: Update cursor on drag

        draw_skip = self.smart_draw_skip.get()
        distance = math.sqrt((event.x - self.last_drawn_x)**2 + (event.y - self.last_drawn_y)**2)
        if distance < draw_skip:
            return

        self.last_drawn_x, self.last_drawn_y = event.x, event.y

        if self.is_erasing_points.get():
            self._process_erasure_at_point(event, defer_redraw=True)
        else:
            self._process_detection_at_point(event, defer_redraw=True)

        if not self.redraw_scheduled:
            self.redraw_scheduled = True
            self.app.master.after(self.REDRAW_THROTTLE_MS, self._deferred_redraw)

    def on_mouse_up(self, event):
        """Finalizes a drawing or erasing stroke."""
        self.is_drawing = False
        if self.redraw_scheduled:
            self.app.master.after_cancel(self._deferred_redraw)
        self._deferred_redraw()

    # --- NEW: Preview Canvas Event Handlers ---
    def on_preview_down(self, event):
        """Starts erasure in the zoomed preview."""
        self._update_preview_cursor(event)
        self._process_preview_erasure(event)

    def on_preview_drag(self, event):
        """Allows continuous erasure in the zoomed preview, with throttling."""
        self._update_preview_cursor(event)
        self._process_preview_erasure(event, defer_redraw=True)

        if not self.redraw_scheduled:
            self.redraw_scheduled = True
            self.app.master.after(self.REDRAW_THROTTLE_MS, self._deferred_redraw)

    def on_preview_up(self, event):
        """Ensures final state is immediately drawn after preview dragging stops."""
        if self.redraw_scheduled:
            self.app.master.after_cancel(self._deferred_redraw)
        self._deferred_redraw()

    def on_preview_leave(self, event):
        """Hides the cursor when the mouse leaves the preview canvas."""
        if self.preview_cursor_circle_id:
            self.app.ui_manager.border_preview_canvas.itemconfig(self.preview_cursor_circle_id, state='hidden')

    def on_preview_move(self, event):
        """Updates the preview cursor position."""
        self._update_preview_cursor(event)

    def _deferred_redraw(self):
        """Redraws the highlight points after a throttle delay."""
        if not self.app.master.winfo_exists(): return
        self._update_highlights()
        self.update_preview_canvas() # Also update the preview canvas
        self.redraw_scheduled = False

    def _process_detection_at_point(self, event, defer_redraw=False):
        """The core logic to detect border points under the brush."""
        brush_radius = self.smart_brush_radius.get()
        diff_threshold = self.smart_diff_threshold.get()
        img = self.active_detection_image
        if not img: return

        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)

        # --- REWRITE: Convert world coordinates to composite image coordinates ---
        # The composite image is 1:1 with world units, so no scaling is needed.
        # We just need to offset by the composite's top-left corner.
        img_x_center = int(world_x - self.composite_x_offset)
        img_y_center = int(world_y - self.composite_y_offset) # type: ignore

        # --- DEFINITIVE REWRITE: Use NumPy for high-performance edge detection ---
        # 1. Define the bounding box for the brush area in image coordinates.
        x1, y1 = img_x_center - brush_radius, img_y_center - brush_radius
        x2, y2 = img_x_center + brush_radius, img_y_center + brush_radius

        # 2. Ensure the box is within the image bounds.
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.width, x2), min(img.height, y2)
        if x1 >= x2 or y1 >= y2: return

        # 3. Crop the brush area and convert to a NumPy array for fast processing.
        brush_area_img = img.crop((x1, y1, x2, y2))
        # We only need the alpha channel for edge detection.
        alpha_channel = np.array(brush_area_img.getchannel('A'))

        # 4. Perform edge detection using array slicing (much faster than loops).
        # Calculate horizontal and vertical gradients.
        grad_x = np.abs(alpha_channel[:, 1:] - alpha_channel[:, :-1])
        grad_y = np.abs(alpha_channel[1:, :] - alpha_channel[:-1, :])

        # Find pixels where the gradient exceeds the threshold.
        edge_mask = np.zeros_like(alpha_channel, dtype=bool)
        edge_mask[:, :-1] |= (grad_x > diff_threshold)
        edge_mask[:-1, :] |= (grad_y > diff_threshold)

        # 5. Get the coordinates of the edge pixels within the brush area.
        edge_y_coords, edge_x_coords = np.where(edge_mask)

        # 6. Convert local brush coordinates back to world coordinates and add to the set.
        # This is a bulk operation, which is very fast.
        world_x_coords = edge_x_coords + x1 + self.composite_x_offset
        world_y_coords = edge_y_coords + y1 + self.composite_y_offset
        
        new_points = set(zip(world_x_coords, world_y_coords))
        self.raw_border_points.update(new_points)

        if not defer_redraw:
            self._update_highlights()

    def _process_erasure_at_point(self, event, defer_redraw=False):
        """Erases detected points under the brush."""
        if not self.raw_border_points: return

        brush_radius_world = self.smart_brush_radius.get() / self.app.camera.zoom_scale
        erase_cx, erase_cy = self.app.camera.screen_to_world(event.x, event.y)

        new_points = []
        # Use a copy of the set to iterate over while modifying it
        points_to_remove = {p for p in self.raw_border_points if ((p[0] - erase_cx)**2 + (p[1] - erase_cy)**2) <= brush_radius_world**2}
        
        self.raw_border_points.difference_update(points_to_remove)

        if not defer_redraw:
            self._update_highlights()

    def _process_preview_erasure(self, event, defer_redraw=False):
        """Erases points from the raw_border_points list based on the zoomed preview brush."""
        if not self.raw_border_points or not self.active_detection_component: return

        scale = self.preview_scale_var.get()
        if scale == 0: return

        preview_canvas = self.app.ui_manager.border_preview_canvas
        preview_w = preview_canvas.winfo_width()
        preview_h = preview_canvas.winfo_height()

        # The preview is centered on the component's center
        comp = self.active_detection_component
        center_x = (comp.world_x1 + comp.world_x2) / 2
        center_y = (comp.world_y1 + comp.world_y2) / 2

        # 1. Determine center of erasure in WORLD coordinates from preview canvas click
        zoom_x = event.x - preview_w / 2
        zoom_y = event.y - preview_h / 2
        world_x_center = (zoom_x / scale) + center_x
        world_y_center = (zoom_y / scale) + center_y

        # 2. Determine erasure radius in WORLD coordinates
        # Fixed preview eraser size (10 preview canvas pixels) divided by the zoom scale.
        world_eraser_radius = 10 / scale

        # 3. Find and remove points from raw_border_points
        new_raw_border_points = []
        erased_count = 0

        for p_x, p_y in self.raw_border_points:
            dist_sq = (p_x - world_x_center)**2 + (p_y - world_y_center)**2
            if dist_sq > world_eraser_radius**2:
                new_raw_border_points.append((p_x, p_y))
            else:
                erased_count += 1

        if erased_count > 0:
            self.raw_border_points = new_raw_border_points
            if not defer_redraw:
                self._deferred_redraw()
            else:
                self.status_message.set(f"Preview Eraser: Removed {erased_count} points. Redraw pending.")


    def _create_brush_cursor(self):
        """Creates the circular brush preview on the main canvas if it doesn't exist."""
        if self.cursor_circle_id is None:
            self.cursor_circle_id = self.canvas.create_oval(0, 0, 0, 0, outline="cyan", width=1, state='hidden')

    def _update_brush_cursor(self, event):
        """Updates the position and appearance of the brush cursor."""
        self._create_brush_cursor()
        if not self.cursor_circle_id: return

        radius = self.smart_brush_radius.get()
        color = "red" if self.is_erasing_points.get() else "cyan"
        width = 2 if self.is_erasing_points.get() else 1

        x1, y1 = event.x - radius, event.y - radius
        x2, y2 = event.x + radius, event.y + radius
        
        self.canvas.coords(self.cursor_circle_id, x1, y1, x2, y2)
        self.canvas.itemconfig(self.cursor_circle_id, outline=color, width=width, state='normal')

    def _hide_brush_cursor(self):
        """Hides the brush cursor."""
        if self.cursor_circle_id:
            self.canvas.itemconfig(self.cursor_circle_id, state='hidden')

    def _update_preview_cursor(self, event):
        """Updates the position and appearance of the preview brush cursor."""
        preview_canvas = self.app.ui_manager.border_preview_canvas
        if not preview_canvas: return

        if self.preview_cursor_circle_id is None:
            self.preview_cursor_circle_id = preview_canvas.create_oval(0, 0, 0, 0, outline="red", width=2, state='hidden')

        radius = 10 # Fixed radius for preview eraser
        x1, y1 = event.x - radius, event.y - radius
        x2, y2 = event.x + radius, event.y + radius

        if self.preview_cursor_circle_id:
            preview_canvas.coords(self.preview_cursor_circle_id, x1, y1, x2, y2)
            preview_canvas.itemconfig(self.preview_cursor_circle_id, state='normal')

    def _update_highlights(self):
        """Requests a full canvas redraw, which now includes the highlight layer."""
        self.app.redraw_all_zoomable()

    def update_preview_canvas(self, *args):
        """Redraws the stored border points on the preview canvas with the current zoom scale."""
        preview_canvas = self.app.ui_manager.border_preview_canvas
        if not preview_canvas: return

        preview_canvas.delete("preview_dot")

        if not self.raw_border_points or not self.active_detection_component:
            return

        scale = self.preview_scale_var.get()
        preview_w = preview_canvas.winfo_width()
        preview_h = preview_canvas.winfo_height()

        # Center the preview on the component being analyzed
        comp = self.active_detection_component
        center_x = (comp.world_x1 + comp.world_x2) / 2
        center_y = (comp.world_y1 + comp.world_y2) / 2

        for raw_x, raw_y in self.raw_border_points:
            # 1. Translate point relative to component's world center
            rel_x = raw_x - center_x
            rel_y = raw_y - center_y

            # 2. Apply zoom scale
            zoom_x = rel_x * scale
            zoom_y = rel_y * scale

            # 3. Translate point to preview canvas center
            preview_x = zoom_x + preview_w / 2
            preview_y = zoom_y + preview_h / 2

            # Draw point
            preview_canvas.create_oval(
                preview_x, preview_y, preview_x + 2, preview_y + 2,
                fill="cyan", outline="", tags="preview_dot"
            )

    def clear_detected_points(self):
        """Clears all detected points and their highlights."""
        self.raw_border_points.clear()
        self._update_highlights()
        self.update_preview_canvas()
        print("Cleared all detected border points.")

    def finalize_border(self):
        """Creates a new component from the detected border points."""
        if not self.raw_border_points:
            messagebox.showwarning("No Points", "No border points have been detected to finalize.")
            return
        
        thickness = self.border_thickness.get()
        growth_direction = self.border_growth_direction.get()

        # 1. Get the logical bounding box of the detected points in WORLD coordinates
        points_list = list(self.raw_border_points) # Convert set to list for indexing
        min_x = int(min(p[0] for p in points_list))
        min_y = int(min(p[1] for p in points_list))
        max_x = int(max(p[0] for p in points_list))
        max_y = int(max(p[1] for p in points_list))

        logical_w = max_x - min_x + 1
        logical_h = max_y - min_y + 1 # type: ignore

        if logical_w <= 0 or logical_h <= 0:
            messagebox.showerror("Error", "Could not create border from points (invalid size).")
            return

        # 2. Calculate the final render size and component position based on growth
        render_w, render_h = logical_w, logical_h
        comp_x, comp_y = min_x, min_y
        if growth_direction == 'out':
            comp_x -= thickness
            comp_y -= thickness
            render_w += thickness * 2
            render_h += thickness * 2
        
        # 3. Adjust points to be relative to the new component's top-left corner for rendering
        relative_points = [(p[0] - comp_x, p[1] - comp_y) for p in points_list]
        
        # 4. Render the image using the same function as presets, passing the relative points
        # The logical size is now the render size because the points are already relative.
        border_image = self._render_border_image((render_w, render_h), (render_w, render_h), shape_form="path", path_data=relative_points)
        if not border_image: return

        # 5. Create the new component with the correct world coordinates
        border_tag = f"smart_border_{self.next_border_id}"
        self.next_border_id += 1
        border_comp = DraggableComponent(self.app, border_tag, comp_x, comp_y, comp_x + render_w, comp_y + render_h, "blue", "BORDER")
        border_comp.is_draggable = True # Make it draggable
        border_comp.set_image(border_image)

        self.app.components[border_tag] = border_comp
        self.app._bind_component_events(border_tag)
        self.app.canvas.tag_raise(border_tag)
        self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        # --- DEFINITIVE FIX: Clean up and exit smart mode BEFORE showing the success message ---
        # This ensures the state is fully reset before the user can interact with the UI again.
        self.toggle_smart_border_mode()
        messagebox.showinfo("Success", f"Created new border component: {border_tag}")