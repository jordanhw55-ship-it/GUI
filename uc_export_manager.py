import os
import subprocess
from tkinter import messagebox
from PIL import Image

class ExportManager:
    """Manages all logic related to exporting final images."""
    def __init__(self, app):
        self.app = app

    def export_images(self, export_format):
        """Generic export function to save modified layers as either PNG or DDS."""
        print("-" * 30)
        print(f"Starting export process for {export_format.upper()}...")
        if export_format not in ['png', 'dds']:
            messagebox.showerror("Export Error", f"Unsupported export format: {export_format}")
            return

        save_dir = os.path.join(self.app.output_dir, f"export_{export_format}")
        os.makedirs(save_dir, exist_ok=True)

        exported_count = 0

        # Pre-calculate which borders belong to which tiles
        borders_by_parent = {}
        for comp in self.app.components.values():
            if comp.tag.startswith("preset_border_") and comp.parent_tag:
                parent_tag = comp.parent_tag
                if parent_tag not in borders_by_parent:
                    borders_by_parent[parent_tag] = []
                borders_by_parent[parent_tag].append(comp)

        for tag, comp in self.app.components.items():
            # We only export primary tiles, not assets, clones, or the borders themselves.
            if not comp.pil_image or comp.is_dock_asset or tag.startswith("clone_") or tag.startswith("preset_border_"):
                continue

            final_image = comp.pil_image.copy()
            has_borders = False

            # Conditionally skip unmodified tiles based on UI checkbox
            if not self.app.export_all_tiles.get():
                is_modified = (comp.original_pil_image is not None and not self.app.image_manager._are_images_identical(comp.pil_image, comp.original_pil_image))
                if not is_modified and tag not in borders_by_parent:
                    continue

            # Composite any borders onto the final image
            if tag in borders_by_parent:
                for border_comp in borders_by_parent[tag]:
                    final_image, has_borders = self.app.image_manager._composite_border_onto_image(final_image, comp, border_comp)

            save_path = os.path.join(save_dir, f"{tag}.{export_format}")
            try:
                if export_format == 'dds':
                    texconv_path = os.path.join(self.app.tools_dir, "texconv.exe")
                    if not os.path.exists(texconv_path):
                        messagebox.showerror("DDS Export Error", f"texconv.exe not found at:\n{texconv_path}")
                        return

                    temp_png_path = os.path.join(save_dir, f"{tag}.png")
                    final_image.save(temp_png_path, format='PNG')

                    command = [texconv_path, "-f", "BC3_UNORM", "-o", save_dir, "-y", temp_png_path]
                    result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

                    if result.returncode != 0:
                        error_message = f"texconv.exe failed.\nSTDOUT:\n{result.stdout.strip()}\n\nSTDERR:\n{result.stderr.strip()}"
                        raise RuntimeError(error_message)
                    os.remove(temp_png_path)
                else:
                    final_image.save(save_path)

                exported_count += 1
                print(f"Saved modified image to: {save_path}")
            except (Exception, RuntimeError) as e:
                messagebox.showerror("DDS Export Error", f"Could not save '{os.path.basename(save_path)}'.\n\nDetails:\n{e}")

        if exported_count > 0:
            messagebox.showinfo("Export Complete", f"Successfully exported {exported_count} modified files.")
        else:
            messagebox.showinfo("Export Info", "No modified layers found to export.")

    def open_export_folder(self, export_format: str):
        """Opens the specified export folder."""
        folder_path = os.path.join(self.app.output_dir, f"export_{export_format}")
        if not os.path.isdir(folder_path):
            messagebox.showinfo("Folder Not Found", "The export folder does not exist yet. Please export images first.")
            return
        try:
            if os.name == 'nt':
                os.startfile(folder_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")