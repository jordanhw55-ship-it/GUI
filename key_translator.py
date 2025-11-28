import re

def normalize_to_canonical(raw_key: str, is_capturing_numpad: bool = False) -> str:
    """
    Normalizes a raw key name from the 'keyboard' library into the canonical internal format.
    The canonical format is "numpad {digit}" (lowercase, with a space).

    Examples:
      "num 7" -> "numpad 7"
      "7_num" -> "numpad 7"
      "numpad 7" -> "7"
    """
    if not raw_key:
        return ""
    
    key_lower = raw_key.lower().strip()
    
    # Check for various numpad formats and extract the digit
    if key_lower.startswith("num") or key_lower.endswith("_num"):
        digit = ''.join(filter(str.isdigit, key_lower))
        if digit:
            return digit

    # If a single digit is captured AND we know it's for a numpad button
    if key_lower.isdigit() and len(key_lower) == 1 and is_capturing_numpad:
        return key_lower

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
    For AHK hotkey definition.
    Canonical 'numpad 7' -> 'numpad7'
    Canonical '7' -> 'numpad7'
    """
    return canonical.replace(" ", "")
    if canonical.isdigit() and len(canonical) == 1:
        return f"numpad{canonical}"
    return canonical.replace(" ", "")

def to_ahk_send(key_name: str) -> str:
    """
    Translates a key name into the format required for an AutoHotkey SendInput command.
    '7' -> 'Numpad7'
    """
    if key_name.isdigit() and len(key_name) == 1:
        return f"Numpad{key_name}"
    return key_name.title().replace(" ", "")

def to_pyautogui(canonical: str) -> str:
    """
    Translates the canonical format to the format required by the 'pyautogui' library.
    Canonical '7' -> 'num7'.
    """
    if canonical.isdigit() and len(canonical) == 1:
        return f"num{canonical}"
    return canonical