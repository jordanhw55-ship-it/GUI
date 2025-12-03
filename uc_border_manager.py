import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import numpy as np
import os

from uc_component import DraggableComponent

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.is_tracing = False
        self.trace_points = []
        self.temp_trace_line_id = None
        self.next_border_id = 0

        # --- UI-related state variables ---
        self.border_style = tk.StringVar(value="Solid")
        self.border_color = tk.StringVar(value="#ff0000")
        self.border_thickness = tk.IntVar(value=10)
        self.glow_enabled = tk.BooleanVar(value=False)
        self.glow_color = tk.StringVar(value="#ffff00")
        self.glow_size = tk.IntVar(value=10)

        # Pre-load some asset textures (in a real app, this might be dynamic)
        self.border_textures = {}
        self._load_default_textures()

    def _load_default_textures(self):
        """Loads default border textures into memory."""
        try:
            brick_path = self.app.image_base_dir + "/brick.png"
            if os.path.exists(brick_path):
                self.border_textures["Brick"] = Image.open(brick_path).convert("RGBA")
                print("Loaded 'Brick' border texture.")
        except Exception as e:
            print(f"Could not load default brick texture: {e}")

    def toggle_trace_mode(self):
        """Starts or stops the border tracing mode."""
        self.is_tracing = not self.is_tracing
        if self.is_tracing:
            self.app.ui_manager.trace_border_btn.config(text="Cancel Tracing", relief='sunken')
            self.canvas.config(cursor="crosshair")
            # Temporarily unbind component dragging to prioritize tracing
            self.canvas.tag_unbind("draggable", '<Button-1>')
            self.canvas.tag_unbind("draggable", '<B1-Motion>')
            self.canvas.tag_unbind("draggable", '<ButtonRelease-1>')
            # Bind tracing events
            self.canvas.bind('<Button-1>', self._on_trace_press)
            self.canvas.bind('<B1-Motion>', self._on_trace_drag)
            self.canvas.bind('<ButtonRelease-1>', self._on_trace_release)
        else:
            self.app.ui_manager.trace_border_btn.config(text="Trace New Border", relief='flat')
            self.canvas.config(cursor="")
            # Re-bind component dragging
            for comp in self.app.components.values():
                if not comp.is_dock_asset:
                    self.app._bind_component_events(comp.tag)
            # Unbind tracing events
            self.canvas.unbind('<Button-1>')
            self.canvas.unbind('<B1-Motion>')
            self.canvas.unbind('<ButtonRelease-1>')
            if self.temp_trace_line_id:
                self.canvas.delete(self.temp_trace_line_id)
                self.temp_trace_line_id = None

    def _on_trace_press(self, event):
        """Starts a new trace path."""
        self.trace_points = [(event.x, event.y)]
        if self.temp_trace_line_id:
            self.canvas.delete(self.temp_trace_line_id)
        self.temp_trace_line_id = self.canvas.create_line(self.trace_points * 2, fill="yellow", width=2, dash=(4, 4))

    def _on_trace_drag(self, event):
        """Adds a point to the trace path and updates the temporary line."""
        self.trace_points.append((event.x, event.y))
        self.canvas.coords(self.temp_trace_line_id, *sum(self.trace_points, ()))

    def _on_trace_release(self, event):
        """Finalizes the trace and creates the border."""
        if len(self.trace_points) < 2:
            self.toggle_trace_mode()
            return

        # Convert screen trace points to world coordinates
        world_trace_points = [self.app.camera.screen_to_world(p[0], p[1]) for p in self.trace_points]

        # 1. Find if the trace intersects with any component
        snapped_comp = self._find_intersecting_component(world_trace_points)

        if snapped_comp:
            # Use the component's bounding box
            x1, y1, x2, y2 = snapped_comp.world_x1, snapped_comp.world_y1, snapped_comp.world_x2, snapped_comp.world_y2
            polygon = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            print(f"Snapped border to component '{snapped_comp.tag}'.")
        else:
            # Use the freehand polygon (simplified)
            polygon = self._simplify_trace(world_trace_points)
            print("Creating freehand border.")

        # 2. Create the border component
        self._create_border_from_polygon(polygon)

        # 3. Exit trace mode
        self.toggle_trace_mode()

    def _find_intersecting_component(self, world_points):
        """Finds the first component that intersects with the traced path's bounding box."""
        if not world_points: return None
        min_x = min(p[0] for p in world_points)
        min_y = min(p[1] for p in world_points)
        max_x = max(p[0] for p in world_points)
        max_y = max(p[1] for p in world_points)

        for comp in self.app.components.values():
            if comp.is_dock_asset or comp.is_decal or not comp.pil_image:
                continue
            # Simple bounding box intersection test
            if not (max_x < comp.world_x1 or min_x > comp.world_x2 or max_y < comp.world_y1 or min_y > comp.world_y2):
                return comp
        return None

    def _simplify_trace(self, points, tolerance=2.0):
        """Simplifies a path using the Ramer-Douglas-Peucker algorithm."""
        if len(points) < 3:
            return points
        
        # For a simple closed shape, just use the bounding box of the trace
        min_x = min(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_x = max(p[0] for p in points)
        max_y = max(p[1] for p in points)
        return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]

    def _create_border_from_polygon(self, polygon):
        """Creates and draws a new border component based on a polygon."""
        if not polygon: return

        # Create a new component for the border itself
        border_tag = f"border_instance_{self.next_border_id}"
        self.next_border_id += 1

        # The border component's world coords are the bounding box of the polygon
        min_x = min(p[0] for p in polygon)
        min_y = min(p[1] for p in polygon)
        max_x = max(p[0] for p in polygon)
        max_y = max(p[1] for p in polygon)

        border_comp = DraggableComponent(self.app, border_tag, min_x, min_y, max_x, max_y, "blue", "BORDER")
        border_comp.is_draggable = False # Borders are not draggable by default

        # Generate the PIL image for the border
        border_image = self._render_border_image(polygon, (max_x - min_x, max_y - min_y))
        if not border_image: return

        border_comp.set_image(border_image)
        self.app.components[border_tag] = border_comp
        self.app.canvas.tag_lower(border_tag, "draggable") # Send behind other components
        self.app.redraw_all_zoomable()

    def _render_border_image(self, polygon, size):
        """Renders the selected border style onto a PIL image."""
        width, height = int(size[0]), int(size[1])
        if width <= 0 or height <= 0: return None

        style = self.border_style.get()
        final_image = Image.new("RGBA", (width, height), (0,0,0,0))
        
        # Normalize polygon to the image's local coordinates (0,0)
        min_x, min_y = min(p[0] for p in polygon), min(p[1] for p in polygon)
        local_polygon = [(p[0] - min_x, p[1] - min_y) for p in polygon]

        if style == "Solid" or style == "Dashed":
            draw = ImageDraw.Draw(final_image)
            # For now, we draw a rectangle for simplicity, even for freehand traces
            rect_bounds = [(0,0), (width-1, height-1)]
            outline_color = self.border_color.get()
            thickness = self.border_thickness.get()
            
            if style == "Solid":
                draw.rectangle(rect_bounds, outline=outline_color, width=thickness)
            # Dashed style can be added here if needed

        elif style == "Brick" and "Brick" in self.border_textures:
            texture = self.border_textures["Brick"]
            thickness = self.border_thickness.get() # Use the thickness value

            # 1. Create a mask for the border outline
            mask = Image.new("L", (width, height), 0) # 'L' mode for grayscale mask
            draw = ImageDraw.Draw(mask)
            # Draw a white rectangle outline on the black mask
            draw.rectangle([(0,0), (width-1, height-1)], fill=0, outline=255, width=thickness)

            # 2. Create a layer with the tiled texture
            tiled_texture_layer = Image.new("RGBA", (width, height))
            for y in range(0, height, texture.height):
                for x in range(0, width, texture.width):
                    tiled_texture_layer.paste(texture, (x, y))

            # 3. Composite the tiled texture onto the final image using the mask
            final_image.paste(tiled_texture_layer, (0, 0), mask)

        # Apply glow effect if enabled
        if self.glow_enabled.get():
            glow_layer = final_image.filter(ImageFilter.GaussianBlur(self.glow_size.get()))
            # To make the glow a specific color, we can create a colored version
            solid_color_glow = Image.new("RGBA", glow_layer.size, self.glow_color.get())
            alpha_mask = glow_layer.getchannel('A')
            solid_color_glow.putalpha(alpha_mask)
            final_image = Image.alpha_composite(solid_color_glow, final_image)

        return final_image

    def apply_asset_border_to_selection(self):
        """
        Applies the selected border from the dock to the selected tile on the canvas.
        This re-uses the decal/cloning mechanism.
        """
        pass

    def choose_border_color(self):
        color = colorchooser.askcolor(title="Choose Border Color", initialcolor=self.border_color.get())
        if color and color[1]: self.border_color.set(color[1])

    def choose_glow_color(self):
        color = colorchooser.askcolor(title="Choose Glow Color", initialcolor=self.glow_color.get())
        if color and color[1]: self.glow_color.set(color[1])