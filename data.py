import os
import re

from utils import get_base_path

class ItemDatabase:
    """Handles loading and searching item data from text files."""
    def __init__(self):
        self.contents_base_path = os.path.join(get_base_path(), "contents")
        self.items_base_path = os.path.join(self.contents_base_path, "Items")
        self.all_items_data = []
        self.drops_data = []
        self.raid_data = []
        self.vendor_data = []
        self.recipes_data = []

    def _clean_item(self, raw_line: str) -> dict:
        line = raw_line.strip()
        if not line:
            return {}
        patterns = [
            r"^\s*\[([^\]]+)\]\s*(.+?)\s*[:\-]\s*([\d\.]+)%\s*$",
            r"^\s*\[([^\]]+)\]\s*(.+)$",
            r"^\s*(.+?)\s*[:\-]\s*([\d\.]+)%\s*$",
        ]
        for i, pattern in enumerate(patterns):
            match = re.match(pattern, line)
            if match:
                if i == 0: return {"type": match.group(1), "name": match.group(2).strip(), "rate": f"{match.group(3)}%"}
                if i == 1: return {"type": match.group(1), "name": match.group(2).strip(), "rate": ""}
                if i == 2: return {"name": match.group(1).strip(), "rate": f"{match.group(2)}%"}
        return {"name": line, "rate": ""}

    def _load_item_data_from_folder(self, folder: str) -> list:
        data = []
        folder_path = os.path.join(self.items_base_path, folder)
        if not os.path.isdir(folder_path):
            return []
        for filename in os.listdir(folder_path):
            if not filename.endswith(".txt"):
                continue
            file_path = os.path.join(folder_path, filename)
            zone = os.path.splitext(filename)[0]
            unit = "?"
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for raw in f:
                        line = raw.strip()
                        if not line:
                            continue
                        zone_match = re.match(r"^Zone:\s*(.+)", line)
                        unit_match = re.match(r"^\[Unit\]\s*(.+)", line)
                        if zone_match:
                            zone = zone_match.group(1).strip()
                        elif unit_match:
                            unit = unit_match.group(1).strip()
                        else:
                            item_obj = self._clean_item(line)
                            if item_obj.get("name"):
                                data.append({
                                    "Item": item_obj["name"],
                                    "Drop%": item_obj.get("rate", ""),
                                    "Unit": unit,
                                    "Location": zone
                                })
            except (IOError, OSError):
                continue
        return data

    def load_recipes(self):
        if self.recipes_data:
            return
        file_path = os.path.join(self.items_base_path, "Recipes.txt")
        if not os.path.exists(file_path):
            return
        self.recipes_data = []
        current_recipe_name = ""
        current_components = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        if current_recipe_name:
                            self.recipes_data.append({"name": current_recipe_name, "components": current_components})
                            current_recipe_name = ""
                            current_components = []
                        continue
                    material_match = re.match(r"^\s*Material\s*:\s*(.+)", line, re.IGNORECASE)
                    if material_match:
                        if current_recipe_name:
                            current_components.append(material_match.group(1).strip())
                    else:
                        if current_recipe_name:
                            self.recipes_data.append({"name": current_recipe_name, "components": current_components})
                        current_recipe_name = line
                        current_components = []
            if current_recipe_name:
                self.recipes_data.append({"name": current_recipe_name, "components": current_components})
        except (IOError, OSError):
            print(f"Could not read {file_path}")