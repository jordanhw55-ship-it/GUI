import re

def normalize_to_canonical(raw_key: str) -> str:
    """
    Normalizes a raw key name from the 'keyboard' library into the canonical internal format.
    The canonical format is "numpad {digit}" (lowercase, with a space).

    Examples:
      "num 7" -> "numpad 7"
      "7_num" -> "numpad 7"
      "7"     -> "numpad 7" (if it's a single digit)
      "numpad 7" -> "numpad 7" (already canonical)
    """
    if not raw_key:
        return ""
    
    key_lower = raw_key.lower().strip()
    
    # Extract digit from various numpad formats
    if key_lower.startswith("num ") or key_lower.endswith("_num") or key_lower.startswith("numpad"):
        digit = ''.join(filter(str.isdigit, key_lower))
        if digit:
            return f"numpad {digit}"

    # Handle single-digit captures for numpad keys
    if key_lower.isdigit() and len(key_lower) == 1:
        return f"numpad {key_lower}"

    # Return the key as is if it's not a recognized numpad format
    return key_lower

def to_keyboard_lib(canonical: str) -> str:
    """
    Translates the canonical format to the format required by the 'keyboard' library for registration.
    Canonical 'numpad 7' -> 'numpad 7' (identity function).
    """
    return canonical

def to_ahk_hotkey(canonical: str) -> str:
    """
    Translates the canonical format to the format required for an AutoHotkey hotkey definition.
    Canonical 'numpad 7' -> 'numpad7' (lowercase, no space).
    """
    return canonical.replace(" ", "")

def to_ahk_send(key_name: str) -> str:
    """
    Translates a key name into the format required for an AutoHotkey SendInput command.
    'numpad 7' -> 'Numpad7'
    'Numpad7'  -> 'Numpad7'
    """
    return key_name.title().replace(" ", "")

def to_pyautogui(canonical: str) -> str:
    """
    Translates the canonical format to the format required by the 'pyautogui' library.
    Canonical 'numpad 7' -> 'num7'.
    """
    return canonical.replace("numpad ", "num")