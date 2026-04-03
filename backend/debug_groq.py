import os, asyncio
from dotenv import load_dotenv
from llm_service import LLMService

load_dotenv()
llm = LLMService()

result = asyncio.run(llm.analyze(
    "Trump is the president of the USA",
    {"score": 0.55, "label": "Suspicious"},
    None,
    None
))

print("\n=== RESULT ===")
for k, v in result.items():
    print(f"{k}: {v}")
