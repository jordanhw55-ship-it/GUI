import tkinter as tk

class Camera:
    """Manages the canvas viewport (zoom and pan)."""
    def __init__(self, app, canvas):
        self.app = app
        self.canvas = canvas
        self.zoom_scale = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.zoom_job = None

        self.zoom_label_var = tk.StringVar(value="100%")

        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        self.canvas.bind("<Control-plus>", self.zoom_in)
        self.canvas.bind("<Control-equal>", self.zoom_in)
        self.canvas.bind("<Control-minus>", self.zoom_out)
        self.canvas.bind("<Control-Button-1>", self.on_pan_press)
        self.canvas.bind("<Control-B1-Motion>", self.on_pan_drag)
        self.canvas.bind("<Control-ButtonRelease-1>", self.on_pan_release)

    def world_to_screen(self, world_x, world_y):
        """Converts world coordinates to screen coordinates."""
        screen_x = (world_x * self.zoom_scale) + self.pan_offset_x
        screen_y = (world_y * self.zoom_scale) + self.pan_offset_y
        return screen_x, screen_y

    def screen_to_world(self, screen_x, screen_y):
        """Converts screen coordinates to world coordinates."""
        world_x = (screen_x - self.pan_offset_x) / self.zoom_scale
        world_y = (screen_y - self.pan_offset_y) / self.zoom_scale
        return world_x, world_y

    def on_zoom(self, event):
        """Handles zooming the canvas with Ctrl+MouseWheel."""
        if self.app.paint_manager.paint_mode_active or self.app.paint_manager.eraser_mode_active:
            self.app.paint_manager.toggle_paint_mode(tool='off')

        if self.zoom_job:
            self.app.master.after_cancel(self.zoom_job)
        self.zoom_job = self.app.master.after(300, lambda: self.app.redraw_all_zoomable(use_fast_preview=False))

        mouse_world_x_before, mouse_world_y_before = self.screen_to_world(event.x, event.y)

        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_scale *= factor

        self.pan_offset_x = event.x - (mouse_world_x_before * self.zoom_scale)
        self.pan_offset_y = event.y - (mouse_world_y_before * self.zoom_scale)

        self._update_zoom_display()
        self._clamp_camera_pan()
        self.app.redraw_all_zoomable(use_fast_preview=True)

    def zoom_in(self, event=None):
        """Zooms in on the center of the canvas."""
        x = self.canvas.winfo_width() / 2
        y = self.canvas.winfo_height() / 2
        center_world_x, center_world_y = self.screen_to_world(x, y)

        factor = 1.1
        self.zoom_scale *= factor

        self.pan_offset_x = x - (center_world_x * self.zoom_scale)
        self.pan_offset_y = y - (center_world_y * self.zoom_scale)

        self._update_zoom_display()
        self._clamp_camera_pan()
        self.app.redraw_all_zoomable()
        return "break"

    def zoom_out(self, event=None):
        """Zooms out from the center of the canvas."""
        x = self.canvas.winfo_width() / 2
        y = self.canvas.winfo_height() / 2
        center_world_x, center_world_y = self.screen_to_world(x, y)

        factor = 0.9
        self.zoom_scale *= factor

        self.pan_offset_x = x - (center_world_x * self.zoom_scale)
        self.pan_offset_y = y - (center_world_y * self.zoom_scale)

        self._update_zoom_display()
        self._clamp_camera_pan()
        self.app.redraw_all_zoomable()
        return "break"

    def _update_zoom_display(self):
        """Updates the zoom percentage label."""
        zoom_percentage = f"{self.zoom_scale * 100:.0f}%"
        self.zoom_label_var.set(zoom_percentage)
        print(f"Zoom: {self.zoom_scale:.2f}x")

    def reset_view(self, event=None):
        """Resets the zoom to 100% and centers the pan."""
        self.zoom_scale = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self._update_zoom_display()
        self.app.redraw_all_zoomable()
        print("View has been reset.")

    def _clamp_camera_pan(self):
        """Ensures the composition area is always visible on the canvas."""
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        comp_world_w = self.app.COMP_AREA_X2 - self.app.COMP_AREA_X1
        comp_world_h = self.app.COMP_AREA_Y2 - self.app.COMP_AREA_Y1

        scaled_comp_w = comp_world_w * self.zoom_scale
        scaled_comp_h = comp_world_h * self.zoom_scale

        if scaled_comp_w < canvas_w:
            self.pan_offset_x = (canvas_w - scaled_comp_w) / 2 - (self.app.COMP_AREA_X1 * self.zoom_scale)
        else:
            max_pan_x = -(self.app.COMP_AREA_X1 * self.zoom_scale)
            min_pan_x = canvas_w - (self.app.COMP_AREA_X2 * self.zoom_scale)
            self.pan_offset_x = max(min_pan_x, min(self.pan_offset_x, max_pan_x))

        if scaled_comp_h < canvas_h:
            self.pan_offset_y = (canvas_h - scaled_comp_h) / 2 - (self.app.COMP_AREA_Y1 * self.zoom_scale)
        else:
            max_pan_y = -(self.app.COMP_AREA_Y1 * self.zoom_scale)
            min_pan_y = canvas_h - (self.app.COMP_AREA_Y2 * self.zoom_scale)
            self.pan_offset_y = max(min_pan_y, min(self.pan_offset_y, max_pan_y))

    def on_pan_press(self, event):
        """Records the starting position for panning."""
        if self.app.paint_manager.paint_mode_active or self.app.paint_manager.eraser_mode_active:
            self.app.paint_manager.toggle_paint_mode(tool='off')
        
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.app.is_group_dragging = True
        # --- FIX: Save pre-move state for all main tiles ---
        self.app._save_pre_move_state()

        self.canvas.config(cursor="fleur")
        # Return "break" to prevent other bindings from firing (like individual component drag)
        return "break"

    def on_pan_drag(self, event):
        """Drags all non-dock, non-clone components at once."""
        if not self.app.is_group_dragging: return
        dx_world = (event.x - self.pan_start_x) / self.zoom_scale
        dy_world = (event.y - self.pan_start_y) / self.zoom_scale
        
        self.app.move_all_main_tiles(dx_world, dy_world)
        
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        
        self.app.redraw_all_zoomable()

    def on_pan_release(self, event):
        """Resets the cursor when panning is finished."""
        self.app.is_group_dragging = False
        # --- FIX: Finalize group move for undo ---
        if self.app.pre_move_state:
            self.app._save_undo_state({'type': 'move', 'positions': self.app.pre_move_state})
            self.app.pre_move_state = {} # Clear the temp state

        self.canvas.config(cursor="")
        # Return "break" to prevent other release bindings from firing
        return "break"