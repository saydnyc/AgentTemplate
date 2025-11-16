# logicv3.py
# Generic Browser Agent with DOM summarizer sub-agent (no extra LLM)

import os
import json
import random
from datetime import datetime

from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# =====================
# OpenAI + Selenium setup
# =====================

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Please set the OPENAI_API_KEY environment variable (your OpenAI API key).")

client = OpenAI(api_key=api_key)

# Launch Chrome (adjust options as you like)
driver = webdriver.Chrome()

# =====================
# Selenium-backed tools
# =====================

def _get_by(by: str):
    by = by.lower()
    if by in ["css", "css_selector", "css selector"]:
        return By.CSS_SELECTOR
    if by == "xpath":
        return By.XPATH
    if by == "id":
        return By.ID
    if by == "name":
        return By.NAME
    if by in ["link_text", "link text"]:
        return By.LINK_TEXT
    raise ValueError(f"Unsupported locator type: {by}")


def goto_url(url: str):
    driver.get(url)
    return {"status": "navigated", "url": url}


def wait_for_element(by: str, selector: str, timeout: int = 10):
    by_type = _get_by(by)
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by_type, selector))
        )
        return {
            "status": "found",
            "by": by,
            "selector": selector,
            "timeout": timeout,
        }
    except TimeoutException:
        return {
            "status": "timeout",
            "by": by,
            "selector": selector,
            "timeout": timeout,
        }


def click_element(by: str, selector: str):
    """
    Click an element safely:
    - If disabled, return 'disabled' instead of throwing.
    - Try normal click first, then fallback JS click.
    """
    by_type = _get_by(by)
    element = driver.find_element(by_type, selector)

    disabled_attr = element.get_attribute("disabled")
    if (disabled_attr is not None) or (not element.is_enabled()):
        return {
            "status": "disabled",
            "by": by,
            "selector": selector,
            "disabled_attr": disabled_attr,
        }

    try:
        element.click()
        return {"status": "clicked", "by": by, "selector": selector}
    except Exception as e:
        # Fallback to JS click
        try:
            driver.execute_script("arguments[0].click();", element)
            return {
                "status": "clicked_js",
                "by": by,
                "selector": selector,
                "note": "used JS click fallback",
            }
        except Exception as e2:
            return {
                "status": "error",
                "by": by,
                "selector": selector,
                "error": str(e2),
                "original_error": str(e),
            }


def type_text(by: str, selector: str, text: str, submit: bool = False):
    by_type = _get_by(by)
    element = driver.find_element(by_type, selector)
    element.clear()
    element.send_keys(text)
    if submit:
        element.submit()
    return {
        "status": "typed",
        "by": by,
        "selector": selector,
        "text_length": len(text),
        "submitted": submit,
    }


def get_text(by: str, selector: str):
    by_type = _get_by(by)
    element = driver.find_element(by_type, selector)
    txt = element.text
    return {
        "status": "ok",
        "by": by,
        "selector": selector,
        "text": txt,
    }


def scroll_by(x: int = 0, y: int = 500):
    driver.execute_script("window.scrollBy(arguments[0], arguments[1]);", x, y)
    return {"status": "scrolled", "x": x, "y": y}


def get_page_html():
    """
    Return the current page HTML (trimmed).
    The main agent should usually prefer summarize_page_for_agent(),
    but this stays as a debug / backup tool.
    """
    html = driver.page_source
    max_len = 20000
    trimmed = html[:max_len]
    return {
        "status": "ok",
        "length": len(html),
        "returned_length": len(trimmed),
        "html": trimmed,
    }


def screenshot_page():
    """
    Take a screenshot of the current page for YOU to inspect manually.
    The agent only sees the file path.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{ts}.png"
    driver.save_screenshot(filename)
    return {
        "status": "saved",
        "file": filename,
    }


def list_form_elements():
    """
    Use JavaScript to list input/select/button elements and their attributes.
    Helps the AI pick correct selectors instead of guessing.
    """
    elements = driver.execute_script(
        """
        return Array.from(document.querySelectorAll('input, select, button')).map(e => ({
            tag: e.tagName,
            name: e.name || null,
            id: e.id || null,
            type: e.type || null,
            text: e.innerText || null,
            placeholder: e.placeholder || null,
            classes: e.className || null
        }));
        """
    )
    return {
        "status": "ok",
        "count": len(elements),
        "elements": elements,
    }


def list_clickable_elements():
    """
    List clickable elements (links, buttons, div[role=button]) with visible text.
    Very useful on dynamic apps.
    """
    elements = driver.execute_script(
        """
        return Array.from(
            document.querySelectorAll('a, button, div[role="button"]')
        ).map(e => ({
            tag: e.tagName,
            text: e.innerText || null,
            classes: e.className || null,
            aria_label: e.getAttribute('aria-label')
        }));
        """
    )
    return {
        "status": "ok",
        "count": len(elements),
        "elements": elements,
    }


def select_option(
    by: str,
    selector: str,
    visible_text: str | None = None,
    value: str | None = None,
    index: int | None = None,
    random_option: bool = False,
):
    """
    Select an <option> in a <select> dropdown.

    Priority:
    1) visible_text, if provided
    2) value, if provided
    3) index, if provided
    4) random_option=True -> pick a random non-placeholder option
    """
    by_type = _get_by(by)
    element = driver.find_element(by_type, selector)
    sel = Select(element)
    selected_text = None
    selected_value = None

    try:
        if visible_text is not None:
            sel.select_by_visible_text(visible_text)
        elif value is not None:
            sel.select_by_value(value)
        elif index is not None:
            sel.select_by_index(index)
        elif random_option:
            options = sel.options
            if len(options) > 1:
                idx = random.randint(1, len(options) - 1)
            else:
                idx = 0
            sel.select_by_index(idx)

        selected = sel.first_selected_option
        selected_text = selected.text
        selected_value = selected.get_attribute("value")
    except Exception as e:
        return {
            "status": "error",
            "by": by,
            "selector": selector,
            "error": str(e),
        }

    return {
        "status": "selected",
        "by": by,
        "selector": selector,
        "selected_text": selected_text,
        "selected_value": selected_value,
    }


# =====================
# DOM summarizer sub-agent (NO extra LLM)
# =====================

def _simple_css_for_element(tag, el):
    """
    Helper to make a simple CSS selector from an element descriptor.
    Prefers id, then name, then first class.
    """
    tag = (tag or "").lower() if tag else ""
    el_id = el.get("id")
    name = el.get("name")
    classes = el.get("classes")

    if el_id:
        return f"#{el_id}"
    if name and tag:
        # guess by tag+name
        return f"{tag.lower()}[name=\"{name}\"]"
    if classes:
        first_class = classes.split()[0]
        if first_class:
            return f"{tag.lower()}.{first_class}"
    return None


def summarize_page_for_agent():
    """
    Local-only summarizer:
    - Uses DOM (title, headings, paragraphs, inputs, buttons, links).
    - Returns a compact JSON string for the main agent to reason over.
    No extra OpenAI call here.
    """
    try:
        title = driver.title or ""
    except Exception:
        title = ""

    # Grab headings and some paragraph text
    try:
        headings = driver.execute_script(
            """
            return Array.from(document.querySelectorAll('h1, h2, h3'))
                .map(e => e.innerText)
                .filter(t => t && t.trim())
                .slice(0, 8);
            """
        ) or []
    except Exception:
        headings = []

    try:
        paragraphs = driver.execute_script(
            """
            return Array.from(document.querySelectorAll('p'))
                .map(e => e.innerText)
                .filter(t => t && t.trim())
                .slice(0, 5);
            """
        ) or []
    except Exception:
        paragraphs = []

    important_text = []
    seen = set()
    for t in [title] + headings + paragraphs:
        if not t:
            continue
        t = t.strip()
        if t and t not in seen:
            important_text.append(t)
            seen.add(t)

    # Use existing helpers to list form and clickable elements
    form_info = list_form_elements()
    click_info = list_clickable_elements()

    inputs = []
    buttons = []
    links = []

    # Inputs: from form elements that look like inputs/selects
    for el in form_info.get("elements", [])[:40]:
        tag = (el.get("tag") or "").lower()
        if tag in ("input", "select", "textarea", "button"):
            css = _simple_css_for_element(tag, el)
            inputs.append(
                {
                    "label": el.get("text"),
                    "placeholder": el.get("placeholder"),
                    "id": el.get("id"),
                    "name": el.get("name"),
                    "type": el.get("type"),
                    "css": css,
                }
            )

    # Buttons & links from clickables
    for el in click_info.get("elements", [])[:80]:
        tag = (el.get("tag") or "").lower()
        text = (el.get("text") or "").strip()
        aria = el.get("aria_label")
        css = None

        # Build pseudo element descriptor for CSS helper
        pseudo_el = {
            "id": None,
            "name": None,
            "classes": el.get("classes"),
        }
        css = _simple_css_for_element(tag, pseudo_el)

        if tag == "button" or (tag == "div" and aria):
            buttons.append(
                {
                    "text": text or None,
                    "aria_label": aria,
                    "css": css,
                }
            )
        elif tag == "a":
            links.append(
                {
                    "text": text or None,
                    "css": css,
                }
            )

    # Trim lists to keep it small
    inputs = inputs[:25]
    buttons = buttons[:25]
    links = links[:25]

    summary_obj = {
        "page_purpose": title or (headings[0] if headings else None),
        "important_text": important_text,
        "inputs": inputs,
        "buttons": buttons,
        "links": links,
    }

    return {
        "status": "ok",
        "summary": json.dumps(summary_obj, ensure_ascii=False),
    }


# Map tool names to Python functions
TOOL_IMPLS = {
    "goto_url": goto_url,
    "wait_for_element": wait_for_element,
    "click_element": click_element,
    "type_text": type_text,
    "get_text": get_text,
    "scroll_by": scroll_by,
    "get_page_html": get_page_html,
    "screenshot_page": screenshot_page,
    "list_form_elements": list_form_elements,
    "list_clickable_elements": list_clickable_elements,
    "select_option": select_option,
    "summarize_page_for_agent": summarize_page_for_agent,
}

# =====================
# Tool definitions (exposed to GPT)
# =====================

tools = [
    {
        "type": "function",
        "function": {
            "name": "goto_url",
            "description": "Navigate to a specified URL in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Absolute URL to navigate to, including protocol (https://...).",
                    }
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_element",
            "description": "Wait until an element exists in the DOM, or time out.",
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "description": "Locator strategy: css, xpath, id, name, or link_text.",
                        "enum": ["css", "xpath", "id", "name", "link_text"],
                    },
                    "selector": {
                        "type": "string",
                        "description": "The selector used with the chosen locator strategy.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max seconds to wait for the element.",
                        "default": 10,
                    },
                },
                "required": ["by", "selector"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_element",
            "description": "Click an element on the current page. Returns 'disabled' if the element is disabled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "description": "Locator strategy: css, xpath, id, name, or link_text.",
                        "enum": ["css", "xpath", "id", "name", "link_text"],
                    },
                    "selector": {
                        "type": "string",
                        "description": "The selector used with the chosen locator strategy.",
                    },
                },
                "required": ["by", "selector"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an input or textarea, with an option to submit the form.",
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "description": "Locator strategy: css, xpath, id, name, or link_text.",
                        "enum": ["css", "xpath", "id", "name", "link_text"],
                    },
                    "selector": {
                        "type": "string",
                        "description": "The selector used with the chosen locator strategy.",
                    },
                    "text": {
                        "type": "string",
                        "description": "The text to type into the element.",
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "If true, submit the form after typing.",
                        "default": False,
                    },
                },
                "required": ["by", "selector", "text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_text",
            "description": "Get visible text content from an element on the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "description": "Locator strategy: css, xpath, id, name, or link_text.",
                        "enum": ["css", "xpath", "id", "name", "link_text"],
                    },
                    "selector": {
                        "type": "string",
                        "description": "The selector used with the chosen locator strategy.",
                    },
                },
                "required": ["by", "selector"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_by",
            "description": "Scroll the page by a given offset in pixels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "Horizontal scroll offset in pixels (positive = right, negative = left).",
                        "default": 0,
                    },
                    "y": {
                        "type": "integer",
                        "description": "Vertical scroll offset in pixels (positive = down, negative = up).",
                        "default": 500,
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
            "name": "get_page_html",
            "description": "Get the current page HTML (trimmed). Prefer summarize_page_for_agent() first.",
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
            "name": "screenshot_page",
            "description": "Take a screenshot of the current page and save it as a PNG file.",
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
            "name": "list_form_elements",
            "description": "List input/select/button elements with their name, id, placeholder, etc., to help choose correct selectors.",
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
            "name": "list_clickable_elements",
            "description": "List clickable elements (links, buttons, div[role=button]) with visible text and classes.",
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
            "name": "select_option",
            "description": "Select a value in a <select> dropdown by visible text, value, index, or randomly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {
                        "type": "string",
                        "description": "Locator strategy: css, xpath, id, name, or link_text.",
                        "enum": ["css", "xpath", "id", "name", "link_text"],
                    },
                    "selector": {
                        "type": "string",
                        "description": "The selector used with the chosen locator strategy.",
                    },
                    "visible_text": {
                        "type": "string",
                        "description": "Visible text of the option to select (e.g., 'March', '14', '2007').",
                    },
                    "value": {
                        "type": "string",
                        "description": "Option value attribute to select.",
                    },
                    "index": {
                        "type": "integer",
                        "description": "Index of the option to select (0-based).",
                    },
                    "random_option": {
                        "type": "boolean",
                        "description": "If true (and no other selector provided), pick a random non-placeholder option.",
                        "default": False,
                    },
                },
                "required": ["by", "selector"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_page_for_agent",
            "description": (
                "Analyze the current page DOM and return a compact JSON description of "
                "its main UI elements (inputs, buttons, links, text). "
                "Use this instead of get_page_html when you want to understand the page."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]

# =====================
# System prompt (generic, multi-site, low-question)
# =====================

SYSTEM_PROMPT = """
You are WebAgent, an AI that controls a real Chrome browser through tools.

GOAL
- The user will give you natural language tasks like:
  - "host a kahoot game about earth science"
  - "make a Roblox account"
  - "find a cheap gaming mouse on eBay"
- Your job is to COMPLETE the task in the browser as far as technically possible
  using the provided tools.

GLOBAL RULES
- TOOLS FIRST: If the task involves a website, ALWAYS act with tools (goto_url, click_element, type_text, etc.).
- Do NOT keep asking the user follow-up questions when you can make reasonable assumptions.
  Example: "host a kahoot game about earth science" -> just create a 15–20 question quiz with normal difficulty.
- Only ask the user for:
  1) Credentials you absolutely need (email, password, etc.).
  2) Codes for 2FA / verification steps.
  3) Clarification when the task is genuinely ambiguous in a way that blocks you.

CREDENTIALS & PRIVACY
- The user might give you credentials (email, password, codes).
- Use them ONLY inside type_text() to log in.
- NEVER print, repeat, summarize, or expose credentials back to the user.
- NEVER include credentials in your final answer.

PAGE UNDERSTANDING
- When you need to understand what's currently on the page:
  1) Prefer calling summarize_page_for_agent() first.
     - It returns a JSON summary with page_purpose, important_text,
       and lists of inputs/buttons/links with suggested CSS selectors.
  2) Use that JSON to decide what to click or type next.
- Only call get_page_html() directly if:
  - The summary appears incomplete or wrong, OR
  - You are debugging selectors and need raw HTML.

OTHER USEFUL TOOLS
- list_form_elements(): discover inputs/selects/buttons and their attributes.
- list_clickable_elements(): discover clickable elements with visible text (good for apps with dynamic UIs).
- screenshot_page(): take a screenshot when you want the human to inspect something visually.

SELECTORS & ACTIONS
- Prefer robust selectors:
  - IDs: "#some-id"
  - Data attributes or clear aria-labels: "button[aria-label='Create new Kahoot.']"
  - Simple classes if needed: ".btn-primary"
- If a click or wait times out:
  - Try summarize_page_for_agent() or list_clickable_elements() to find better selectors.
  - Do NOT give up after a single failure.

CAPTCHAs & 2FA
- If you hit any of these, STOP tools and explain:
  - CAPTCHA / "I am not a robot"
  - 2-Step Verification / code sent to phone or email
  - Recovery questions / device verification
- Tell the user exactly what the page asks for and what they need to do manually.

FINAL ANSWER FORMAT
- When you decide the task is finished (or blocked), send ONE plain text message.
- Be concise. No essays. Include:
  1) What you just did (high level).
  2) Where the browser is now (e.g., "Kahoot game lobby is open, PIN is visible").
  3) What, if anything, the user must do manually next.

GENERAL MINDSET
- You are a quiet, efficient browser assistant.
- Prefer doing over talking.
- Take initiative. If details are missing but you can assume sane defaults, DO IT.
"""

# =====================
# Single-task agent loop
# =====================

def run_single_task(user_task: str):
    """
    Runs the browser agent for ONE task.
    Returns when the model decides it is finished for this task.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_task},
    ]

    while True:
        completion = client.chat.completions.create(
            model="gpt-5.1",  # main reasoning model
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = completion.choices[0].message
        messages.append(msg)

        # If there are tool calls, execute them and loop again
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
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    }
                )

            # Continue loop to let the model see tool results
            continue

        # No tool calls -> model believes it's finished for this task.
        if msg.content:
            print("\n=== Agent Final Message for this task ===")
            print(msg.content)
            print("\n[Task finished]\n")
        break


# =====================
# Infinite loop with 'exit'
# =====================

def main():
    try:
        while True:
            user_task = input("Enter your browser task (or type 'exit' to quit): ").strip()
            if user_task.lower() == "exit":
                print("Exiting WebAgent...")
                break
            if not user_task:
                continue
            run_single_task(user_task)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
