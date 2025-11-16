import os
from openai import OpenAI
from selenium import webdriver

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)
Driver = webdriver.Chrome()

def goto_url(url: str):
    Driver.get(url)
    return {"status": "navigated", "url": url}

tools = [
    {
        "type": "function",
        "name": "GotoURL",
        "description": "Navigate to a specified URL in the browser",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"}
            },
            "required": ["url"],
            "additionalProperties": False
        }
    }
]

task = input("Enter your search task: ")

response = client.responses.create(
    model="gpt-5-nano",
    input="You are a ai browser agent. Complete the user's task using browser tools.",
    tools=tools,
    tool_choice="auto"
)

input(response.output_text)