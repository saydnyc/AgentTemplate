import os
from selenium import webdriver
from openai import OpenAI

# if there is an error do 
# setx OPENAI_API_KEY "key"
# Or just set the "api_key" variable directly below
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Api key not set")

client = OpenAI(api_key=api_key)

driver = webdriver.Chrome()
driver.get("https://google.com/")

while True:
    img = driver.get_screenshot_as_base64()

    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
          {"role":"system", "content":[ { "type":"text", "text":"You are a system that analizies what is on the broswer." } ]},
          {"role":"user", "content":[ 
              { "type":"image_url", "image_url": { "url": f"data:image/jpeg;base64,{img}" } }
          ]}
        ],
    )



    answer = response.choices[0].message.content
    print(answer)

driver.quit()
