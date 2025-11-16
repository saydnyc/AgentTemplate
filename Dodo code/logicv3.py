import os
import time
import json
import base64
from io import BytesIO
from datetime import datetime

import pyautogui
from PIL import Image, ImageDraw, ImageFont

from openai import OpenAI

# =====================
# Basic setup
# =====================

# Fail-safe: moving mouse to TOP-LEFT corner aborts pyautogui
pyautogui.FAILSAFE = True

GRID_CELL_SIZE = 50  # pixels for the numbered grid overlay

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Please set the OPENAI_API_KEY environment variable (your OpenAI API key).")

client = OpenAI(api_key=api_key)

# =====================
# Grid overlay helper
# =====================

def _overlay_numbered_grid(img: Image.Image, cell_size: int = GRID_CELL_SIZE) -> Image.Image:
    """
    Overlay a semi-transparent grid and cell index numbers over the screenshot,
    so the vision model can refer to numbered cells.

    Cell indexing:
      - Top-left cell is index 0
      - Increase left-to-right, then top-to-bottom (row-major)
      - Each cell is cell_size x cell_size pixels
    """
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    line_color = (255, 255, 255, 80)
    text_color = (255, 255, 255, 160)
    line_width = 1
    font_size = 18

    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # Draw grid lines
    for x in range(0, w, cell_size):
        draw.line((x, 0, x, h), fill=line_color, width=line_width)
    for y in range(0, h, cell_size):
        draw.line((0, y, w, y), fill=line_color, width=line_width)

    # Draw cell indices
    cell_index = 0
    for y in range(0, h, cell_size):
        for x in range(0, w, cell_size):
            center_x = x + cell_size // 2
            center_y = y + cell_size // 2
            text = str(cell_index)

            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            draw.text(
                (center_x - tw / 2, center_y - th / 2),
                text,
                fill=text_color,
                font=font,
            )

            cell_index += 1

    # Composite overlay on top of original screenshot
    if img.mode != "RGBA":
        base = img.convert("RGBA")
    else:
        base = img
    result = Image.alpha_composite(base, overlay)
    return result

# =====================
# Screenshot helpers
# =====================

def _take_screenshot():
    """
    Take a screenshot of the full screen, overlay a numbered grid, and
    return its path and base64-encoded PNG.

    Returns:
        path: str - file path to PNG
        width: int
        height: int
        b64: str - base64-encoded PNG (with grid overlay)
    """
    ts = int(time.time())
    filename = f"screen_{ts}.png"

    raw_img = pyautogui.screenshot()
    w, h = raw_img.size

    img_with_grid = _overlay_numbered_grid(raw_img, GRID_CELL_SIZE)
    img_with_grid.save(filename, "PNG")

    buffer = BytesIO()
    img_with_grid.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return filename, w, h, b64

# =====================
# Vision / screen summarizer tool
# =====================

def capture_and_describe_screen(task_hint: str | None = None,
                                grid_rows: int = 3,
                                grid_cols: int = 3):
    """
    Core vision tool.

    1. Takes a screenshot and overlays a numbered grid (50px cells).
    2. Sends it to a mini model with instructions to:
       - Describe the screen.
       - Detect important UI elements.
       - Map them into a logical grid (rows x cols) AND
         also, when possible, into a numbered-grid index.
    3. Returns structured JSON the main agent can reason over.

    Uses model: gpt-4.1-mini
    """
    path, w, h, b64 = _take_screenshot()
    img_url = f"data:image/png;base64,{b64}"

    task_text = task_hint or "No specific task provided; describe the screen in a useful way."

    system_msg = (
        "You are ScreenSummarizer, a helper for another agent that will control the computer.\n"
        "You receive: (1) the user's current task in words, and (2) a screenshot of the whole screen, "
        "with a semi-transparent numbered grid overlay.\n\n"
        "GRID DETAILS:\n"
        "- Each grid cell is 50x50 pixels.\n"
        "- Cells are numbered in row-major order (left-to-right, then top-to-bottom).\n"
        "- Top-left cell index is 0.\n"
        "- The overlaid numbers you see correspond to this index.\n\n"
        "You also receive a logical grid size: grid_rows x grid_cols, which is separate from the 50px numbered grid.\n"
        "Your job: return a single JSON object with keys:\n"
        "{\n"
        '  \"summary\": string,\n'
        '  \"notable_ui\": [\n'
        "    {\n"
        '      \"id\": string,\n'
        '      \"role\": string,\n'
        '      \"label\": string,\n'
        '      \"approx_grid_cell\": [r, c],\n'
        '      \"numbered_cell_index\": integer (optional, if you can read the 50px grid index),\n'
        '      \"notes\": string\n'
        "    }, ...\n"
        "  ],\n"
        '  \"ocr_text_snippets\": [string, ...],\n'
        '  \"suggested_next_actions\": [string, ...]\n'
        "}\n\n"
        "Define the logical grid as:\n"
        "- The visible screen is divided into grid_rows x grid_cols.\n"
        "- Top-left corner is cell [0,0]. Bottom-right is [grid_rows-1, grid_cols-1].\n"
        "- For each notable UI element, estimate which logical grid cell its center is in.\n\n"
        "If you can see the cell number text from the 50px grid overlay where an element sits, "
        "include \"numbered_cell_index\" in that element.\n\n"
        "Be concise but informative. DO NOT include any comments outside the JSON. "
        "Return strictly valid JSON."
    )

    user_content = [
        {
            "type": "text",
            "text": (
                f"User task: {task_text}\n"
                f"Logical grid size: rows={grid_rows}, cols={grid_cols}.\n"
                "Now analyze the screenshot (with numbered grid) and respond with the JSON described in the system message."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": img_url},
        },
    ]

    try:
        mini_completion = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
        content = mini_completion.choices[0].message.content
        parsed = json.loads(content)
    except Exception as e:
        parsed = {
            "error": f"screen_summarizer_failed: {str(e)}",
            "summary": "Error summarizing screen.",
            "notable_ui": [],
            "ocr_text_snippets": [],
            "suggested_next_actions": [],
        }

    parsed["_meta"] = {
        "screenshot_path": path,
        "viewport": {"width": w, "height": h},
        "grid": {"rows": grid_rows, "cols": grid_cols},
        "numbered_grid": {"cell_size_pixels": GRID_CELL_SIZE},
    }

    return parsed


def raw_screenshot():
    """
    Simple screenshot tool: just capture (with grid overlay) and return basic info.
    """
    path, w, h, _ = _take_screenshot()
    return {
        "status": "ok",
        "path": path,
        "width": w,
        "height": h,
    }

# =====================
# Control tools (mouse / keyboard)
# =====================

def move_mouse(x: int, y: int, duration: float = 0.0):
    """
    Move mouse to absolute screen coordinates (x, y).
    """
    pyautogui.moveTo(x, y, duration=duration)
    return {"status": "ok", "x": x, "y": y, "duration": duration}


def click(x: int | None = None, y: int | None = None, button: str = "left",
          clicks: int = 1, interval: float = 0.0):
    """
    Click at (x, y) if given, else at current position.
    """
    if x is not None and y is not None:
        pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)
    else:
        pyautogui.click(clicks=clicks, interval=interval, button=button)
    return {
        "status": "ok",
        "x": x,
        "y": y,
        "button": button,
        "clicks": clicks,
        "interval": interval,
    }


def double_click(x: int | None = None, y: int | None = None, button: str = "left"):
    """
    Double-click at the CURRENT mouse position.

    NOTE: We intentionally ignore x, y to avoid the model trying to move to
    (0, 0) and triggering the PyAutoGUI failsafe corner.
    """
    pyautogui.click(clicks=2, interval=0.1, button=button)
    return {
        "status": "ok",
        "x": None,
        "y": None,
        "button": button,
        "clicks": 2,
        "interval": 0.1,
        "note": "double-clicked at current mouse position; x,y arguments are ignored for safety.",
    }


def click_grid_cell(row: int,
                    col: int,
                    rows: int,
                    cols: int,
                    x_offset: float = 0.0,
                    y_offset: float = 0.0,
                    button: str = "left"):
    """
    Click approximately in the center of a logical grid cell (row, col).

    - rows, cols: total grid dimensions used in capture_and_describe_screen.
    - x_offset, y_offset: relative offset from center in range [-0.5, +0.5] of cell size.
    """
    screen_w, screen_h = pyautogui.size()

    cell_w = screen_w / cols
    cell_h = screen_h / rows

    center_x = (col + 0.5) * cell_w
    center_y = (row + 0.5) * cell_h

    x = int(center_x + x_offset * cell_w)
    y = int(center_y + y_offset * cell_h)

    pyautogui.click(x=x, y=y, button=button)
    return {
        "status": "ok",
        "row": row,
        "col": col,
        "rows": rows,
        "cols": cols,
        "x": x,
        "y": y,
        "button": button,
    }


def click_numbered_cell(index: int,
                        button: str = "left",
                        clicks: int = 2,
                        interval: float = 0.1):
    """
    Click roughly the center of a numbered 50x50 grid cell.

    - index: 0-based cell index as drawn on the overlay (row-major).
    """
    screen_w, screen_h = pyautogui.size()
    cells_per_row = screen_w // GRID_CELL_SIZE
    rows = screen_h // GRID_CELL_SIZE
    total_cells = cells_per_row * rows

    if index < 0 or index >= total_cells:
        return {
            "error": f"index {index} out of range for screen grid",
            "cells_per_row": cells_per_row,
            "rows": rows,
            "total_cells": total_cells,
        }

    row = index // cells_per_row
    col = index % cells_per_row

    x = col * GRID_CELL_SIZE + GRID_CELL_SIZE // 2
    y = row * GRID_CELL_SIZE + GRID_CELL_SIZE // 2

    pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)

    return {
        "status": "ok",
        "index": index,
        "row": row,
        "col": col,
        "x": x,
        "y": y,
        "button": button,
        "clicks": clicks,
        "interval": interval,
    }


def type_text(text: str, interval: float = 0.02):
    """
    Type text at current focus.
    """
    pyautogui.write(text, interval=interval)
    return {"status": "ok", "text_length": len(text), "interval": interval}


def press_key(key: str):
    """
    Press a single key (e.g. 'enter', 'tab', 'esc', 'f5').
    """
    pyautogui.press(key)
    return {"status": "ok", "key": key}


def hotkey(keys: list[str]):
    """
    Press a combination as a hotkey, e.g. ['ctrl', 'l'] or ['win', 's'].
    """
    pyautogui.hotkey(*keys)
    return {"status": "hotkey", "keys": keys}


def sleep(seconds: float):
    """
    Pause execution (to wait for UI updates).

    IMPORTANT:
    - Prefer short sleeps (0.3–1.0s) and then RE-CHECK the screen.
    - Only use longer sleeps if absolutely necessary (e.g. 2–3s for heavy loads).
    """
    time.sleep(seconds)
    return {"status": "slept", "seconds": seconds}

# =====================
# Tool registry for the agent
# =====================

TOOL_IMPLS = {
    "raw_screenshot": raw_screenshot,
    "capture_and_describe_screen": capture_and_describe_screen,
    "move_mouse": move_mouse,
    "click": click,
    "double_click": double_click,
    "click_grid_cell": click_grid_cell,
    "click_numbered_cell": click_numbered_cell,
    "type_text": type_text,
    "press_key": press_key,
    "hotkey": hotkey,
    "sleep": sleep,
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "raw_screenshot",
            "description": "Take a screenshot of the full screen (with numbered grid overlay) and return basic info and path.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_and_describe_screen",
            "description": "Take a screenshot and return a structured JSON description with a logical grid, numbered grid indices, and notable UI elements.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_hint": {
                        "type": "string",
                        "description": "Short description of what you're trying to do, to help the vision model focus.",
                    },
                    "grid_rows": {
                        "type": "integer",
                        "description": "Number of rows in the logical grid.",
                        "default": 3,
                    },
                    "grid_cols": {
                        "type": "integer",
                        "description": "Number of columns in the logical grid.",
                        "default": 3,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse to an absolute (x, y) position on the screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "duration": {
                        "type": "number",
                        "description": "Optional smooth movement duration in seconds.",
                        "default": 0.0,
                    },
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click at a position (x, y) or at the current mouse location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "default": "left",
                    },
                    "clicks": {
                        "type": "integer",
                        "default": 1,
                    },
                    "interval": {
                        "type": "number",
                        "default": 0.0,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "double_click",
            "description": "Double-click at the current mouse location (ignores x,y for safety).",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "default": "left",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_grid_cell",
            "description": "Click roughly the center of a logical grid cell given row/col and total rows/cols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "row": {"type": "integer"},
                    "col": {"type": "integer"},
                    "rows": {"type": "integer"},
                    "cols": {"type": "integer"},
                    "x_offset": {
                        "type": "number",
                        "description": "Optional relative offset from center (-0.5 to 0.5).",
                        "default": 0.0,
                    },
                    "y_offset": {
                        "type": "number",
                        "description": "Optional relative offset from center (-0.5 to 0.5).",
                        "default": 0.0,
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "default": "left",
                    },
                },
                "required": ["row", "col", "rows", "cols"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_numbered_cell",
            "description": "Click roughly the center of a numbered 50x50 grid cell (index corresponds to grid overlay numbers).",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "default": "left",
                    },
                    "clicks": {
                        "type": "integer",
                        "default": 2,
                    },
                    "interval": {
                        "type": "number",
                        "default": 0.1,
                    },
                },
                "required": ["index"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text at the current focused input.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "interval": {
                        "type": "number",
                        "default": 0.02,
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a single key (e.g. 'enter', 'tab', 'esc').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                },
                "required": ["key"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Press a combination of keys (e.g. ['ctrl', 'l']).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["keys"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sleep",
            "description": "Pause for a number of seconds (prefer 0.3–1.0s, then re-check the screen).",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "default": 0.5,
                    },
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    },
]

# =====================
# System prompt for ScreenPilot v3
# =====================

SYSTEM_PROMPT = """
You are ScreenPilot v3, a vision-first automation agent.

You control the REAL computer using tools that:
- Take screenshots (with a 50px numbered grid overlay) and describe them via a helper model.
- Move and click the mouse (grid-based or absolute coordinates).
- Type text, press keys, and send hotkeys.
- Sleep to allow the UI to update.

GENERAL STRATEGY
- Treat the screen as a black box of pixels. You do NOT have DOM, internal app APIs, or direct site structure.
- On a new task, almost always:
  1) Call capture_and_describe_screen with a short task_hint describing what you're trying to do.
  2) Inspect the returned JSON:
     - 'summary': what is on screen
     - 'notable_ui': list of UI items with 'label', 'role', 'approx_grid_cell', and possibly 'numbered_cell_index'
     - '_meta.grid': the logical grid size you used
  3) Prefer using VISIBLE targets related to the task:
     - Example: if the task is "open Chrome", FIRST look in 'notable_ui' for labels like "Google Chrome" or a Chrome icon,
       and click that numbered cell.
  4) If a UI element has 'numbered_cell_index', use click_numbered_cell(index=...) as your primary way to click it.
  5) Otherwise, use click_grid_cell with its logical approx_grid_cell.

ACTION → SHORT WAIT → VERIFY LOOP
- After you do an action that should change the UI (typing, clicking, hotkey, navigation), follow this pattern:
  1) sleep for a SHORT time (0.3–1.0 seconds, not longer unless necessary),
  2) call capture_and_describe_screen with an appropriate task_hint,
  3) check whether the desired state actually happened (e.g. YouTube home is visible).
- DO NOT end the task immediately after sending keys or typing a URL.
  Always visually verify success at least once for navigation tasks.
- Only use longer sleeps (2–3 seconds) if the system appears slow or you have evidence that content is still loading.

WINDOWS SHORTCUTS (YOU SHOULD USE THESE!)
- Open Chrome quickly:
  - hotkey(['win']) then type_text("chrome") then press_key('enter').
- Focus browser address bar:
  - hotkey(['ctrl', 'l']) then type the URL, then press_key('enter').
- New tab:
  - hotkey(['ctrl', 't']).
- Switch apps:
  - hotkey(['alt', 'tab']) to cycle.
- Show desktop:
  - hotkey(['win', 'd']).
- Open first pinned taskbar app:
  - hotkey(['win', '1']) (second is 'win'+'2', etc.).

GRID MENTAL MODEL
- capture_and_describe_screen(grid_rows, grid_cols) divides the screen into a logical grid.
- Top-left is [0,0]; bottom-right is [rows-1, cols-1].
- Each 'notable_ui' item contains 'approx_grid_cell': [row, col].
- Separately, the screenshot overlay has 50px numbered cells with indices (0,1,2,...).
- When 'numbered_cell_index' is present for an element, prefer click_numbered_cell(index) for higher precision.

VISION-FIRST RULES
- Prefer capture_and_describe_screen over random guessing or asking the user.
- If capture_and_describe_screen returns an error, you may:
  - Try again once.
  - If it still fails, fall back to simple hotkeys or generic actions, but explain this limitation to the user.
- Do NOT spam the user with clarifying questions if the task is clear enough. Assume reasonable defaults.

ASKING THE HUMAN FOR INPUT
- If you need clarification that only the user can give, respond with a message that STARTS with:
  "[ASK_USER] " followed by your question.
- The outer program will show that question to the human and feed their answer back to you
  as a new user message. Then you CONTINUE the task with that new information.

STOPPING CONDITIONS
- When you believe you have completed the task, you MUST have visually verified it
  with at least one recent call to capture_and_describe_screen that confirms success.
- Then send a final normal message explaining:
  - What you did (briefly).
  - What the user should now see or do.
- If you hit a hard limit (system permission popup, unknown environment, or something dangerous),
  stop using tools and explain clearly what blocked you and what the user has to do manually.

SAFETY
- Consider that pyautogui can click ANYWHERE: behave carefully.
- Avoid actions that could obviously shut down or damage the system (e.g. power off, format, uninstall).
- Never intentionally move the mouse to the very top-left corner (this triggers the failsafe).
- When in doubt, prefer non-destructive actions and ask the user for confirmation via [ASK_USER].

STYLE
- Keep reasoning internal; your messages to the user should be short, clear, and focused on what’s done and what to do next.
"""

# =====================
# Single-task agent loop
# =====================

def run_single_task(user_task: str):
    """
    Runs the screen agent for ONE task.
    Returns when the model decides it is finished for this task.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_task},
    ]

    while True:
        completion = client.chat.completions.create(
            model="gpt-5.1",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = completion.choices[0].message
        messages.append(msg)

        # If the model called tools, execute them
        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}

                print(f"[Agent] Calling tool {func_name} with args {args}")
                tool_fn = TOOL_IMPLS.get(func_name)
                if not tool_fn:
                    tool_result = {"error": f"Tool {func_name} not implemented."}
                else:
                    try:
                        tool_result = tool_fn(**args)
                    except Exception as e:
                        tool_result = {"error": str(e)}

                print(f"[Tool Result] {tool_result}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                })

            # Loop again so the model can see tool results
            continue

        # No tool calls -> either final answer OR a question ([ASK_USER])
        content = msg.content or ""
        stripped = content.strip()

        # If the agent wants to ask the user something, it must start with [ASK_USER]
        if stripped.startswith("[ASK_USER]"):
            human_text = stripped[len("[ASK_USER]"):].strip()
            print("\n[Agent question for you]\n" + human_text + "\n")
            user_reply = input("Your answer: ")

            # Feed the answer back as a user message, then continue the loop
            messages.append({"role": "user", "content": user_reply})
            continue

        # Otherwise this is a final message for the task
        if content:
            print("\n=== Agent Final Message for this task ===")
            print(content)
            print("\n[Task finished]\n")
        break

# =====================
# Main loop
# =====================

def main():
    print("ScreenPilot v3 (vision + pyautogui + numbered grid). Move mouse to TOP-LEFT corner to trigger pyautogui failsafe.\n")
    try:
        while True:
            user_task = input("Enter your screen task (or type 'exit' to quit): ").strip()
            if user_task.lower() == "exit":
                print("Exiting ScreenPilot v3...")
                break
            if not user_task:
                continue
            run_single_task(user_task)
    finally:
        pass


if __name__ == "__main__":
    main()
