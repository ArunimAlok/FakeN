import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

models_to_try = [
    'gemini-2.5-flash',
    'gemini-flash-latest', 
    'gemini-2.0-flash',
    'gemini-2.0-flash-lite',
    'gemini-1.5-flash'
]

for m in models_to_try:
    print(f"Testing {m}...")
    try:
        model = genai.GenerativeModel(m)
        response = model.generate_content("Hello, this is a connectivity test. Reply with 'OK'.")
        print(f"SUCCESS: {m}")
        print(f"Response: {response.text}")
        break
    except Exception as e:
        print(f"FAILED: {m} - {e}")
