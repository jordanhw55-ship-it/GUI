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
from uc_cursor_window import CursorWindow

class SmartBorderManager:
    """Manages the interactive 'Smart Border' tool."""
    def __init__(self, app, border_manager):
        self.app = app
        self.canvas = app.canvas
        self.border_manager = border_manager
        self.on_mouse_down_binding_id = None

        # --- NEW: Instantiate the custom cursor window ---
        self.cursor_window = CursorWindow(app.master)

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
        self.highlight_color = (0, 255, 255, 255) # This is for the detected points, not the cursor
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

            print("[DEBUG] Smart Border: Binding <ButtonRelease-1>, <Motion>, <Button-1>.")
            self.app.ui_manager.smart_border_btn.config(text="Smart Border (Active)", relief='sunken', bg='#ef4444')
            self.on_mouse_up_binding_id = self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
            self.on_mouse_move_binding_id = self.canvas.bind("<Motion>", self._update_canvas_brush_position)
            self.canvas.config(cursor="none")
            # --- FIX: Explicitly bind B1-Motion to the smart manager's drag handler ---
            # This ensures that dragging to draw works correctly with the transparent cursor window.
            self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
            self.on_mouse_down_binding_id = self.canvas.bind("<Button-1>", self.start_drawing_stroke) # This might be redundant with app-level binding
            self._create_canvas_brush_cursor()

            print(f"Smart Border mode ENABLED. Analyzing composite image of {len(tile_components)} tiles.")
        else:
            self.active_detection_image = None
            self.active_detection_alpha_numpy = None # Clear the NumPy array
            self.active_detection_component = None
            self.app.ui_manager.smart_border_btn.config(text="Smart Border Tool", relief='flat', bg='#0e7490')
            self.canvas.config(cursor="")
            print("[DEBUG] Smart Border: Cleaning up bindings.")

            self._cleanup_drawing_bindings()

            # --- NEW: Hide the cursor window ---
            self.cursor_window.hide()
            if self.on_mouse_move_binding_id:
                print("[DEBUG] Smart Border: Unbinding <Motion>.")
                self.canvas.unbind("<Motion>", self.on_mouse_move_binding_id)
            # --- FIX: Unbind the specific drag handler for this tool ---
            print("[DEBUG] Smart Border: Unbinding <B1-Motion>.")
            self.canvas.unbind("<B1-Motion>")
            if self.on_mouse_down_binding_id:
                print("[DEBUG] Smart Border: Unbinding <Button-1>.")
                self.canvas.unbind("<Button-1>", self.on_mouse_down_binding_id)
            self.composite_x_offset = 0
            self.composite_y_offset = 0

            if self.highlight_layer_id:
                # --- DEFINITIVE FIX: Delete the canvas item and reset all related state ---
                self.canvas.delete(self.highlight_layer_id)
                self.highlight_layer_id = None
                self.highlight_layer_image = None
                self.highlight_layer_tk = None

            # --- FIX: Restore the generic drag handler to prevent lingering bindings ---
            self.app.bind_generic_drag_handler()

            # --- DEFINITIVE FIX: Reset binding IDs to None after unbinding ---
            # This ensures that the next time the tool is activated, it doesn't carry over stale binding IDs.
            self.on_mouse_up_binding_id = None
            self.on_mouse_move_binding_id = None
            self.on_mouse_down_binding_id = None

            print("Smart Border mode DISABLED and all states reset.")

    def _cleanup_drawing_bindings(self):
        """Removes all temporary event bindings used by the smart border tool."""
        if hasattr(self, 'on_mouse_up_binding_id') and self.on_mouse_up_binding_id:
            print("[DEBUG] Smart Border: Unbinding <ButtonRelease-1>.")
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

        # --- REFACTOR: More efficient gradient calculation and thresholding ---
        # 1. Calculate horizontal and vertical gradients.
        grad_x = np.abs(np.diff(alpha_channel.astype(np.int16), axis=1)) > diff_threshold
        grad_y = np.abs(np.diff(alpha_channel.astype(np.int16), axis=0)) > diff_threshold

        # 2. Combine gradients into a single mask. We pad the smaller gradient arrays
        #    to match the original alpha_channel shape for the 'where' operation.
        edge_mask = np.zeros_like(alpha_channel, dtype=bool)
        edge_mask[:, :-1] |= grad_x
        edge_mask[:-1, :] |= grad_y

        edge_y_coords, edge_x_coords = np.where(edge_mask)

        # --- REFACTOR: Use more direct vectorized operations for coordinate conversion ---
        world_coords = np.column_stack((edge_x_coords + x1 + self.composite_x_offset, edge_y_coords + y1 + self.composite_y_offset))
        new_points = set(map(tuple, world_coords))
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
        
        # --- FIX: Restore the drawing logic for the preview canvas ---
        # This logic was incorrectly removed in a previous refactor.
        points_to_draw = []
        for p_x, p_y in self.raw_border_points:
            # Check if the point is within the selected world coordinates
            if wx1 <= p_x <= wx2 and wy1 <= p_y <= wy2:
                # Translate world point to be relative to the center of the preview area
                relative_x = (p_x - center_x) * scale
                relative_y = (p_y - center_y) * scale
                # Translate to canvas coordinates (center of preview canvas)
                screen_x = relative_x + preview_w / 2
                screen_y = relative_y + preview_h / 2
                points_to_draw.append((screen_x, screen_y))
        if points_to_draw:
            # --- FIX: Draw points directly onto the preview canvas widget ---
            for x, y in points_to_draw:
                preview_canvas.create_oval(x-1, y-1, x+1, y+1, fill="cyan", outline="cyan")

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
        # This function now just needs to trigger the initial drawing of the cursor style
        # and show the window.
        self._redraw_cursor_image_style()
        self.cursor_window.show()

    def _redraw_cursor_image_style(self):
        """Generates the PIL image for the cursor and updates the cursor window."""
        radius = self.smart_brush_radius.get()
        size = (radius * 2) + 4
        offset = size // 2

        # 1. Create a new PIL image for the cursor.
        cursor_pil_image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(cursor_pil_image)
        color = "red" if self.is_erasing_points.get() else "cyan"
        draw.ellipse((offset - radius, offset - radius, offset + radius, offset + radius), outline=color, width=2)

        # 2. Update the cursor window with the new image.
        self.cursor_window.set_image(cursor_pil_image)

        # 3. Immediately update its position to the current mouse location.
        # This prevents the cursor from appearing at (0,0) or an old position.
        root_x = self.app.master.winfo_pointerx()
        root_y = self.app.master.winfo_pointery()
        self.cursor_window.move(root_x - offset, root_y - offset)

    def _update_canvas_brush_position(self, event):
        """Moves the custom cursor window to follow the mouse."""
        # The cursor window needs absolute screen coordinates.
        # We get these from the event's root_x and root_y attributes.
        # If they don't exist, we calculate them.
        try:
            root_x, root_y = event.x_root, event.y_root
        except AttributeError:
            root_x = self.canvas.winfo_rootx() + event.x
            root_y = self.canvas.winfo_rooty() + event.y

        radius = self.smart_brush_radius.get()
        offset = radius + 2 # Half of the image size ((radius*2)+4)/2
        self.cursor_window.move(root_x - offset, root_y - offset)

    def _update_canvas_brush_color(self):
        """Updates the color of the cursor by forcing a style redraw."""
        self._redraw_cursor_image_style()

    def toggle_preview_selection_mode(self):
        """Activates the mode to select an area on the main canvas for previewing."""
        if not self.app.smart_border_mode_active:
            messagebox.showwarning("Tool Inactive", "The Smart Border tool must be active to select a preview area.")
            return

        self.is_selecting_preview_area = True
        self.canvas.config(cursor="crosshair")

        # Unbind the generic drag handler to prevent conflicts
        print("[DEBUG] Preview Selection: Unbinding <B1-Motion> to prevent conflicts.")
        self.canvas.unbind("<B1-Motion>")

        # Bind the specific selection events
        print("[DEBUG] Preview Selection: Binding <Button-1>, <B1-Motion>, <ButtonRelease-1> for selection.")
        self.canvas.bind("<Button-1>", self._on_preview_selection_press)
        self.canvas.bind("<B1-Motion>", self._on_preview_selection_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_preview_selection_release)

    def _on_preview_selection_press(self, event):
        """Handles the start of dragging a selection box on the main canvas."""
        if not self.is_selecting_preview_area: return

        self.preview_selection_start_x = event.x
        self.preview_selection_start_y = event.y

        if self.preview_selection_rect_id:
            self.canvas.delete(self.preview_selection_rect_id)

        self.preview_selection_rect_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="yellow", dash=(5, 3), width=2
        )

    def _on_preview_selection_drag(self, event):
        """Updates the selection box as the user drags the mouse."""
        if not self.is_selecting_preview_area or not self.preview_selection_rect_id: return
        self.canvas.coords(self.preview_selection_rect_id, self.preview_selection_start_x, self.preview_selection_start_y, event.x, event.y)

    def _on_preview_selection_release(self, event):
        """Finalizes the selection, captures the area, and updates the preview."""
        if not self.is_selecting_preview_area: return

        sx1, sy1 = self.preview_selection_start_x, self.preview_selection_start_y
        sx2, sy2 = event.x, event.y
        wx1, wy1 = self.app.camera.screen_to_world(sx1, sy1)
        wx2, wy2 = self.app.camera.screen_to_world(sx2, sy2)

        self.preview_area_world_coords = (min(wx1, wx2), min(wy1, wy2), max(wx1, wx2), max(wy1, wy2))

        self.canvas.delete(self.preview_selection_rect_id)
        self.preview_selection_rect_id = None
        self.is_selecting_preview_area = False
        self.canvas.config(cursor="none") # Revert to the smart border cursor

        # Re-bind the generic drag handler and the initial click handler
        print("[DEBUG] Preview Selection: Restoring generic drag handler and <Button-1> binding.")
        self.app.bind_generic_drag_handler()
        self.canvas.bind("<Button-1>", self.start_drawing_stroke)

        # --- FIX: Trigger a redraw to show the points in the preview canvas ---
        self.app.redraw_all_zoomable()

        self.update_preview_canvas()
        print(f"[DEBUG] Preview selection mode DEACTIVATED. Area captured: {self.preview_area_world_coords}")

    def finalize_border(self):
        """
        Converts the detected raw_border_points into a new, draggable border component.
        """
        if not self.raw_border_points:
            messagebox.showwarning("No Points", "No border points have been detected. Use the smart border tool to draw a border first.")
            return

        # 1. Find the bounding box of the points in world coordinates.
        min_x = min(p[0] for p in self.raw_border_points)
        min_y = min(p[1] for p in self.raw_border_points)
        max_x = max(p[0] for p in self.raw_border_points)
        max_y = max(p[1] for p in self.raw_border_points)

        width = int(max_x - min_x) + 1
        height = int(max_y - min_y) + 1

        if width <= 0 or height <= 0:
            messagebox.showerror("Error", "Could not finalize border due to invalid dimensions.")
            return

        # 2. Create a new PIL image for the border.
        border_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(border_image)

        # 3. Draw the points onto the new image, translating them to local coordinates.
        for p_x, p_y in self.raw_border_points:
            local_x = int(p_x - min_x)
            local_y = int(p_y - min_y)
            draw.point((local_x, local_y), fill=self.highlight_color)

        # 4. Create a new DraggableComponent for the border.
        border_tag = f"smart_border_{self.app.image_manager.next_dynamic_id}"
        self.app.image_manager.next_dynamic_id += 1

        new_border_comp = DraggableComponent(
            self.app, border_tag, min_x, min_y, max_x, max_y, "green", border_tag
        )
        new_border_comp.is_decal = True # Treat it like a decal for dragging/stamping
        new_border_comp.original_pil_image = border_image.copy()

        # 5. Add the new component to the application and bind its events.
        self.app.components[border_tag] = new_border_comp
        self.app._bind_component_events(border_tag)
        new_border_comp.set_image(border_image) # This will handle the initial draw

        # 6. Clear the detected points and deactivate the tool.
        self.clear_detected_points()
        self.toggle_smart_border_mode() # This will clean up bindings and cursors

        messagebox.showinfo("Border Finalized", f"New border component '{border_tag}' has been created.")