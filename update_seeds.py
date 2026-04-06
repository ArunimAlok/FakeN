import json
import os

SEED_FILE = "backend/seed_data.json"

if not os.path.exists(SEED_FILE):
    print(f"Error: {SEED_FILE} not found.")
    exit(1)

with open(SEED_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

extra = [
    {"text": "UNESCO declared India National Anthem as Best in the World! Share this with every Indian 🇮🇳", "label": "fake"},
    {"text": "NASA satellite images show India lighting up during Diwali. 🪔✨", "label": "fake"},
    {"text": "The WHO has confirmed that lemon water cures all diseases instantly.", "label": "fake"},
    {"text": "Breaking News: Prime Minister announces 2-day holiday for all schools starting tomorrow.", "label": "fake"},
    {"text": "Forwarded many times: Free recharge of Rs 500 for everyone who clicks this link! 🎁", "label": "fake"},
    {"text": "Indian Rupee reaches historical high against the US Dollar today.", "label": "fake"},
    {"text": "RBI is issuing new Rs 1000 notes from January 1st.", "label": "fake"},
    {"text": "Scientists discover new earth-like planet in the Proxima Centauri system.", "label": "real"},
    {"text": "The Federal Reserve raised interest rates by 0.25% in its recent meeting.", "label": "real"},
    {"text": "Apple announces new iPhone model with titanium frame and improved camera.", "label": "real"},
    {"text": "Climate change is accelerating the melting of Arctic ice according to new data.", "label": "real"},
    {"text": "Olympic games to be held in Los Angeles in 2028.", "label": "real"},
    {"text": "India wins the Cricket World Cup after a thrilling final against Australia.", "label": "real"},
    {"text": "Major breakthrough in cancer research involving mRNA technology published in Nature.", "label": "real"}
]

data.extend(extra)

with open(SEED_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)

print(f"Successfully added {len(extra)} seeds. New total: {len(data)}")
