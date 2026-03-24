# import os
# import google.generativeai as genai

# #genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# genai.configure(api_key="AQ.Ab8RN6IMe71HYO8OQkHmWOnHhUT_VMxWW__jB5jATGPCkFb65A") 

# model = genai.GenerativeModel("gemini-1.5-flash")

# response = model.generate_content("Say hello in one sentence.")
# print(response.text)

import os
from google import genai

# client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
client = genai.Client(api_key="AQ.Ab8RN6IMe71HYO8OQkHmWOnHhUT_VMxWW__jB5jATGPCkFb65A")

# client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"])

print("Available models:")
for m in client.models.list():
    print(m.name)


response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents="Say hello in one sentence."
)

print(response.text)