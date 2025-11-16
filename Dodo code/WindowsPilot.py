import os
import time
import json
import base64
from io import BytesIO
from typing import List, Tuple

import pyautogui
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI


# =====================
# Basic setup
# =====================

# Fail-safe: moving mouse to TOP-LEFT corner aborts pyautogui
pyautogui.FAILSAFE = True

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Please set the OPENAI_API_KEY environment variable (your OpenAI API key).")

client = OpenAI(api_key=api_key)

GRID_SIZE = 50  # size of each numbered grid cell in pixels
LastGrid: List[Tuple[int, int]] = []  # index -> (center_x, center_y)


# =====================
# Your grid + screenshot utilities (AI-ready)
# =====================

def Screenshot() -> Image.Image:
    """
    Take a live screenshot of the current screen and return it as a PIL RGBA image.
    Use GridScreenshot() if you want the numbered grid overlay + LastGrid filled.
    """
    img = pyautogui.screenshot()
    return img.convert("RGBA")


def AddGridToImg(img: Image.Image) -> Image.Image:
    """
    Overlay a numbered grid on top of `img` and populate LastGrid with the
    center coordinates of each cell.

    Cell indexing:
        0 = top-left cell, increasing left-to-right, row-by-row.
    """
    global LastGrid
    LastGrid = []  # reset mapping

    grid_size = GRID_SIZE
    line_color = (255, 0, 0, 120)
    line_width = 1
    text_color = (255, 0, 0, 200)
    font_size = 20

    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # load font
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    # draw grid lines
    for x in range(0, w, grid_size):
        draw.line((x, 0, x, h), fill=line_color, width=line_width)

    for y in range(0, h, grid_size):
        draw.line((0, y, w, y), fill=line_color, width=line_width)

    # draw numbers & record centers in LastGrid
    cell_index = 0
    for y in range(0, h, grid_size):
        for x in range(0, w, grid_size):
            center_x = x + grid_size // 2
            center_y = y + grid_size // 2
            text = str(cell_index)

            # save center for ClickGrid()
            LastGrid.append((center_x, center_y))

            # get text bounding box
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            # draw centered text
            draw.text(
                (center_x - tw / 2, center_y - th / 2),
                text,
                fill=text_color,
                font=font,
            )

            cell_index += 1

    base = img.convert("RGBA") if img.mode != "RGBA" else img
    result = Image.alpha_composite(base, overlay)
    return result


def GridScreenshot() -> Image.Image:
    """
    Take a live screenshot, overlay the numbered grid, and return the result.
    Also refreshes LastGrid with the new cell centers.

    Typical AI usage:
      - call capture_and_describe_screen (which uses this internally)
      - model gets JSON with numbered_cell_index
      - then calls click_numbered_cell(index) to click.
    """
    img = Screenshot()
    result = AddGridToImg(img)
    return result


def ClickPosition(x: int, y: int) -> dict:
    """
    Move the mouse to (x, y) and click once.
    Suitable as a tool result (JSON serializable).
    """
    try:
        pyautogui.moveTo(x, y)
        pyautogui.click()
        return {
            "status": "ok",
            "action": "click_position",
            "x": x,
            "y": y,
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "click_position",
            "x": x,
            "y": y,
            "error": str(e),
        }


def ClickGrid(index: int) -> dict:
    """
    Click the center of a numbered grid cell, using LastGrid.

    Requires GridScreenshot() or AddGridToImg() to have been called earlier.
    """
    global LastGrid

    if index < 0 or index >= len(LastGrid):
        return {
            "status": "error",
            "action": "click_grid",
            "index": index,
            "error": f"Grid index {index} out of range (size={len(LastGrid)})",
        }

    x, y = LastGrid[index]
    base_res = ClickPosition(x, y)
    base_res["action"] = "click_grid"
    base_res["index"] = index
    return base_res


def Click() -> dict:
    """
    Click at the current mouse position.
    """
    try:
        pyautogui.click()
        return {
            "status": "ok",
            "action": "click_current",
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "click_current",
            "error": str(e),
        }


def MoveTo(x: int, y: int) -> dict:
    """
    Move mouse to (x, y) without clicking.
    """
    try:
        pyautogui.moveTo(x, y)
        return {
            "status": "ok",
            "action": "move_to",
            "x": x,
            "y": y,
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "move_to",
            "x": x,
            "y": y,
            "error": str(e),
        }


def SendKeys(keys: str, interval: float = 0.02) -> dict:
    """
    Type the given string as keyboard input.
    """
    try:
        pyautogui.write(keys, interval=interval)
        return {
            "status": "ok",
            "action": "send_keys",
            "text_length": len(keys),
            "interval": interval,
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "send_keys",
            "error": str(e),
        }


def PressKey(key: str) -> dict:
    """
    Press a single key (e.g. 'enter', 'tab', 'esc').
    """
    try:
        pyautogui.press(key)
        return {
            "status": "ok",
            "action": "press_key",
            "key": key,
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "press_key",
            "key": key,
            "error": str(e),
        }


def Hotkey(keys: list[str]) -> dict:
    """
    Press a combination as a hotkey, e.g. ['ctrl', 'l'] or ['win', 's'].
    """
    try:
        pyautogui.hotkey(*keys)
        return {
            "status": "ok",
            "action": "hotkey",
            "keys": keys,
        }
    except Exception as e:
        return {
            "status": "error",
            "action": "hotkey",
            "keys": keys,
            "error": str(e),
        }


def Sleep(seconds: float) -> dict:
    """
    Pause execution (to wait for UI updates).
    """
    time.sleep(seconds)
    return {"status": "slept", "seconds": seconds}


# =====================
# Vision helper using numbered grid
# =====================

def _take_grid_screenshot_for_ai():
    """
    Take a numbered-grid screenshot (updates LastGrid),
    save it, and return (path, width, height, base64_png).
    """
    img = GridScreenshot()
    ts = int(time.time())
    filename = f"screen_{ts}.png"
    img.save(filename, "PNG")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    w, h = img.size
    return filename, w, h, b64


def capture_and_describe_screen(task_hint: str | None = None,
                                coarse_grid_rows: int = 3,
                                coarse_grid_cols: int = 3):
    """
    Core vision tool.

    1. Takes a screenshot with your numbered grid overlay.
    2. Sends it to gpt-4.1-mini with instructions to:
       - Describe the screen.
       - Detect important UI elements.
       - Map them into:
         * a logical coarse grid (rows x cols)
         * your fine numbered grid (cell indices drawn on the image).
    3. Returns structured JSON the main agent can reason over.

    Returns JSON like:
    {
      "summary": "...",
      "notable_ui": [
        {
          "id": "google_chrome_icon",
          "role": "icon",
          "label": "Google Chrome",
          "approx_grid_cell": [1, 0],          # coarse grid row/col
          "numbered_cell_index": 158,          # YOUR numbered cell
          "notes": "Chrome icon on desktop"
        },
        ...
      ],
      "ocr_text_snippets": [...],
      "suggested_next_actions": [...],
      "_meta": {
        "screenshot_path": "...",
        "viewport": { "width": ..., "height": ... },
        "grid": { "rows": coarse_grid_rows, "cols": coarse_grid_cols },
        "numbered_grid": { "cell_size_pixels": GRID_SIZE }
      }
    }
    """
    path, w, h, b64 = _take_grid_screenshot_for_ai()
    img_url = f"data:image/png;base64,{b64}"

    task_text = task_hint or "No specific task provided; describe the screen in a useful way."

    system_msg = (
        "You are ScreenSummarizer, a helper for another agent that will control the computer.\n"
        "You receive: (1) the user's current task in words, and (2) a screenshot of the whole screen.\n\n"
        "IMPORTANT: The screenshot ALREADY has a fine grid overlay drawn on it:\n"
        "- Each small square cell (about 50x50 pixels) has a UNIQUE INTEGER INDEX written at its center.\n"
        "- This is the 'numbered grid'. For any UI element, you must try to read the number nearest "
        "  the element's center and call it 'numbered_cell_index'.\n\n"
        "Additionally, the controlling agent also uses a coarse logical grid of size "
        "coarse_grid_rows x coarse_grid_cols (e.g. 3x3) for high-level positioning.\n\n"
        "Your job: return a single JSON object with keys:\n"
        "{\n"
        '  "summary": string,  // short high-level summary of what is on screen\n'
        '  "notable_ui": [     // up to ~20 important UI elements\n'
        "    {\n"
        '      "id": string,              // short unique id you make up, like "search_box" or "chrome_icon_1"\n'
        '      "role": string,            // e.g. "button", "link", "input", "tab", "icon", "window"\n'
        '      "label": string,           // visible text on it, or best guess (e.g. "Google Chrome")\n'
        '      "approx_grid_cell": [r,c], // 0-based row/col of where it sits on the COARSE grid\n'
        '      "numbered_cell_index": int|null, // index of the numbered grid cell drawn on the screenshot; '
        'if unreadable, use null\n'
        '      "notes": string            // anything helpful: like "Chrome icon on desktop", "taskbar search field"\n'
        "    }, ...\n"
        "  ],\n"
        '  "ocr_text_snippets": [string, ...], // 5-20 short text snippets that look important (titles, headings, buttons)\n'
        '  "suggested_next_actions": [string, ...] // 3-10 plain-language suggestions like: '
        '"click the numbered cell containing \\"Google Chrome\\"", '
        '"click the taskbar search box and type \\"Chrome\\"" \n'
        "}\n\n"
        "Coarse grid definition:\n"
        "- The visible screen is divided into coarse_grid_rows x coarse_grid_cols.\n"
        "- Top-left corner is cell [0,0].\n"
        "- Bottom-right corner is cell [coarse_grid_rows-1, coarse_grid_cols-1].\n\n"
        "Be concise but informative. DO NOT include any comments outside the JSON. "
        "Return strictly valid JSON."
    )

    user_content = [
        {
            "type": "text",
            "text": (
                f"User task: {task_text}\n"
                f"Coarse grid size: rows={coarse_grid_rows}, cols={coarse_grid_cols}.\n"
                f"Fine grid: numbered cells of size about {GRID_SIZE}x{GRID_SIZE} pixels drawn on the image.\n"
                "Now analyze the screenshot and respond with the JSON described in the system message."
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
        "grid": {"rows": coarse_grid_rows, "cols": coarse_grid_cols},
        "numbered_grid": {"cell_size_pixels": GRID_SIZE},
    }

    return parsed


def raw_screenshot():
    """
    Simple screenshot tool: just capture and return basic info (no grid overlay).
    """
    img = Screenshot()
    ts = int(time.time())
    filename = f"screen_raw_{ts}.png"
    img.save(filename, "PNG")
    w, h = img.size
    return {
        "status": "ok",
        "path": filename,
        "width": w,
        "height": h,
    }


# =====================
# Tool registry (wrapping your functions)
# =====================

def tool_click_position(x: int, y: int):
    return ClickPosition(x, y)


def tool_click_numbered_cell(index: int):
    return ClickGrid(index)


def tool_move_mouse(x: int, y: int):
    return MoveTo(x, y)


def tool_click_current():
    return Click()


def tool_send_keys(text: str, interval: float = 0.02):
    return SendKeys(text, interval=interval)


def tool_press_key(key: str):
    return PressKey(key)


def tool_hotkey(keys: list[str]):
    return Hotkey(keys)


def tool_sleep(seconds: float):
    return Sleep(seconds)


TOOL_IMPLS = {
    "raw_screenshot": raw_screenshot,
    "capture_and_describe_screen": capture_and_describe_screen,
    "click_position": tool_click_position,
    "click_numbered_cell": tool_click_numbered_cell,
    "move_mouse": tool_move_mouse,
    "click_current": tool_click_current,
    "send_keys": tool_send_keys,
    "press_key": tool_press_key,
    "hotkey": tool_hotkey,
    "sleep": tool_sleep,
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "raw_screenshot",
            "description": "Take a screenshot of the full screen (no grid) and return basic info and path.",
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
            "description": "Take a screenshot with a numbered grid overlay and return a structured JSON description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_hint": {
                        "type": "string",
                        "description": "Short description of what you're trying to do, to help the vision model focus.",
                    },
                    "coarse_grid_rows": {
                        "type": "integer",
                        "description": "Number of rows in the coarse logical grid.",
                        "default": 3,
                    },
                    "coarse_grid_cols": {
                        "type": "integer",
                        "description": "Number of columns in the coarse logical grid.",
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
            "name": "click_position",
            "description": "Move the mouse to an absolute (x, y) position on the screen and click once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_numbered_cell",
            "description": "Click the center of a numbered grid cell by index. Requires capture_and_describe_screen to have been called recently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                },
                "required": ["index"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_mouse",
            "description": "Move the mouse to an absolute (x, y) position on the screen without clicking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_current",
            "description": "Click at the current mouse position.",
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
            "name": "send_keys",
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
            "description": "Pause for a number of seconds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "default": 0.7,
                    },
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
        },
    },
]


# =====================
# System prompt for ScreenPilot v3 (with numbered grid + shortcuts)
# =====================

SYSTEM_PROMPT = """
You are ScreenPilot v3, a vision-first automation agent.

You control the REAL computer using tools that:
- Take screenshots with a numbered grid overlay (capture_and_describe_screen).
- Move/click the mouse via numbered cells or absolute coordinates.
- Type text, press keys, and send hotkeys.
- Sleep briefly to allow the UI to update.

GENERAL STRATEGY
- Treat the screen as a black box of pixels. You do NOT have DOM, internal app APIs, or direct site structure.
- On a new task, almost always:
  1) Call capture_and_describe_screen with a short task_hint describing what you're trying to do.
  2) Inspect the returned JSON:
     - 'summary': what is on screen
     - 'notable_ui': list of UI items with 'label', 'role', 'approx_grid_cell', and 'numbered_cell_index'
     - '_meta.grid': the coarse grid size
  3) Prefer using VISIBLE targets related to the task:
     - Example: if the task is "open Chrome", FIRST look in 'notable_ui' for labels like "Google Chrome", "Chrome", or a browser icon.
       If 'numbered_cell_index' is present, use click_numbered_cell(index).
  4) After clicking something, use a SHORT sleep (0.3–1.0s) then capture_and_describe_screen again to verify the new state.

- Use send_keys ONLY after you've focused an input field (or used shortcuts to focus it).
- Use press_key / hotkey for things like:
  - 'enter', 'tab', 'esc'
  - ['ctrl','l'] to focus browser address bar
  - ['ctrl','t'] new tab
  - ['ctrl','w'] close tab

NUMBERED GRID MENTAL MODEL
- The screenshot has a fine grid drawn with numbers at each cell center.
- 'numbered_cell_index' in 'notable_ui' tells you EXACTLY which cell to click.
- Use click_numbered_cell(index) as your primary way to click elements detected by vision.
- Avoid guessing raw coordinates unless truly necessary.

COARSE GRID
- In addition, you have a coarse logical grid (e.g. 3x3) described by 'approx_grid_cell' [row, col].
- This is mainly for reasoning about layout (top-left / center / bottom-right).
- Prefer numbered_cell_index for precise clicking.

WINDOWS & BROWSER SHORTCUTS (VERY IMPORTANT)
- Opening Chrome:
  - Hotkey ['win'] (open start), then send_keys("chrome"), then press_key("enter").
- General:
  - ['win','d'] -> show desktop (toggle).
- In browser (Chrome/Edge/etc.):
  - ['ctrl','l'] -> focus address bar.
  - ['ctrl','t'] -> new tab.
  - ['ctrl','w'] -> close current tab.
  - ['ctrl','r'] or 'f5' -> refresh.
- On YouTube:
  - Once the page is clearly visible (via capture_and_describe_screen), look for 'Search' box or an input with label like 'Search'.

VERIFICATION
- Never just assume something worked because you sent keystrokes.
- After a sequence like opening Chrome and typing a URL:
  - Use a short sleep (0.5s), then call capture_and_describe_screen to confirm the browser window or page is present.
- If something expected does NOT show up, try again with a slightly different approach (e.g. click the browser icon directly).

SAFETY / FAIL-SAFE
- pyautogui.FAILSAFE is TRUE. Moving the mouse to a corner (e.g. top-left) will raise an exception and stop control.
- DO NOT intentionally move or click extremely close to the corners of the screen.
- Avoid destructive actions (shutdown, logout, uninstall, etc.).
- If you hit a fail-safe or exception, stop tool calls and explain clearly to the user what happened.

INTERACTION STYLE
- Keep your tool calls purposeful and minimal.
- Use short sleeps rather than long waits. Re-check visually instead of waiting many seconds.
- When you believe you have completed the task, send a final normal message explaining:
  - What you did (briefly).
  - What the user should now see or do next.
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

        if msg.tool_calls:
            # Execute tools
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

        # No tool calls -> model thinks it's done for this task
        if msg.content:
            print("\n=== Agent Final Message for this task ===")
            print(msg.content)
            print()
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
        # Nothing special to clean up here, but kept for symmetry
        pass


if __name__ == "__main__":
    main()
