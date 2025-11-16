import time
import uiautomation as auto
import pyautogui
from PIL import Image, ImageDraw

# CONFIG
SCAN_FOREGROUND_ONLY = True  # True = just the active window, False = whole desktop
MAX_DEPTH = 100000               # higher = deeper scan, but slower

# Dynamically include EVERY ControlType that ends with "Control"
CLICKABLE_CONTROL_TYPES = {
    value
    for name, value in auto.ControlType.__dict__.items()
    if name.endswith("Control")
}

print("Number of ControlTypes in CLICKABLE_CONTROL_TYPES:", len(CLICKABLE_CONTROL_TYPES))


def is_clickable(elem: auto.Control):
    """
    Treat basically everything as clickable if:
    - it has a valid visible bounding rect, AND
    - its control type is ANY ControlType (we added them all), OR
    - it has Invoke/Selection/ExpandCollapse/Toggle patterns, OR
    - UIA says it has a clickable point
    """
    try:
        rect = elem.BoundingRectangle
    except Exception:
        return False

    if not rect or rect.width() <= 0 or rect.height() <= 0:
        return False

    try:
        if not elem.IsEnabled:
            return False
        if elem.IsOffscreen:
            return False
    except Exception:
        return False

    # Now: *any* control type that exists in ControlType is considered clickable
    if elem.ControlType in CLICKABLE_CONTROL_TYPES:
        return True

    # Pattern-based checks
    def has_pattern(getter_name: str) -> bool:
        try:
            pat = getattr(elem, getter_name)()
            return pat is not None
        except Exception:
            return False

    if (
        has_pattern("GetInvokePattern")
        or has_pattern("GetSelectionItemPattern")
        or has_pattern("GetExpandCollapsePattern")
        or has_pattern("GetTogglePattern")
    ):
        return True

    # Fallback: if UIA can give us a clickable point, call it clickable
    try:
        elem.GetClickablePoint()
        return True
    except Exception:
        pass

    return False


def walk_and_collect(root: auto.Control, depth=0, max_depth=5, results=None):
    if results is None:
        results = []

    if depth > max_depth:
        return results

    for child in root.GetChildren():
        try:
            if is_clickable(child):
                rect = child.BoundingRectangle
                item = {
                    "name": child.Name,
                    "control_type": child.ControlTypeName,
                    "x1": rect.left,
                    "y1": rect.top,
                    "x2": rect.right,
                    "y2": rect.bottom,
                    "width": rect.width(),
                    "height": rect.height(),
                    "automation_id": child.AutomationId,
                    "class_name": child.ClassName,
                }
                results.append(item)

            walk_and_collect(child, depth + 1, max_depth, results)
        except Exception:
            continue

    return results


if __name__ == "__main__":
    print("You have 2 seconds to arrange the screen / active window...")
    time.sleep(2)

    if SCAN_FOREGROUND_ONLY:
        root = auto.GetForegroundControl()
        print("Scanning active window:", root.Name, "| Class:", root.ClassName)
    else:
        root = auto.GetRootControl()
        print("Scanning entire desktop")

    clickable_items = walk_and_collect(root, max_depth=MAX_DEPTH)

    # Print list
    for i, item in enumerate(clickable_items, start=1):
        print(f"[{i}] {item['control_type']}  '{item['name']}'")
        print(f"    Rect: ({item['x1']}, {item['y1']}) -> ({item['x2']}, {item['y2']})"
              f"  size=({item['width']}x{item['height']})")
        print(f"    Class='{item['class_name']}'  AutomationId='{item['automation_id']}'")
        print()
    print(f"Total clickable-ish items found: {len(clickable_items)}")

    # Screenshot + overlay
    screenshot = pyautogui.screenshot()
    screenshot = screenshot.convert("RGB")
    draw = ImageDraw.Draw(screenshot)

    img_w, img_h = screenshot.size

    for item in clickable_items:
        x1 = int(item["x1"])
        y1 = int(item["y1"])
        x2 = int(item["x2"])
        y2 = int(item["y2"])

        # Clamp to screenshot bounds
        x1 = max(0, min(x1, img_w - 1))
        y1 = max(0, min(y1, img_h - 1))
        x2 = max(0, min(x2, img_w - 1))
        y2 = max(0, min(y2, img_h - 1))

        if x2 <= x1 or y2 <= y1:
            continue

        draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=2)

    out_path = "clickables_overlay.png"
    screenshot.save(out_path)
    print(f"Overlay screenshot saved to: {out_path}")
