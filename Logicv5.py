import pyautogui
import pytesseract
import uiautomation as auto
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import time
import os

# --- Config ---
GRID_SIZE = 50
LastGrid = []

# --- Screenshot + Vision ---
def capture_screenshot(path='screenshot.png'):
    pyautogui.screenshot(path)
    return path

def ocr_image(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    text = pytesseract.image_to_string(gray)
    return text

# --- Grid Overlay ---
def overlay_grid(image_path):
    global LastGrid
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    
    font = ImageFont.load_default()
    cell_index = 0
    LastGrid = []
    for y in range(0, h, GRID_SIZE):
        for x in range(0, w, GRID_SIZE):
            center_x = x + GRID_SIZE // 2
            center_y = y + GRID_SIZE // 2
            LastGrid.append((center_x, center_y))
            draw.text((center_x-5, center_y-5), str(cell_index), fill=(255,255,255,255), font=font)
    combined = Image.alpha_composite(img, overlay)
    output_path = "grid_overlay.png"
    combined.save(output_path)
    return output_path

# --- Grid Click Fallback ---
def click_grid(index):
    try:
        x, y = LastGrid[index]
        pyautogui.moveTo(x, y)
        pyautogui.click()
        return f"Clicked grid cell {index} at ({x},{y})"
    except:
        return "Grid index out of range"

# --- UI Automation ---
def find_ui_elements_by_name(name):
    matches = []
    desktop = auto.GetRootControl()
    for ctrl, _ in desktop.GetChildren():
        if name.lower() in ctrl.Name.lower():
            matches.append(ctrl)
    return matches

def click_ui_element_by_name(name):
    matches = find_ui_elements_by_name(name)
    if matches:
        ctrl = matches[0]
        rect = ctrl.BoundingRectangle
        x = (rect.left + rect.right) // 2
        y = (rect.top + rect.bottom) // 2
        pyautogui.moveTo(x, y)
        pyautogui.click()
        return f"Clicked UI element '{name}' at ({x},{y})"
    else:
        return f"No UI element found with name: {name}"

# --- General Actions ---
def type_text(text):
    pyautogui.write(text, interval=0.03)

def press_key(key):
    pyautogui.press(key)

def ask_user(prompt):
    return input(f"[USER INPUT NEEDED] {prompt}\n> ")

# --- Main Task Handler ---
def run_task_loop():
    print("ScreenPilot v5 ready. Type tasks like 'open Chrome and search YouTube'. Type 'exit' to quit.")
    while True:
        user_task = input("\nEnter a screen task: ").strip()
        if user_task.lower() == 'exit':
            print("Exiting...")
            break

        # Step 1: Try automation
        action_words = user_task.lower().split()
        did_action = False
        for word in action_words:
            print(f"Trying UI automation for '{word}'...")
            result = click_ui_element_by_name(word)
            if "Clicked" in result:
                print(result)
                did_action = True
                break

        # Step 2: If that fails, do OCR vision
        if not did_action:
            print("Trying OCR fallback...")
            path = capture_screenshot()
            text = ocr_image(path)
            print("OCR saw:", text[:200])

        # Step 3: Ask user for grid fallback
        if not did_action:
            overlay_path = overlay_grid(path)
            print(f"Fallback: See image {overlay_path} and tell me the number to click.")
            idx = ask_user("What grid cell should I click?")
            try:
                idx = int(idx)
                print(click_grid(idx))
            except:
                print("Invalid index. Skipping.")

# Run
if __name__ == "__main__":
    run_task_loop()