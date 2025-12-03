import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os

class DraggableComponent:
    """
    A class to represent and manage an independent, draggable element 
    on the Tkinter canvas, now supporting real images with transparency.
    """
    def __init__(self, canvas, app_instance, tag, x1, y1, x2, y2, color, text, is_dock_asset=False):
        self.canvas = canvas
        self.app = app_instance # Reference to the main app
        self.tag = tag
        self.last_x = 0
        self.last_y = 0
        self.tk_image = None # Reference to the PhotoImage object
        self.preview_pil_image = None # For dock previews
        self.pil_image = None # Reference to the PIL Image object
        self.border_pil_image = None # For storing the border image
        self.original_pil_image = None # For storing the pristine decal image
        self.rect_id = None
        self.text_id = None
        self.is_draggable = True # Control whether the component can be dragged
        self.is_decal = False # To identify temporary decals
        self.is_border_asset = False # To identify border assets
        
        # Caching for Performance
        self._cached_screen_w = -1
        self._cached_screen_h = -1

        self.is_dock_asset = is_dock_asset # To identify dock assets
        # Initialize with the colored box
        self._draw_placeholder(x1, y1, x2, y2, color, text)
        
        self.canvas.tag_bind(self.tag, '<Button-1>', self.on_press)
        self.canvas.tag_bind(self.tag, '<B1-Motion>', self.on_drag)
        self.canvas.tag_bind(self.tag, '<ButtonRelease-1>', self.on_release)

    def _draw_placeholder(self, x1, y1, x2, y2, color, text):
        """Draws the initial colored rectangle and text."""
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)

        self.rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, 
                                                     fill=color, 
                                                     outline='white',
                                                     width=2)
        
        self.text_id = self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, 
                                              text=text, 
                                              fill="white", 
                                              font=("Inter", 16, "bold"),
                                              tags=(self.tag, "draggable"))
        
        tags_to_add = [self.tag, "draggable"]
        if not self.is_dock_asset:
            tags_to_add.append("zoom_target")
        self.canvas.addtag_withtag(tags_to_add[0], self.rect_id)
        for t in tags_to_add[1:]:
            self.canvas.addtag_withtag(t, self.rect_id)
        self.world_x1, self.world_y1, self.world_x2, self.world_y2 = x1, y1, x2, y2


    def set_image_from_path(self, image_path):
        """Loads an image from a file path and applies it to the component."""
        try:
            pil_image = Image.open(image_path).convert("RGBA")
            self._set_pil_image(pil_image)
            print(f"Image loaded for {self.tag}: {os.path.basename(image_path)}")
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not load image: {e}")

    def _set_pil_image(self, pil_image, resize_to_fit=True):
        """Core logic to apply a PIL image to this component."""
        self.pil_image = pil_image
        
        if self.border_pil_image:
            pil_image = self._composite_border(pil_image)

        x_start, y_start = self.app.camera.world_to_screen(self.world_x1, self.world_y1)

        if resize_to_fit:
            image_to_render = self.preview_pil_image if self.is_dock_asset else self.pil_image
            w, h = int(self.world_x2 - self.world_x1), int(self.world_y2 - self.world_y1)
            image_to_render = image_to_render.resize((w, h), Image.Resampling.LANCZOS) if w > 0 and h > 0 else image_to_render
        else:
            image_to_render = self.pil_image

        new_tk_image = ImageTk.PhotoImage(image_to_render)

        self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)
            self.text_id = None

        self.rect_id = self.canvas.create_image(x_start, y_start,
                                                 image=new_tk_image,
                                                 anchor=tk.NW,
                                                 tags=(self.tag, "draggable"))
        if not self.is_dock_asset:
            self.canvas.addtag_withtag("zoom_target", self.rect_id)

        self.tk_image = new_tk_image

    def set_border_image(self, border_image_path):
        """Loads and applies a border image from a file path."""
        if not self.pil_image:
            messagebox.showwarning("No Content", "Please apply a main image to the tile before adding a border.")
            return

        try:
            self.border_pil_image = Image.open(border_image_path).convert("RGBA")
            self._set_pil_image(self.pil_image)
            print(f"Border '{os.path.basename(border_image_path)}' applied to {self.tag}")
        except Exception as e:
            messagebox.showerror("Border Error", f"Could not load border image: {e}")

    def remove_border(self):
        """Removes the border and redraws the component."""
        if self.border_pil_image:
            self.border_pil_image = None
            self._set_pil_image(self.pil_image)
            print(f"Border removed from {self.tag}")

    def _composite_border(self, base_image):
        """Composites the border image on top of the base image."""
        if not self.border_pil_image:
            return base_image
        border_resized = self.border_pil_image.resize(base_image.size, Image.Resampling.LANCZOS)
        return Image.alpha_composite(base_image.copy(), border_resized)

    def on_press(self, event):
        """Records the starting position and brings the element to the front."""
        if self.is_dock_asset:
            bbox = self.canvas.bbox(self.rect_id)
            if not bbox: return

            if not (bbox[0] <= event.x <= bbox[2] and bbox[1] <= event.y <= bbox[3]):
                return

            rel_x = int(event.x - bbox[0])
            rel_y = int(event.y - bbox[1])

            try:
                alpha = (self.preview_pil_image or self.original_pil_image).getpixel((rel_x, rel_y))[3]
                if alpha > 10:
                    self.app.create_clone_from_asset(self, event)
            except (IndexError, TypeError):
                pass
            return

        self.last_x = event.x
        self.last_y = event.y
        
        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)
        print(f"[DEBUG] Pressed '{self.tag}' | Screen: ({event.x}, {event.y}) | World: ({int(world_x)}, {int(world_y)})")

        self.canvas.tag_raise(self.rect_id)
        if self.text_id:
            self.canvas.tag_raise(self.text_id)

    def on_drag(self, event):
        """Calculates the distance moved and updates the element's position."""
        """Calculates the distance moved and updates the element's position."""
        if not self.is_draggable or (self.app.is_group_dragging and not self.is_decal) or self.is_dock_asset:
            return

        dx_world = (event.x - self.last_x) / self.app.camera.zoom_scale
        dy_world = (event.y - self.last_y) / self.app.camera.zoom_scale

        if not self.is_decal:
            new_world_x1 = self.world_x1 + dx_world
            new_world_y1 = self.world_y1 + dy_world

            bounds = self.app
            tile_w_world = self.world_x2 - self.world_x1
            tile_h_world = self.world_y2 - self.world_y1

            if new_world_x1 < bounds.COMP_AREA_X1: new_world_x1 = bounds.COMP_AREA_X1
            if new_world_x1 + tile_w_world > bounds.COMP_AREA_X2: new_world_x1 = bounds.COMP_AREA_X2 - tile_w_world
            if new_world_y1 < bounds.COMP_AREA_Y1: new_world_y1 = bounds.COMP_AREA_Y1
            if new_world_y1 + tile_h_world > bounds.COMP_AREA_Y2: new_world_y1 = bounds.COMP_AREA_Y2 - tile_h_world

            self.world_x1, self.world_y1 = new_world_x1, new_world_y1
            self.world_x2, self.world_y2 = new_world_x1 + tile_w_world, new_world_y1 + tile_h_world
        else:
            self.world_x1 += dx_world; self.world_y1 += dy_world
            self.world_x2 += dx_world; self.world_y2 += dy_world
        
        self.last_x = event.x
        self.last_y = event.y
        
        # This can be very verbose, so it's commented out. Uncomment for detailed drag logging.
        # print(f"[DEBUG] Dragging '{self.tag}' to world coords ({int(self.world_x1)}, {int(self.world_y1)})")

        self.app.redraw_all_zoomable()

    def on_release(self, event):
        """Action after drag finishes."""
        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)
        print(f"[DEBUG] Released '{self.tag}' | Screen: ({event.x}, {event.y}) | New World TL: ({int(self.world_x1)}, {int(self.world_y1)})")
        self.app._keep_docks_on_top()

    def select(self, app_instance):
        """Simulate selecting this component in the sidebar and update app state."""
        app_instance.set_selected_component(self.tag)
        
        for comp in app_instance.components.values():
            if comp.rect_id and comp.tk_image is None:
                 self.canvas.itemconfig(comp.rect_id, outline='white', width=2)
        
        if self.tk_image is None:
            self.canvas.itemconfig(self.rect_id, outline='yellow', width=3)
        
        print(f"[ACTION] Component '{self.tag}' selected via sidebar.")