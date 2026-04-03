import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

try:
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents='Trump is the president',
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}]
        )
    )
    print("SUCCESS")
    print(response.text)
except Exception as e:
    print(f"FAILED WITH Exception: {type(e).__name__}")
    print(str(e))
