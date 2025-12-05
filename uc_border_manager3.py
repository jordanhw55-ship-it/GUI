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

        self.is_selecting_preview_area = False
        self.preview_selection_rect_id = None
        self.preview_selection_start_x = 0
        self.preview_selection_start_y = 0
        self.preview_area_world_coords = None
        self.highlight_oval_ids = []
        self.last_drawn_x = -1
        self.last_drawn_y = -1
        self.redraw_scheduled = False
        self.after_id = None # NEW: To store the ID returned by app.master.after

        self.smart_brush_radius = tk.IntVar(value=15)
        self.smart_diff_threshold = tk.IntVar(value=50)
        self.smart_draw_skip = tk.IntVar(value=5)
        self.active_detection_image = None
        self.active_detection_alpha_numpy = None # NEW: To store the NumPy array
        self.active_detection_component = None
        self.composite_x_offset = 0
        self.composite_y_offset = 0

        self.preview_scale_var = tk.DoubleVar(value=1.0)
        self.preview_cursor_circle_id = None

        self.preview_tk_image = None
        self.highlight_layer_image = None
        self.highlight_layer_tk = None
        self.highlight_layer_id = None
        self.highlight_color = (0, 255, 255, 255)
        
        self.cursor_image_size = 50 # Size for the dynamic brush layer
        self.cursor_pil_image = None
        self.cursor_tk_image = None
        self.cursor_canvas_id = None # NEW: Replaces brush_cursor_oval_id
        self.on_mouse_move_binding_id = None
        self.REDRAW_THROTTLE_MS = 20 # Reduced for better responsiveness

    def toggle_smart_border_mode(self):
        """Activates or deactivates the smart border detection tool."""
        if not NUMPY_AVAILABLE:
            messagebox.showerror("Dependency Missing", "The Smart Border tool requires the 'numpy' library for performance. Please install it by running:\npip install numpy")
            self.app.smart_border_mode_active = False
            return

        self.app.smart_border_mode_active = not self.app.smart_border_mode_active

        if self.app.smart_border_mode_active:
            self.app.paint_manager.toggle_paint_mode('off')
            if self.app.tile_eraser_mode_active:
                self.app.toggle_tile_eraser_mode()

            for comp in self.app.components.values():
                comp.is_draggable = True

            tile_components = [
                c for c in self.app.components.values() 
                if c.original_pil_image and not c.is_decal and not c.is_dock_asset
            ]
            if not tile_components:
                messagebox.showwarning("No Images", "No image tiles found to analyze.")
                self.app.smart_border_mode_active = False
                return

            min_x = min(c.world_x1 for c in tile_components)
            min_y = min(c.world_y1 for c in tile_components)
            max_x = max(c.world_x2 for c in tile_components)
            max_y = max(c.world_y2 for c in tile_components)

            self.composite_x_offset = min_x
            self.composite_y_offset = min_y

            composite_width = int(max_x - min_x)
            composite_height = int(max_y - min_y)
            self.active_detection_image = Image.new("RGBA", (composite_width, composite_height), (0,0,0,0))

            for comp in tile_components:
                world_w = int(comp.world_x2 - comp.world_x1)
                world_h = int(comp.world_y2 - comp.world_y1)
                if world_w <= 0 or world_h <= 0: continue
                
                resized_img = comp.original_pil_image.resize((world_w, world_h), Image.Resampling.LANCZOS)
                paste_x = int(comp.world_x1 - self.composite_x_offset)
                paste_y = int(comp.world_y1 - self.composite_y_offset)
                self.active_detection_image.paste(resized_img, (paste_x, paste_y), resized_img)

            # --- OPTIMIZATION: Convert to NumPy array ONCE on activation ---
            if self.active_detection_image:
                self.active_detection_alpha_numpy = np.array(self.active_detection_image.getchannel('A'))

            self.app.ui_manager.smart_border_btn.config(text="Smart Border (Active)", relief='sunken', bg='#ef4444')
            self.on_mouse_up_binding_id = self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
            self.on_mouse_move_binding_id = self.canvas.bind("<Motion>", self._update_canvas_brush_position)
            self.canvas.config(cursor="none")
            self.on_mouse_down_binding_id = self.canvas.bind("<Button-1>", self.start_drawing_stroke)
            self._create_canvas_brush_cursor()

            print(f"Smart Border mode ENABLED. Analyzing composite image of {len(tile_components)} tiles.")
        else:
            self.active_detection_image = None
            self.active_detection_alpha_numpy = None # Clear the NumPy array
            self.active_detection_component = None
            self.app.ui_manager.smart_border_btn.config(text="Smart Border Tool", relief='flat', bg='#0e7490')
            self.canvas.config(cursor="")

            self._cleanup_drawing_bindings()

            if self.cursor_canvas_id:
                self.canvas.delete(self.cursor_canvas_id)
                self.cursor_canvas_id = None
            if self.on_mouse_move_binding_id:
                self.canvas.unbind("<Motion>", self.on_mouse_move_binding_id)
            if self.on_mouse_down_binding_id:
                self.canvas.unbind("<Button-1>", self.on_mouse_down_binding_id)
            self.composite_x_offset = 0
            self.composite_y_offset = 0

            if self.highlight_layer_id:
                self.canvas.itemconfig(self.highlight_layer_id, state='hidden')
            
            self.highlight_layer_image = None
            self.highlight_layer_tk = None

            print("Smart Border mode DISABLED and all states reset.")

    def _cleanup_drawing_bindings(self):
        """Removes all temporary event bindings used by the smart border tool."""
        if hasattr(self, 'on_mouse_up_binding_id') and self.on_mouse_up_binding_id:
            self.canvas.unbind("<ButtonRelease-1>", self.on_mouse_up_binding_id)

    def start_drawing_stroke(self, event):
        """Handles the start of a drawing or erasing stroke."""
        if not self.app.smart_border_mode_active or not self.active_detection_image:
            return
        
        self.is_drawing = True
        print("[DEBUG] Smart Border: Mouse Down")
        self.last_drawn_x, self.last_drawn_y = event.x, event.y

        if self.is_erasing_points.get():
            self._process_erasure_at_point(event)
        else:
            self._process_detection_at_point(event)

    def on_mouse_drag(self, event):
        """Handles continuous drawing or erasing."""
        if not self.highlight_layer_id:
            self.highlight_layer_id = self.canvas.create_image(0, 0, anchor=tk.NW, tags=("smart_border_highlight_layer",))
            self.canvas.tag_lower(self.highlight_layer_id)

        if not self.is_drawing: return

        # --- FIX: Schedule a cursor update during drag to make it follow the mouse ---
        self._update_canvas_brush_position(event)

        draw_skip = self.smart_draw_skip.get()
        distance = math.sqrt((event.x - self.last_drawn_x)**2 + (event.y - self.last_drawn_y)**2)
        if distance < draw_skip:
            return # Skip processing if the mouse hasn't moved enough

        if self.is_erasing_points.get():
            self._process_erasure_at_point(event, defer_redraw=True)
        else:
            self._process_detection_at_point(event, defer_redraw=True)

        if not self.redraw_scheduled:
            self._schedule_redraw()

        # Update the last drawn position *after* processing
        self.last_drawn_x, self.last_drawn_y = event.x, event.y

    def on_mouse_up(self, event):
        """Finalizes a drawing or erasing stroke."""
        self.is_drawing = False
        print("[DEBUG] Smart Border: Mouse Up")
        if self.redraw_scheduled:
            self.app.master.after_cancel(self.after_id)
        self._perform_throttled_redraw()

    def on_preview_down(self, event):
        """Starts erasure in the zoomed preview."""
        self._update_preview_cursor(event)
        self._process_preview_erasure(event)

    def on_preview_drag(self, event):
        """Allows continuous erasure in the zoomed preview, with throttling."""
        self._update_preview_cursor(event)
        self._process_preview_erasure(event, defer_redraw=True)

        if not self.redraw_scheduled:
            self._schedule_redraw()

    def on_preview_up(self, event):
        """Ensures final state is immediately drawn after preview dragging stops."""
        if self.redraw_scheduled and self.after_id:
            self.app.master.after_cancel(self.after_id)
        self._perform_throttled_redraw()

    def on_preview_leave(self, event):
        """Hides the cursor when the mouse leaves the preview canvas."""
        if self.preview_cursor_circle_id:
            self.app.ui_manager.border_preview_canvas.itemconfig(self.preview_cursor_circle_id, state='hidden')

    def on_preview_move(self, event):
        """Updates the preview cursor position."""
        self._update_preview_cursor(event)

    def _schedule_redraw(self):
        """Schedules a redraw only if one isn't already pending."""
        if self.redraw_scheduled:
            return
        self.redraw_scheduled = True
        self.after_id = self.app.master.after(self.REDRAW_THROTTLE_MS, self._perform_throttled_redraw)

    def _perform_throttled_redraw(self):
        """Redraws the highlight points after a throttle delay."""
        if not self.app.master.winfo_exists(): return
        if self.is_drawing:
            self._update_highlights()
        self.after_id = None # Reset the ID after the redraw is performed
        self.redraw_scheduled = False # Allow the next redraw to be scheduled

    def _process_detection_at_point(self, event, defer_redraw=False):
        """The core logic to detect border points under the brush."""
        if not self.app.smart_border_mode_active or not self.active_detection_image:
            return

        brush_radius = self.smart_brush_radius.get()
        diff_threshold = self.smart_diff_threshold.get()
        img = self.active_detection_alpha_numpy # Use the pre-converted NumPy array
        if img is None: return

        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)

        img_x_center = int(world_x - self.composite_x_offset)
        img_y_center = int(world_y - self.composite_y_offset)

        x1, y1 = img_x_center - brush_radius, img_y_center - brush_radius
        x2, y2 = img_x_center + brush_radius, img_y_center + brush_radius

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
        if x1 >= x2 or y1 >= y2: return

        # --- OPTIMIZATION: Slice the existing NumPy array instead of cropping and converting ---
        alpha_channel = img[y1:y2, x1:x2]

        grad_x = np.abs(alpha_channel[:, 1:] - alpha_channel[:, :-1])
        grad_y = np.abs(alpha_channel[1:, :] - alpha_channel[:-1, :])

        edge_mask = np.zeros_like(alpha_channel, dtype=bool)
        edge_mask[:, :-1] |= (grad_x > diff_threshold)
        edge_mask[:-1, :] |= (grad_y > diff_threshold)

        edge_y_coords, edge_x_coords = np.where(edge_mask)

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

        points_to_remove = {p for p in self.raw_border_points if ((p[0] - erase_cx)**2 + (p[1] - erase_cy)**2) <= brush_radius_world**2}
        
        self.raw_border_points.difference_update(points_to_remove)

        if not defer_redraw:
            self._update_highlights()

    def _process_preview_erasure(self, event, defer_redraw=False):
        """Erases points from the raw_border_points list based on the zoomed preview brush."""
        if not self.raw_border_points: return

        scale = self.preview_scale_var.get()
        if scale == 0: return

        preview_canvas = self.app.ui_manager.border_preview_canvas
        if not preview_canvas: return
        preview_w = preview_canvas.winfo_width()
        preview_h = preview_canvas.winfo_height()

        main_canvas_x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        main_canvas_y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        center_x, center_y = self.app.camera.screen_to_world(main_canvas_x, main_canvas_y)

        zoom_x = event.x - preview_w / 2
        zoom_y = event.y - preview_h / 2
        world_x_center = (zoom_x / scale) + center_x
        world_y_center = (zoom_y / scale) + center_y

        world_eraser_radius = 10 / scale

        points_to_remove = {p for p in self.raw_border_points if ((p[0] - world_x_center)**2 + (p[1] - world_y_center)**2) <= world_eraser_radius**2}
        
        if points_to_remove:
            self.raw_border_points.difference_update(points_to_remove)
            if not defer_redraw:
                self._deferred_redraw()

    def _update_preview_cursor(self, event):
        """Updates the position and appearance of the preview brush cursor."""
        preview_canvas = self.app.ui_manager.border_preview_canvas
        if not preview_canvas: return

        if self.preview_cursor_circle_id is None:
            self.preview_cursor_circle_id = preview_canvas.create_oval(0, 0, 0, 0, outline="red", width=2, state='hidden')

        radius = 10
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

        preview_canvas.delete("all")
        self.preview_cursor_circle_id = None

        if not self.raw_border_points or not self.preview_area_world_coords:
            return

        scale = self.preview_scale_var.get()
        preview_w = preview_canvas.winfo_width()
        preview_h = preview_canvas.winfo_height()

        wx1, wy1, wx2, wy2 = self.preview_area_world_coords
        center_x = (wx1 + wx2) / 2
        center_y = (wy1 + wy2) / 2

        # The drawing logic for the preview canvas was moved into the main
        # app's `redraw_all_zoomable` function for optimization. This function
        # is now only responsible for setting up the preview area coordinates.

    def clear_detected_points(self):
        """Clears all detected points and their highlights."""
        self.raw_border_points.clear()
        self._update_highlights()
        self.update_preview_canvas()
        print("Cleared all detected border points.")

    def on_erase_mode_toggle(self):
        """Handles UI update when 'Erase Points' is toggled."""
        self._update_highlights()
        self._update_canvas_brush_color()

    def _update_canvas_brush_size(self, event=None):
        """Updates the size of the canvas-drawn cursor."""
        # This function now just needs to trigger a redraw of the cursor image.        
        self._redraw_cursor_image_style()
        
    def _create_canvas_brush_cursor(self):
        """Creates the canvas image used as the brush cursor (replacing the slow oval)."""
        if self.cursor_canvas_id:
            self.canvas.delete(self.cursor_canvas_id)
        
        size = self.cursor_image_size
        self.cursor_pil_image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        self.cursor_tk_image = ImageTk.PhotoImage(self.cursor_pil_image)

        self.cursor_canvas_id = self.canvas.create_image(
            0, 0, 
            image=self.cursor_tk_image, 
            anchor=tk.NW, 
            tags=('brush_cursor',), 
            state='hidden'
        )
        self._redraw_cursor_image_style()

    def _redraw_cursor_image_style(self):
        """Performs the expensive PIL/PhotoImage update for the cursor's visual style/size."""
        if not self.cursor_canvas_id: return

        radius = self.smart_brush_radius.get()
        size = self.cursor_image_size
        offset = size // 2

        # 1. Redraw the circle onto the PIL layer (The expensive step)
        self.cursor_pil_image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(self.cursor_pil_image)
        color = "red" if self.is_erasing_points.get() else "cyan"
        draw.ellipse((offset - radius, offset - radius, offset + radius, offset + radius), outline=color, width=2)

        # 2. Update the PhotoImage on the canvas
        self.cursor_tk_image.paste(self.cursor_pil_image)
        self.canvas.itemconfig(self.cursor_canvas_id, state='normal')
        self.canvas.tag_raise(self.cursor_canvas_id)
        
        # Ensure the cursor is placed correctly on screen
        # Since we don't have the event, we just move it to the current pointer location
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        self.canvas.coords(self.cursor_canvas_id, x - offset, y - offset)

    def _update_canvas_brush_position(self, event):
        """Moves the image-drawn cursor immediately (cheap operation)."""
        if not self.cursor_canvas_id: return

        # 1. Perform the immediate, cheap move
        size = self.cursor_image_size
        offset = size // 2
        self.canvas.coords(self.cursor_canvas_id, event.x - offset, event.y - offset)
        
        # NOTE: The expensive style/color update is now handled only when radius/color changes, 
        # via calls to _update_canvas_brush_color or _update_canvas_brush_size.
        # This function no longer needs to schedule a redraw.

    def _update_canvas_brush_color(self):
        """Updates the color of the image-drawn cursor by forcing a redraw."""
        if not self.cursor_canvas_id: return
        
        # Just call the style redraw function
        self._redraw_cursor_image_style()