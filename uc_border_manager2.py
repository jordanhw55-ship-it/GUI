import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import math
import time

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[WARNING] NumPy not found. Smart Border tool performance will be significantly degraded.")


# ----------------------------------------------------------------------
# 1. DRAGGABLE COMPONENT (Dependency)
# ----------------------------------------------------------------------
class DraggableComponent:
    """A simplified placeholder for a component drawn on the canvas."""
    def __init__(self, app, tag, x1, y1, x2, y2, color, comp_type):
        self.app = app
        self.tag = tag
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.color = color
        self.comp_type = comp_type
        self.is_draggable = True
        self.image = None
        self.image_id = None

    def set_image(self, pil_image):
        self.image = ImageTk.PhotoImage(pil_image)
        # Note: This requires the canvas to use the PhotoImage object.
        # In this simplified demo, we won't draw it, but the structure is here.


# ----------------------------------------------------------------------
# 2. BORDER MANAGER (Dependency)
# ----------------------------------------------------------------------
class BorderManager:
    """A simplified placeholder for the main Border Manager."""
    def __init__(self, app):
        self.app = app
        self.next_border_id = 1
        self.border_thickness = tk.IntVar(value=5)

    def _render_border_image(self, size, logical_size, shape_form, path_data, is_segmented, relative_to):
        """Stub function to create a simple PIL Image placeholder."""
        w, h = size
        img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # Draw a simple red line/shape to represent the border
        if path_data and path_data[0]:
            # Convert world coords (path_data) to image coords (relative to 'relative_to')
            comp_x, comp_y = relative_to
            
            # Since path_data is a list of segments, draw each one
            for segment in path_data:
                # Flatten the segment coordinates for ImageDraw.Draw.line()
                coords = []
                for x, y in segment:
                    # Translate world coordinates to image coordinates
                    coords.append(x - comp_x)
                    coords.append(y - comp_y)

                # Draw the path (segment by segment)
                if len(coords) >= 4:
                    draw.line(coords, fill="red", width=self.border_thickness.get() * 2, joint="curve")

        # Return the PIL Image
        return img


# ----------------------------------------------------------------------
# 3. SMART BORDER MANAGER (Core Logic)
# ----------------------------------------------------------------------
class SmartBorderManager:
    """Manages the interactive 'Smart Border' tool."""
    def __init__(self, app, border_manager):
        self.app = app
        self.canvas = app.canvas
        self.border_manager = border_manager
        self.on_mouse_down_binding_id = None
        self.on_mouse_move_binding_id = None
        self.on_mouse_up_binding_id = None

        self.is_drawing = False
        self.is_erasing_points = tk.BooleanVar(value=False)
        self.raw_border_points = set()
        self.brush_cursor_oval_id = None

        self.is_selecting_preview_area = False
        self.preview_selection_rect_id = None
        self.preview_selection_start_x = 0
        self.preview_selection_start_y = 0
        self.preview_area_world_coords = None
        self.highlight_oval_ids = []
        self.last_drawn_x = -1
        self.last_drawn_y = -1
        
        # Debounce/redraw variables
        self.after_id = None 
        self.redraw_scheduled = False

        # Settings
        self.smart_brush_radius = tk.IntVar(value=15)
        self.smart_min_segment_length = tk.IntVar(value=20)
        self.smart_max_gap = tk.IntVar(value=50)


    def _canvas_to_world(self, x, y):
        """Converts canvas coordinates to world (document) coordinates."""
        # Uses simplified app properties for this demo
        zoom = self.app.zoom if self.app.zoom != 0 else 1.0
        viewport_x = self.app.viewport_x
        viewport_y = self.app.viewport_y
            
        x_world = x / zoom + viewport_x
        y_world = y / zoom + viewport_y
        return int(x_world), int(y_world)

    def _world_to_canvas(self, x, y):
        """Converts world coordinates to canvas coordinates."""
        zoom = self.app.zoom if self.app.zoom != 0 else 1.0
        viewport_x = self.app.viewport_x
        viewport_y = self.app.viewport_y
        
        x_canvas = (x - viewport_x) * zoom
        y_canvas = (y - viewport_y) * zoom
        return int(x_canvas), int(y_canvas)

    def enable_smart_border_tool(self):
        """Sets up bindings for the smart border drawing."""
        self.on_mouse_down_binding_id = self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.on_mouse_move_binding_id = self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.on_mouse_up_binding_id = self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Motion>", self._update_brush_cursor_only) # For cursor preview when not drawing
        self.canvas.focus_set()

    def disable_smart_border_tool(self):
        """Clears bindings and remaining UI elements."""
        self.canvas.unbind("<Button-1>", self.on_mouse_down_binding_id)
        self.canvas.unbind("<B1-Motion>", self.on_mouse_move_binding_id)
        self.canvas.unbind("<ButtonRelease-1>", self.on_mouse_up_binding_id)
        self.canvas.unbind("<Motion>")
        self.canvas.delete(self.brush_cursor_oval_id)
        self._redraw_highlight_ovals(clear_only=True)
        self._clear_all_points()
        
    def _update_brush_cursor_only(self, event):
        """Updates the cursor position when not drawing."""
        if not self.brush_cursor_oval_id:
             r = self.smart_brush_radius.get()
             radius_on_canvas = r * self.app.zoom
             # Create the brush cursor
             self.brush_cursor_oval_id = self.canvas.create_oval(
                 0, 0, radius_on_canvas * 2, radius_on_canvas * 2, 
                 outline="#FF0000", tags=("brush_cursor",), dash=(5, 5), width=2
             )
        
        r = self.smart_brush_radius.get()
        radius_on_canvas = r * self.app.zoom
        x1, y1 = event.x - radius_on_canvas, event.y - radius_on_canvas
        x2, y2 = event.x + radius_on_canvas, event.y + radius_on_canvas
        self.canvas.coords(self.brush_cursor_oval_id, x1, y1, x2, y2)
        self.canvas.tag_raise(self.brush_cursor_oval_id)

    def _on_mouse_down(self, event):
        """Starts the drawing process."""
        self.is_drawing = True
        # Reset last drawn point when starting a new stroke
        x_world, y_world = self._canvas_to_world(event.x, event.y)
        self.last_drawn_x, self.last_drawn_y = x_world, y_world
        
        # If erasing mode is active, prevent drawing
        if self.is_erasing_points.get():
            self.is_drawing = False


    def _on_mouse_move(self, event):
        x_world, y_world = self._canvas_to_world(event.x, event.y)
        current_points_count = len(self.raw_border_points)

        # 1. Update brush cursor position (required for both drawing/erasing)
        if self.brush_cursor_oval_id:
            r = self.smart_brush_radius.get()
            radius_on_canvas = r * self.app.zoom
            x1, y1 = event.x - radius_on_canvas, event.y - radius_on_canvas
            x2, y2 = event.x + radius_on_canvas, event.y + radius_on_canvas
            self.canvas.coords(self.brush_cursor_oval_id, x1, y1, x2, y2)

        # 2. Handle Drawing or Erasing
        if self.is_erasing_points.get():
            # --- Erasing Logic ---
            r = self.smart_brush_radius.get()
            r_sq = r * r
            points_to_remove = set()
            
            # Iterate over a copy to allow modification of the original set
            for x, y in list(self.raw_border_points): 
                # Check distance in world coordinates
                dist_sq = (x - x_world)**2 + (y - y_world)**2
                if dist_sq < r_sq:
                    points_to_remove.add((x, y))

            if points_to_remove:
                self.raw_border_points -= points_to_remove
                new_points_count = len(self.raw_border_points)
                
                # DEBUG PRINT: Check when points are removed
                print(f"[DEBUG] Erased {len(points_to_remove)} points. Old Count: {current_points_count}, New Count: {new_points_count}")
                
                # Schedule a redraw of the highlight ovals
                self._schedule_highlight_redraw()
            
        elif self.is_drawing:
            # --- Drawing Logic ---
            # Use a small distance check (e.g., 2 pixels) in world coordinates 
            # to prevent adding points too close to the last one.
            if self.last_drawn_x == -1 or \
               (abs(x_world - self.last_drawn_x) >= 2 or abs(y_world - self.last_drawn_y) >= 2):
                
                if (x_world, y_world) not in self.raw_border_points:
                    self.raw_border_points.add((x_world, y_world))
                    self.last_drawn_x, self.last_drawn_y = x_world, y_world
                    
                    new_points_count = len(self.raw_border_points)
                    # DEBUG PRINT: Check when points are added
                    print(f"[DEBUG] Added 1 point. Total Count: {new_points_count}")
                    
                    # Schedule a redraw of the highlight ovals
                    self._schedule_highlight_redraw()
                else:
                    self.last_drawn_x, self.last_drawn_y = x_world, y_world # Update last_drawn even if not added
        
        # 3. Handle Preview Area Selection (stub)
        if self.is_selecting_preview_area:
            # Add logic for drawing the preview selection rectangle here
            pass

    def _on_mouse_up(self, event):
        """Ends the drawing process."""
        self.is_drawing = False
        self.last_drawn_x = -1 # Reset draw tracking
        self.last_drawn_y = -1

    def _schedule_highlight_redraw(self, delay=50):
        """A simple debounce mechanism to avoid redrawing highlights on every mouse move."""
        if self.after_id:
            self.app.master.after_cancel(self.after_id)
        # Use app.master.after to schedule the redraw on the main thread
        self.after_id = self.app.master.after(delay, self._redraw_highlight_ovals)

    def _redraw_highlight_ovals(self, clear_only=False):
        """Clears and redraws the small highlight ovals for the points."""
        if self.after_id:
            self.app.master.after_cancel(self.after_id)
            self.after_id = None 

        # 1. Clear existing highlights
        for oval_id in self.highlight_oval_ids:
            self.canvas.delete(oval_id)
        self.highlight_oval_ids = []
        
        if clear_only:
            return

        # 2. Draw new highlights if points exist
        if self.raw_border_points:
            # Only draw a subset of points for performance reasons
            points_list = list(self.raw_border_points)
            
            # Draw every Nth point to keep the UI responsive for large borders
            sample_rate = max(1, len(points_list) // 500) 
            
            for i, (x_world, y_world) in enumerate(points_list):
                if i % sample_rate != 0:
                    continue
                
                x_canvas, y_canvas = self._world_to_canvas(x_world, y_world)
                # Small circle size on canvas
                r = 3 
                oval_id = self.canvas.create_oval(
                    x_canvas - r, y_canvas - r, 
                    x_canvas + r, y_canvas + r, 
                    fill="yellow", outline="black", tags=("border_highlight",)
                )
                self.highlight_oval_ids.append(oval_id)
            
            self.canvas.tag_raise("brush_cursor") # Keep cursor on top
            
    def _clear_all_points(self):
        """Clears the points set and updates the UI."""
        self.raw_border_points.clear()
        self.canvas.delete(self.brush_cursor_oval_id)
        self.brush_cursor_oval_id = None
        self._redraw_highlight_ovals(clear_only=True)
        print("[DEBUG] All border points cleared.")

    def _create_smart_border(self):
        """Placeholder for the border creation logic."""
        if not self.raw_border_points:
            messagebox.showinfo("Smart Border", "No points drawn to create a border.")
            return

        print(f"[DEBUG] Attempting to create border from {len(self.raw_border_points)} points.")

        # --- Simplified Segmentation/Pathfinding (NN approach) ---
        remaining_points = list(self.raw_border_points)
        point_segments = []
        
        # Determine bounding box for rendering
        min_x = min(p[0] for p in remaining_points)
        max_x = max(p[0] for p in remaining_points)
        min_y = min(p[1] for p in remaining_points)
        max_y = max(p[1] for p in remaining_points)

        logical_w = max_x - min_x
        logical_h = max_y - min_y
        
        # Simple nearest-neighbor segmentation to turn the set of points into a path
        while remaining_points:
            current_segment = [remaining_points.pop(0)]
            
            # Simple nearest neighbor search (very inefficient, but serves as a stub)
            for _ in range(500): # Limit segment length for safety
                last_point = current_segment[-1]
                min_dist_sq = float('inf')
                nearest_neighbor = None
                
                # Search up to max_gap radius
                search_radius_sq = self.smart_max_gap.get() ** 2 
                
                # Find the closest point in the remaining set
                for p in remaining_points:
                    dist_sq = (p[0] - last_point[0])**2 + (p[1] - last_point[1])**2
                    if dist_sq < min_dist_sq and dist_sq <= search_radius_sq:
                        min_dist_sq = dist_sq
                        nearest_neighbor = p
                
                if nearest_neighbor:
                    current_segment.append(nearest_neighbor)
                    remaining_points.remove(nearest_neighbor)
                else:
                    break
            point_segments.append(current_segment)
        
        if not point_segments or not logical_w or not logical_h:
            messagebox.showerror("Error", "Could not create border from points (invalid size or segmentation failed).")
            self._clear_all_points()
            return
            
        # --- Rendering Setup ---
        thickness = self.border_manager.border_thickness.get()
        render_w, render_h = logical_w + thickness * 2, logical_h + thickness * 2
        comp_x, comp_y = min_x - thickness, min_y - thickness
            
        border_image = self.border_manager._render_border_image(
            (render_w, render_h), (logical_w, logical_h), 
            shape_form="path", 
            path_data=point_segments, 
            is_segmented=True, 
            relative_to=(comp_x, comp_y)
        )
        if not border_image: return

        # --- Component Creation ---
        border_tag = f"smart_border_{self.border_manager.next_border_id}"
        self.border_manager.next_border_id += 1
        border_comp = DraggableComponent(self.app, border_tag, comp_x, comp_y, comp_x + render_w, comp_y + render_h, "blue", "BORDER")
        border_comp.is_draggable = True
        border_comp.set_image(border_image)

        self.app.components[border_tag] = border_comp
        self.app._bind_component_events(border_tag)
        # In a real app, you would draw the component here.
        
        messagebox.showinfo("Success", f"Created border with {len(self.raw_border_points)} points in {len(point_segments)} segments.")
        self._clear_all_points() # Clean up after creation
        # self.app._save_undo_state({'type': 'add', 'tag': border_tag}) # Stub

# ----------------------------------------------------------------------
# 4. MAIN APPLICATION (The Host)
# ----------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Border Tool Demo")
        self.geometry("800x600")

        # Simplified attributes needed by SmartBorderManager
        self.zoom = 1.0
        self.viewport_x = 0
        self.viewport_y = 0
        self.components = {} # Stores DraggableComponent instances
        
        self.border_manager = BorderManager(self)
        self.smart_border_manager = SmartBorderManager(self, self.border_manager)

        self.setup_ui()
        
    def setup_ui(self):
        # Main Canvas Area
        self.canvas = tk.Canvas(self, bg="#f0f0f0", bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=5)
        
        # Control Panel
        control_frame = tk.Frame(self, width=200, bg="#e0e0e0")
        control_frame.pack(fill=tk.Y, side=tk.RIGHT, padx=5, pady=5)
        
        tk.Label(control_frame, text="Smart Border Controls", font=("Arial", 12, "bold"), bg="#e0e0e0").pack(pady=10)

        # Draw/Erase Toggle
        erase_check = tk.Checkbutton(control_frame, 
                                     text="Erase Mode (Hold CTRL to temporarily toggle)", 
                                     variable=self.smart_border_manager.is_erasing_points,
                                     bg="#e0e0e0")
        erase_check.pack(pady=5, padx=10, anchor='w')

        # Brush Radius Slider (Placeholder)
        tk.Label(control_frame, text="Brush Radius (World Pixels):", bg="#e0e0e0").pack(pady=(10, 0))
        tk.Scale(control_frame, 
                 from_=5, to_=50, 
                 variable=self.smart_border_manager.smart_brush_radius, 
                 orient=tk.HORIZONTAL, bg="#e0e0e0").pack(padx=10)
        
        # Border thickness (for rendering)
        tk.Label(control_frame, text="Border Thickness (for Commit):", bg="#e0e0e0").pack(pady=(10, 0))
        tk.Scale(control_frame, 
                 from_=1, to_=10, 
                 variable=self.border_manager.border_thickness, 
                 orient=tk.HORIZONTAL, bg="#e0e0e0").pack(padx=10)

        # Action Buttons
        tk.Button(control_frame, text="START Drawing", command=self._start_drawing).pack(pady=20, padx=10, fill='x')
        tk.Button(control_frame, text="COMMIT Border (Stub)", command=self.smart_border_manager._create_smart_border).pack(pady=5, padx=10, fill='x')
        tk.Button(control_frame, text="CLEAR Points", command=self.smart_border_manager._clear_all_points).pack(pady=5, padx=10, fill='x')
        tk.Button(control_frame, text="STOP Tool", command=self.smart_border_manager.disable_smart_border_tool).pack(pady=20, padx=10, fill='x')

        # Keyboard Bindings for Erase Toggle
        self.bind("<Control_L>", self._toggle_erase_on)
        self.bind("<KeyRelease-Control_L>", self._toggle_erase_off)
        
        # Initial tool state
        self.smart_border_manager.enable_smart_border_tool()

    def _start_drawing(self):
        self.smart_border_manager.enable_smart_border_tool()
        
    def _toggle_erase_on(self, event):
        self.smart_border_manager.is_erasing_points.set(True)
        print("[INFO] Erase Mode ON (via CTRL)")

    def _toggle_erase_off(self, event):
        self.smart_border_manager.is_erasing_points.set(False)
        print("[INFO] Erase Mode OFF (via CTRL)")

    # Stub methods
    def _save_undo_state(self, action):
        pass
        
    def _bind_component_events(self, tag):
        pass

    def run(self):
        self.mainloop()

if __name__ == "__main__":
    app = App()
    app.run()