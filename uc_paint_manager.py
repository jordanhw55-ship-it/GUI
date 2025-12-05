import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

class PaintManager:
    """Manages all painting and erasing functionality."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        
        self.paint_mode_active = False
        self.eraser_mode_active = False
        self.universal_eraser_mode_active = False # NEW: For the universal eraser
        self.paint_color = "red"
        self.brush_size = tk.IntVar(value=4)
        self.last_paint_x = None
        self.last_paint_y = None
        self.modified_in_drag = set() # NEW: Track components modified in a single drag for undo
        
        self.paint_layer_image = None
        self.paint_layer_tk = None
        self.paint_layer_id = None

    def toggle_paint_mode(self, tool: str):
        """Toggles the painting or erasing mode on or off."""
        is_activating_paint = tool == 'paint' and not self.paint_mode_active
        is_activating_eraser = tool == 'eraser' and not self.eraser_mode_active
        is_activating_universal_eraser = tool == 'universal_eraser' and not self.universal_eraser_mode_active

        # Deactivate all tools first
        self.paint_mode_active = False
        self.eraser_mode_active = False
        self.universal_eraser_mode_active = False
        self.app.ui_manager.paint_toggle_btn.config(text="Paint Brush", bg='#d97706', relief='flat')
        self.app.ui_manager.eraser_toggle_btn.config(text="Transparency Brush", bg='#0e7490', relief='flat')
        self.app.ui_manager.universal_eraser_btn.config(text="Universal Eraser", bg='#be123c', relief='flat')
        self.app.ui_manager.paint_color_button.config(state='disabled')

        # Activate the selected tool if it wasn't already active
        if is_activating_paint:
            self.paint_mode_active = True
            self.app.ui_manager.paint_toggle_btn.config(text="Paint Brush (Active)", bg='#ef4444', relief='sunken')
            self.app.ui_manager.paint_color_button.config(state='normal')
            print("Paint mode ENABLED.")
        elif is_activating_eraser:
            self.eraser_mode_active = True # This is our transparency brush
            self.app.ui_manager.eraser_toggle_btn.config(text="Transparency Brush (Active)", bg='#ef4444', relief='sunken')
            print("Eraser mode ENABLED.")
        elif is_activating_universal_eraser:
            self.universal_eraser_mode_active = True
            self.app.ui_manager.universal_eraser_btn.config(text="Universal Eraser (Active)", bg='#ef4444', relief='sunken')
            print("Universal Eraser mode ENABLED.")
        else:
            print("Paint and Eraser modes DISABLED.")

        is_any_paint_tool_active = self.paint_mode_active or self.eraser_mode_active
        if is_any_paint_tool_active:
            if not self.paint_layer_image:
                canvas_w = self.canvas.winfo_width()
                canvas_h = self.canvas.winfo_height()
                self.paint_layer_image = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                self.paint_layer_tk = ImageTk.PhotoImage(self.paint_layer_image)
                self.paint_layer_id = self.canvas.create_image(0, 0, image=self.paint_layer_tk, anchor=tk.NW, tags=("paint_layer", "zoom_target"), state='normal')
                self.app._save_undo_state(self.paint_layer_image.copy())

        # Disable dragging if any tool is active
        is_any_tool_active = self.paint_mode_active or self.eraser_mode_active or self.universal_eraser_mode_active
        if is_any_tool_active:
            for comp in self.app.components.values():
                comp.is_draggable = False
            if self.paint_layer_id:
                self.canvas.tag_raise(self.paint_layer_id)
            self.app._keep_docks_on_top()
        else:
            for comp in self.app.components.values():
                comp.is_draggable = True
            # --- FIX: Restore the generic drag handler when all paint tools are off ---
            self.app.bind_generic_drag_handler()
            print("[DEBUG] All paint tools DISABLED. Component dragging enabled, generic drag handler restored.")

    def choose_paint_color(self):
        """Opens a color chooser and sets the paint color."""
        from tkinter import colorchooser
        color_code = colorchooser.askcolor(title="Choose paint color")
        if color_code and color_code[1]:
            self.paint_color = color_code[1]
            print(f"Paint color set to: {self.paint_color}")

    def clear_paintings(self):
        """Removes all lines drawn on the canvas."""
        if self.paint_layer_image:
            self.app._save_undo_state(self.paint_layer_image.copy())
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            self.paint_layer_image = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            self.app.redraw_all_zoomable()
            print("All paintings have been cleared.")

    def paint_on_canvas(self, event):
        """Draws on the dedicated paint layer image."""
        is_painting = self.paint_mode_active or self.eraser_mode_active
        if not is_painting or not self.paint_layer_image:
            return
    
        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)

        if self.last_paint_x is None and self.last_paint_y is None:
            self.app._save_undo_state(self.paint_layer_image.copy())

        if self.last_paint_x and self.last_paint_y:
            last_world_x, last_world_y = self.app.camera.screen_to_world(self.last_paint_x, self.last_paint_y)
            paint_color = (0, 0, 0, 0) if self.eraser_mode_active else self.paint_color

            draw = ImageDraw.Draw(self.paint_layer_image)
            draw.line(
                (last_world_x, last_world_y, world_x, world_y),
                fill=paint_color,
                width=self.brush_size.get(),
                joint='curve'
            )
            self.app.redraw_all_zoomable()
    
        self.last_paint_x, self.last_paint_y = event.x, event.y

    def reset_paint_line(self, event):
        """Resets the start of the line when the mouse is released."""
        self.last_paint_x, self.last_paint_y = None, None
        self.modified_in_drag.clear() # Clear the set of modified components for the next drag

    def erase_on_components(self, event):
        """Erases parts of any component image under the brush stroke."""
        if not self.universal_eraser_mode_active:
            return

        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)

        if self.last_paint_x and self.last_paint_y:
            last_world_x, last_world_y = self.app.camera.screen_to_world(self.last_paint_x, self.last_paint_y)
            brush_size = self.brush_size.get()

            # Iterate through all components to check for intersection
            for comp in self.app.components.values():
                if not comp.pil_image or comp.is_dock_asset:
                    continue

                # Simple bounding box check for intersection
                if (max(last_world_x, world_x) + brush_size > comp.world_x1 and
                    min(last_world_x, world_x) - brush_size < comp.world_x2 and
                    max(last_world_y, world_y) + brush_size > comp.world_y1 and
                    min(last_world_y, world_y) - brush_size < comp.world_y2):

                    # --- Save state for Undo ---
                    # If this is the first time we're hitting this component in this drag, save its state.
                    if comp.tag not in self.modified_in_drag:
                        undo_data = {comp.tag: comp.pil_image.copy()}
                        self.app._save_undo_state(undo_data)
                        self.modified_in_drag.add(comp.tag)

                    # --- Translate world coordinates to local image coordinates ---
                    target_world_w = comp.world_x2 - comp.world_x1
                    target_world_h = comp.world_y2 - comp.world_y1
                    if target_world_w == 0 or target_world_h == 0: continue

                    scale_x = comp.pil_image.width / target_world_w
                    scale_y = comp.pil_image.height / target_world_h

                    local_x1 = (last_world_x - comp.world_x1) * scale_x
                    local_y1 = (last_world_y - comp.world_y1) * scale_y
                    local_x2 = (world_x - comp.world_x1) * scale_x
                    local_y2 = (world_y - comp.world_y1) * scale_y

                    # Draw a transparent line on the component's image
                    draw = ImageDraw.Draw(comp.pil_image)
                    draw.line((local_x1, local_y1, local_x2, local_y2),
                              fill=(0, 0, 0, 0), # RGBA transparent
                              width=int(brush_size * scale_x), # Scale brush size
                              joint='curve')

                    # Force the component to update its visual on the canvas
                    comp.set_image(comp.pil_image)

        self.last_paint_x, self.last_paint_y = event.x, event.y