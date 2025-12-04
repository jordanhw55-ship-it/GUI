import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import numpy as np
import os

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None
from uc_component import DraggableComponent

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.next_border_id = 0
        self.preview_rect_ids = [] # DEFINITIVE FIX: Track multiple preview items

        # --- UI-related state variables ---
        self.selected_preset = tk.StringVar()
        self.selected_style = tk.StringVar()
        self.border_thickness = tk.IntVar(value=10)
        self.border_width = tk.IntVar(value=100) # NEW: For adjusting border component width as a percentage
        self.border_feather = tk.IntVar(value=0)
        self.preview_tk_images = [] # DEFINITIVE FIX: Hold multiple PhotoImage objects
        self.border_growth_direction = tk.StringVar(value="in") # NEW: 'in' or 'out'

        # --- NEW: Interactive Tracing State ---
        self.is_tracing = False
        self.traced_points = []
        self.trace_preview_id = None
        self.last_trace_point = None # NEW: For freehand drag-tracing
        self.trace_button = None # Will be set by UIManager
        self.magic_trace_button = None # Will be set by UIManager
        self.magic_wand_button = None # Will be set by UIManager
        self.finish_button = None # Will be set by UIManager

        # --- Preset Definitions ---
        # A dictionary where each key is a preset name.
        self.is_magic_wand_active = False
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
        if self.border_presets:
            self.selected_preset.set(list(self.border_presets.keys())[0])
        if self.border_textures:
            self.selected_style.set(list(self.border_textures.keys())[0])

    def toggle_tracing(self):
        """Starts or stops the interactive border tracing mode."""
        self.is_tracing = not self.is_tracing

        if self.is_tracing:
            self.traced_points = []
            if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
            self.trace_button.config(text="Cancel Tracing", bg="#ef4444")
            self.finish_button.config(state='normal')
            self.canvas.config(cursor="crosshair")
            messagebox.showinfo("Tracing Started", "Click on the canvas to place points for your border path. Right-click to remove the last point. Press 'Finish & Save' when done.")
        else: # Tracing was cancelled
            self.canvas.unbind("<B1-Motion>") # Unbind the drag event
            self.trace_button.config(text="Start Tracing", bg="#d97706")
            self.finish_button.config(state='disabled')
            self.canvas.config(cursor="")
            if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
            self.traced_points = []

        # Ensure magic wand is off
        if self.is_magic_wand_active:
            self.toggle_magic_wand()

        # Ensure magic trace is off
        if self.is_magic_trace_active:
            self.toggle_magic_trace()

    def finish_tracing(self):
        """Finalizes the tracing and saves the new preset."""
        if not self.traced_points or len(self.traced_points) < 2:
            messagebox.showwarning("Trace Incomplete", "You must place at least two points to create a border.")
            return

        preset_name = simpledialog.askstring("Save Preset", "Enter a name for your new border preset:")
        if not preset_name:
            return # User cancelled

        # Create the new preset definition
        new_preset = {
            "shape_type": "multi_span_path",
            "segments": [
                {"type": "path", "path_coords": self.traced_points}
            ]
        }
        self.border_presets[preset_name] = new_preset

        # Update the preset dropdown menu in the UI
        self.app.ui_manager._populate_border_tab(self.app.ui_manager.border_tab) # Use the direct reference
        self.selected_preset.set(preset_name)
        
        print(f"New border preset '{preset_name}' saved with {len(self.traced_points)} points.")
        self.toggle_tracing() # Reset the tracing state

    def toggle_magic_trace(self):
        """Toggles the 'magic trace' (lasso) mode."""
        self.is_magic_trace_active = not getattr(self, 'is_magic_trace_active', False)

        if self.is_magic_trace_active:
            if self.is_tracing: self.toggle_tracing()
            if self.is_magic_wand_active: self.toggle_magic_wand()

            self.magic_trace_button.config(text="Magic Trace (Active)", bg="#14b8a6", relief='sunken')
            self.canvas.config(cursor="crosshair")
            messagebox.showinfo("Magic Trace Active", "Click and drag to draw a loose selection around the shape you want to create a border for. The tool will automatically snap to the detected outline.")
            # --- DEFINITIVE FIX: Take exclusive control of mouse events ---
            self.canvas.unbind("<B1-Motion>") # Unbind the generic drag handler
            self.canvas.bind("<ButtonPress-1>", self._start_magic_trace)
            self.canvas.bind("<B1-Motion>", self._draw_magic_trace)
            self.canvas.bind("<ButtonRelease-1>", self._finish_magic_trace)
        else:
            self.magic_trace_button.config(text="Magic Trace", bg="#0d9488", relief='flat')
            self.canvas.config(cursor="")
            # --- DEFINITIVE FIX: Restore default event handlers ---
            self.canvas.unbind("<ButtonPress-1>")
            self.canvas.unbind("<B1-Motion>")
            self.canvas.unbind("<ButtonRelease-1>")
            if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
            self.traced_points = []
            self.app.bind_generic_drag_handler() # Re-bind the app's default drag logic

    def _start_magic_trace(self, event):
        """Starts drawing the magic trace lasso."""
        self.traced_points = []
        if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
        self.add_drag_trace_point(event)

    def _draw_magic_trace(self, event):
        """Adds points to the lasso path while dragging."""
        self.add_drag_trace_point(event)

    def _finish_magic_trace(self, event):
        """
        On mouse release, finds the underlying component, detects contours,
        and snaps the user's path to the best-fit contour.
        """
        if not self.traced_points: return
        
        if not cv2 or not np:
            messagebox.showerror("Dependency Missing", "Magic Trace requires OpenCV and NumPy. Please install them via: pip install opencv-python numpy")
            return

        # Find the component under the drawn path
        bounds = self.canvas.bbox(self.trace_preview_id)
        if not bounds: return
        
        overlapping_ids = self.canvas.find_overlapping(*bounds)
        target_comp = None
        for item_id in reversed(overlapping_ids):
            tags = self.canvas.gettags(item_id)
            if tags and tags[0] in self.app.components:
                comp = self.app.components[tags[0]]
                if comp.pil_image and not comp.is_dock_asset and not tags[0].startswith("preset_border_"):
                    target_comp = comp
                    break

        if not target_comp:
            messagebox.showwarning("No Target Found", "Magic Trace could not find an image component within your selection.")
            if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
            self.traced_points = []
            return

        all_contours = self._find_all_contours(target_comp.pil_image)
        if not all_contours:
            messagebox.showwarning("No Contours Found", "Could not find any distinct shapes in the target image's alpha channel.")
            if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
            self.traced_points = []
            return

        # Find the best contour that intersects with the user's drawn path
        user_path_poly = np.array(self.traced_points, dtype=np.int32)
        best_contour = None
        max_intersection = 0

        for contour in all_contours:
            # Check for intersection. A simple bounding box check is efficient.
            contour_poly = np.array(contour, dtype=np.int32)
            if cv2.intersectConvexConvex(user_path_poly, contour_poly)[0] > 0:
                 # For simplicity, we'll just take the first intersecting contour.
                 # A more advanced implementation could find the one with the largest intersection area.
                 best_contour = contour
                 break

        if best_contour is None:
            # If no intersection, find the contour closest to the center of the user's drawing
            user_cx = np.mean(user_path_poly[:, 0])
            user_cy = np.mean(user_path_poly[:, 1])
            min_dist = float('inf')
            for contour in all_contours:
                M = cv2.moments(np.array(contour))
                if M["m00"] == 0: continue
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                dist = np.sqrt((cx - user_cx)**2 + (cy - user_cy)**2)
                if dist < min_dist:
                    min_dist = dist
                    best_contour = contour

        # Convert the chosen local contour points to absolute world coordinates
        self.traced_points = [(target_comp.world_x1 + x, target_comp.world_y1 + y) for x, y in best_contour]
        self._update_trace_preview() # Update preview to show the snapped path
        
        # Now that the path is refined, the user can click "Finish & Save"
        self.finish_button.config(state='normal')
        self.toggle_magic_trace() # Exit the mode

    def add_trace_point(self, event):
        """Adds a point to the current trace path."""
        if not self.is_tracing: return
        
        # --- NEW: Logic for freehand drag-tracing ---
        # On the initial click, clear previous points and bind the drag event.
        self.traced_points = []
        if self.trace_preview_id: self.canvas.delete(self.trace_preview_id)
        
        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)
        self.last_trace_point = (world_x, world_y)
        self.traced_points.append((int(world_x), int(world_y)))
        
        # Bind the motion event to a new handler for continuous drawing
        self.canvas.bind("<B1-Motion>", self.add_drag_trace_point)

    def add_drag_trace_point(self, event):
        """Continuously adds points to the path while dragging."""
        if not (self.is_tracing or getattr(self, 'is_magic_trace_active', False)) or not self.last_trace_point: return
        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)
        
        # Only add a new point if the cursor has moved a minimum distance to avoid overly dense paths
        if abs(world_x - self.last_trace_point[0]) > 2 or abs(world_y - self.last_trace_point[1]) > 2:
            self.traced_points.append((int(world_x), int(world_y)))
            self.last_trace_point = (world_x, world_y)
            self._update_trace_preview()

    def remove_last_trace_point(self, event):
        """Removes the last added point from the trace."""
        if self.is_tracing and self.traced_points:
            self.traced_points.pop()
            self._update_trace_preview()

    def toggle_magic_wand(self):
        """Toggles the 'magic wand' edge detection mode."""
        self.is_magic_wand_active = not self.is_magic_wand_active

        if self.is_magic_wand_active:
            # Deactivate manual tracing if it's on
            if self.is_tracing:
                self.toggle_tracing()

            # Deactivate magic trace if it's on
            if getattr(self, 'is_magic_trace_active', False):
                self.toggle_magic_trace()

            self.magic_wand_button.config(text="Magic Wand (Active)", bg="#a78bfa", relief='sunken')
            self.canvas.config(cursor="spraycan")
            messagebox.showinfo("Magic Wand Active", "Click on a tile with an image to automatically trace its outline.")
        else:
            self.magic_wand_button.config(text="Magic Wand", bg="#8b5cf6", relief='flat')
            self.canvas.config(cursor="")

    def run_magic_wand(self, event):
        """Finds the component under the click and runs the contour detection."""
        if not self.is_magic_wand_active: return

        # --- DEFINITIVE FIX: Find the correct component, ignoring temporary layers ---
        # Find all items under the cursor, then iterate to find the first valid component.
        item_ids = self.canvas.find_overlapping(event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        comp_tag = None
        for item_id in reversed(item_ids): # Search from top to bottom
            tags = self.canvas.gettags(item_id)
            if tags and tags[0] in self.app.components:
                # Ignore temporary or non-image components
                if not tags[0].startswith(("paint_layer", "border_preview", "selection_highlight", "clone_", "border_")):
                    comp_tag = tags[0]
                    break # Found the first valid component

        comp = self.app.components.get(comp_tag)

        if not comp or not comp.pil_image:
            messagebox.showwarning("Invalid Target", "Magic Wand requires a tile with an image loaded.")
            return

        try:
            contour = self._find_contour(comp.pil_image)
            if not contour:
                messagebox.showwarning("No Contour Found", "Could not find a distinct shape in the image's alpha channel.")
                return

            # Convert local contour points to world coordinates
            world_contour = [(comp.world_x1 + x, comp.world_y1 + y) for x, y in contour]

            preset_name = simpledialog.askstring("Save Preset", "Enter a name for your new magic-traced preset:")
            if not preset_name: return

            new_preset = {
                "shape_type": "multi_span_path",
                "segments": [{"type": "path", "path_coords": world_contour}]
            }
            self.border_presets[preset_name] = new_preset

            self.app.ui_manager._populate_border_tab(self.app.ui_manager.border_tab)
            self.selected_preset.set(preset_name)
            self.show_preset_preview() # Show the new border immediately
            print(f"New magic preset '{preset_name}' saved with {len(world_contour)} points.")

        except Exception as e:
            messagebox.showerror("Magic Wand Error", f"An error occurred during contour detection: {e}")
        finally:
            # Deactivate the tool after use
            self.toggle_magic_wand()

    def _find_all_contours(self, image):
        """Finds all external contours in an image's alpha channel."""
        try:
            import numpy as np
        except ImportError:
            messagebox.showerror("Dependency Missing", "This feature requires OpenCV and NumPy.\nPlease install them via: pip install opencv-python numpy")
            return []

        if 'A' not in image.getbands():
            return []

        alpha = image.getchannel('A')
        alpha_np = np.array(alpha)

        # Find all external contours
        contours, _ = cv2.findContours(alpha_np, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return []

        # Convert contours to the expected format (list of lists of tuples)
        all_points = []
        for contour in contours:
            points = contour.reshape(-1, 2)
            all_points.append([tuple(point) for point in points])
        return all_points

    def _find_contour(self, image):
        """
        Finds the contour of the first non-transparent shape in an image.
        Returns a list of (x, y) points.
        """
        try:
            # Use the alpha channel as the basis for contour detection
            if 'A' not in image.getbands():
                return None # No alpha channel to trace

            alpha = image.getchannel('A')
            # Convert to numpy array for OpenCV
            alpha_np = np.array(alpha)

            # Find contours
            # RETR_EXTERNAL finds only the outermost contours.
            # CHAIN_APPROX_SIMPLE compresses horizontal, vertical, and diagonal segments, leaving only their end points.
            contours, _ = cv2.findContours(alpha_np, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return None

            # We are interested in the largest contour
            largest_contour = max(contours, key=cv2.contourArea)

            # The contour is a numpy array of shape (N, 1, 2). We need to reshape it to (N, 2).
            points = largest_contour.reshape(-1, 2)

            # Convert numpy points to a list of python tuples
            return [tuple(point) for point in points]
        finally:
            pass

    def _load_border_textures(self):
        """Loads default border textures into memory from the images directory."""
        # In a real app, this could scan a specific 'border_textures' folder.
        # For now, we'll explicitly load a known texture.
        try:
            brick_path = os.path.join(self.app.image_base_dir, "brick.png")
            if os.path.exists(brick_path):
                self.border_textures["Brick"] = Image.open(brick_path).convert("RGBA")
                print("Loaded 'Brick' border texture.")
            # Add more textures here, e.g., "stone.png"
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

    def _update_trace_preview(self):
        """Draws a line connecting the currently traced points."""
        if self.trace_preview_id:
            self.canvas.delete(self.trace_preview_id)

        if len(self.traced_points) >= 2:
            screen_points = [self.app.camera.world_to_screen(x, y) for x, y in self.traced_points]
            self.trace_preview_id = self.canvas.create_line(
                screen_points, fill="cyan", width=2, tags="trace_preview"
            )

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
        if shape_form == "path" and path_data:
            # The path_data is in world coordinates. We need to make it relative to the render box.
            min_x = min(p[0] for p in path_data)
            min_y = min(p[1] for p in path_data)
            relative_path = [(p[0] - min_x, p[1] - min_y) for p in path_data]
            
            # Draw the path as a series of lines with the specified thickness
            draw.line(relative_path, fill=255, width=thickness, joint="curve")

        # --- NEW: Adjust mask based on growth direction ---
        elif growth_direction == 'in':
            if shape_form == "circle":
                draw.ellipse([0, 0, logical_w, logical_h], fill=255)
                if logical_w > thickness * 2 and logical_h > thickness * 2:
                    draw.ellipse([thickness, thickness, logical_w - thickness, logical_h - thickness], fill=0)
            elif shape_form == "rect":
                draw.rectangle([0, 0, logical_w, logical_h], fill=255)
                if logical_w > thickness * 2 and logical_h > thickness * 2:
                    draw.rectangle([thickness, thickness, logical_w - thickness, logical_h - thickness], fill=0)
            # Path with 'in' growth is complex and not fully supported in this simplified render.
            # The line drawing above serves as the primary shape.

        else: # 'out'
            if shape_form == "circle":
                draw.ellipse([0, 0, render_w, render_h], fill=255)
                if render_w > thickness * 2 and render_h > thickness * 2:
                    # The inner cutout is inset by the thickness.
                    draw.ellipse([thickness, thickness, render_w - thickness, render_h - thickness], fill=0)
            else: # Default to rectangle
                # Only draw the rectangle if it's not a path, to avoid overwriting the path mask
                if shape_form != "path":
                    draw.rectangle([0, 0, render_w, render_h], fill=255)
                    if render_w > thickness * 2 and render_h > thickness * 2:
                        draw.rectangle([thickness, thickness, render_w - thickness, render_h - thickness], fill=0)
                        
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