import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import math

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[WARNING] NumPy not found. Smart Border tool performance will be significantly degraded.")

from uc_component import DraggableComponent
# Assuming the rest of your imports and class definition are present

class SmartBorderManager:
    """Manages the interactive 'Smart Border' tool."""
    def __init__(self, app, border_manager):
        self.app = app
        self.canvas = app.canvas
        self.border_manager = border_manager
        self.on_mouse_down_binding_id = None

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
        self.redraw_scheduled = False
        self.after_id = None # To store the ID returned by app.master.after
        self.smart_brush_radius = tk.IntVar(value=15)
        self.smart_min_segment_length = tk.IntVar(value=20)
        self.smart_max_gap = tk.IntVar(value=50)


    def _canvas_to_world(self, x, y):
        # Placeholder for conversion function, adjust based on your app's actual viewport/zoom logic
        if not hasattr(self.app, 'zoom') or self.app.zoom == 0:
            zoom = 1.0
        else:
            zoom = self.app.zoom
            
        if not hasattr(self.app, 'viewport_x'):
             viewport_x = 0
        else:
            viewport_x = self.app.viewport_x
            
        if not hasattr(self.app, 'viewport_y'):
            viewport_y = 0
        else:
            viewport_y = self.app.viewport_y
            
        x_world = x / zoom + viewport_x
        y_world = y / zoom + viewport_y
        return int(x_world), int(y_world)

    def _on_mouse_move(self, event):
        x_world, y_world = self._canvas_to_world(event.x, event.y)
        current_points_count = len(self.raw_border_points)

        # 1. Update brush cursor position
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
            
            # Use a list for iteration and modification
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
                
                # Check if the point already exists (set handles this automatically, but for clarity)
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
        
        # 3. Handle Preview Area Selection
        if self.is_selecting_preview_area:
            # ... (Your existing preview selection logic here, if any)
            pass

    # The rest of your SmartBorderManager class methods here...
    
    def _schedule_highlight_redraw(self, delay=50):
        # A simple debounce mechanism to avoid redrawing highlights on every mouse move
        if self.after_id:
            self.app.master.after_cancel(self.after_id)
        self.after_id = self.app.master.after(delay, self._redraw_highlight_ovals)

    def _redraw_highlight_ovals(self):
        # Clear the old after_id
        self.after_id = None 
        # ... (Your existing logic to clear self.highlight_oval_ids and redraw them)
        # This function should loop through self.raw_border_points and draw a small oval for each.
        
        # For testing, you can comment out the actual drawing logic and just use the prints.
        pass 
        
    def _clear_all_points(self):
        # This function should be called when a border is created or canceled.
        self.raw_border_points.clear()
        self.canvas.delete(self.brush_cursor_oval_id)
        self.brush_cursor_oval_id = None
        self._redraw_highlight_ovals()
        print("[DEBUG] All border points cleared.")
        
    def _on_mouse_up(self, event):
        self.is_drawing = False
        # Optional: Run a cleanup/optimization here if you suspect large point sets are causing issues
        # e.g., self.cleanup_points_on_commit() 
        
# Assuming other methods like _create_smart_border, cleanup_points_on_commit, etc., are present and unchanged.