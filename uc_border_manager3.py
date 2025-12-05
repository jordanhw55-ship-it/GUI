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
        self.smart_brush_radius = tk.IntVar(value=15)
        self.smart_diff_threshold = tk.IntVar(value=50)
        self.smart_draw_skip = tk.IntVar(value=5)
        self.active_detection_image = None
        self.active_detection_component = None
        self.composite_x_offset = 0
        self.composite_y_offset = 0

        self.preview_scale_var = tk.DoubleVar(value=1.0)
        self.preview_cursor_circle_id = None

        self.highlight_layer_image = None
        self.highlight_layer_tk = None
        self.highlight_layer_id = None
        self.highlight_color = (0, 255, 255, 255)

        self.cursor_file_path = None
        self.mask_file_path = None
        self.on_mouse_move_binding_id = None
        self.REDRAW_THROTTLE_MS = 50

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

            self.app.ui_manager.smart_border_btn.config(text="Smart Border (Active)", relief='sunken', bg='#ef4444')
            self.on_mouse_up_binding_id = self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
            self.on_mouse_move_binding_id = self.canvas.bind("<Motion>", self._update_canvas_brush_position)
            self.canvas.config(cursor="none")
            self.on_mouse_down_binding_id = self.canvas.bind("<Button-1>", self.start_drawing_stroke)
            self._create_canvas_brush_cursor()

            print(f"Smart Border mode ENABLED. Analyzing composite image of {len(tile_components)} tiles.")
        else:
            self.active_detection_image = None
            self.active_detection_component = None
            self.app.ui_manager.smart_border_btn.config(text="Smart Border Tool", relief='flat', bg='#0e7490')
            self.canvas.config(cursor="")

            self._cleanup_drawing_bindings()
            
            if self.brush_cursor_oval_id:
                self.canvas.delete(self.brush_cursor_oval_id)
                self.brush_cursor_oval_id = None
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
        self._update_canvas_brush_position(event)

        if not self.highlight_layer_id:
            self.highlight_layer_id = self.canvas.create_image(0, 0, anchor=tk.NW, tags=("smart_border_highlight_layer",))
            self.canvas.tag_lower(self.highlight_layer_id)

        if not self.is_drawing: return
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
        print("[DEBUG] Smart Border: Mouse Up")
        if self.redraw_scheduled:
            self.app.master.after_cancel(self._deferred_redraw)
        self._deferred_redraw()

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
        self.redraw_scheduled = False

    def _process_detection_at_point(self, event, defer_redraw=False):
        """The core logic to detect border points under the brush."""
        if not self.app.smart_border_mode_active or not self.active_detection_image:
            return

        brush_radius = self.smart_brush_radius.get()
        diff_threshold = self.smart_diff_threshold.get()
        img = self.active_detection_image
        if not img: return

        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)

        img_x_center = int(world_x - self.composite_x_offset)
        img_y_center = int(world_y - self.composite_y_offset)

        x1, y1 = img_x_center - brush_radius, img_y_center - brush_radius
        x2, y2 = img_x_center + brush_radius, img_y_center + brush_radius

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(img.width, x2), min(img.height, y2)
        if x1 >= x2 or y1 >= y2: return

        brush_area_img = img.crop((x1, y1, x2, y2))
        alpha_channel = np.array(brush_area_img.getchannel('A'))

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

        for raw_x, raw_y in self.raw_border_points:
            if not (wx1 <= raw_x <= wx2 and wy1 <= raw_y <= wy2):
                continue

            rel_x = raw_x - center_x; rel_y = raw_y - center_y
            zoom_x = rel_x * scale; zoom_y = rel_y * scale
            preview_x = zoom_x + preview_w / 2; preview_y = zoom_y + preview_h / 2

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

    def on_erase_mode_toggle(self):
        """Handles UI update when 'Erase Points' is toggled."""
        self._update_highlights()
        self._update_canvas_brush_color()

    def _update_canvas_brush_size(self, event=None):
        """Updates the size of the canvas-drawn cursor."""
        if not self.brush_cursor_oval_id: return

        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()

        radius = self.smart_brush_radius.get()
        x1, y1 = (x - radius), (y - radius)
        x2, y2 = (x + radius), (y + radius)
        self.canvas.coords(self.brush_cursor_oval_id, x1, y1, x2, y2)

        if self.is_drawing:
            self.on_mouse_drag(type('Event', (), {'x': x, 'y': y}))
        else:
            self._process_detection_at_point(type('Event', (), {'x': x, 'y': y}))
        
    def _create_canvas_brush_cursor(self):
        """Creates the canvas oval used as the brush cursor."""
        if self.brush_cursor_oval_id:
            self.canvas.delete(self.brush_cursor_oval_id)
        
        color = "red" if self.is_erasing_points.get() else "cyan"
        self.brush_cursor_oval_id = self.canvas.create_oval(0, 0, 0, 0, outline=color, width=2, state='hidden')

    def _update_canvas_brush_position(self, event):
        """Moves the canvas-drawn cursor to follow the mouse."""
        if not self.brush_cursor_oval_id: return

        radius = self.smart_brush_radius.get()
        x1, y1 = (event.x - radius), (event.y - radius)
        x2, y2 = (event.x + radius), (y + radius)
        self.canvas.coords(self.brush_cursor_oval_id, x1, y1, x2, y2)
        self.canvas.itemconfig(self.brush_cursor_oval_id, state='normal')
        self.canvas.tag_raise(self.brush_cursor_oval_id)

    def _update_canvas_brush_color(self):
        """Updates the color of the canvas-drawn cursor."""
        if not self.brush_cursor_oval_id: return

        is_erasing = self.is_erasing_points.get()
        color = "red" if is_erasing else "cyan"
        self.canvas.itemconfig(self.brush_cursor_oval_id, outline=color)

    def toggle_preview_selection_mode(self):
        """Activates the mode to select an area on the main canvas for previewing."""
        if not self.app.smart_border_mode_active:
            messagebox.showwarning("Tool Inactive", "The Smart Border tool must be active to select a preview area.")
            return

        self.is_selecting_preview_area = True
        self.canvas.config(cursor="crosshair")

        self.canvas.bind("<Button-1>", self._on_preview_selection_press)
        self.canvas.bind("<B1-Motion>", self._on_preview_selection_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_preview_selection_release)
        print("[DEBUG] Preview selection mode ACTIVATED.")

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
        self.canvas.config(cursor="none")
        self.app.bind_generic_drag_handler()
        self.canvas.bind("<Button-1>", self.start_drawing_stroke)

        self.update_preview_canvas()
        print(f"[DEBUG] Preview selection mode DEACTIVATED. Area captured: {self.preview_area_world_coords}")

    def finalize_border(self):
        """Creates a new component from the detected border points."""
        if not self.raw_border_points:
            messagebox.showwarning("No Points", "No border points have been detected to finalize.")
            return
        
        thickness = self.border_manager.border_thickness.get()
        growth_direction = self.border_manager.border_growth_direction.get()

        points_list = list(self.raw_border_points)
        min_x = int(min(p[0] for p in points_list))
        min_y = int(min(p[1] for p in points_list))
        max_x = int(max(p[0] for p in points_list))
        max_y = int(max(p[1] for p in points_list))

        logical_w = max_x - min_x + 1
        logical_h = max_y - min_y + 1

        if logical_w <= 0 or logical_h <= 0:
            messagebox.showerror("Error", "Could not create border from points (invalid size).")
            return

        render_w, render_h = logical_w, logical_h
        comp_x, comp_y = min_x, min_y
        if growth_direction == 'out':
            comp_x -= thickness
            comp_y -= thickness
            render_w += thickness * 2
            render_h += thickness * 2
        
        point_segments = []
        remaining_points = set(points_list)
        while remaining_points:
            current_segment = [remaining_points.pop()]
            while True:
                last_point = current_segment[-1]
                search_radius_sq = 4**2 
                nearest_neighbor = None
                min_dist_sq = float('inf')

                candidates = {p for p in remaining_points if last_point[0]-4 <= p[0] <= last_point[0]+4 and last_point[1]-4 <= p[1] <= last_point[1]+4}

                for p in candidates:
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

        border_image = self.border_manager._render_border_image((render_w, render_h), (render_w, render_h), shape_form="path", path_data=point_segments, is_segmented=True, relative_to=(comp_x, comp_y))
        if not border_image: return

        border_tag = f"smart_border_{self.border_manager.next_border_id}"
        self.border_manager.next_border_id += 1
        border_comp = DraggableComponent(self.app, border_tag, comp_x, comp_y, comp_x + render_w, comp_y + render_h, "blue", "BORDER")
        border_comp.is_draggable = True
        border_comp.set_image(border_image)

        self.app.components[border_tag] = border_comp
        self.app._bind_component_events(border_tag)
        self.app.canvas.tag_raise(border_tag)
        self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        print("[DEBUG] Finalizing border, initiating cleanup...")
        self.toggle_smart_border_mode()

        messagebox.showinfo("Success", f"Created new border component: {border_tag}")