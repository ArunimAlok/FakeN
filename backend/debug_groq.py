import os, asyncio
from dotenv import load_dotenv
from llm_service import LLMService

load_dotenv()
llm = LLMService()

claim = "Trump is the president of the USA"

async def test():
    print(f"\n=== Testing Researcher + Analyzer ===")
    print(f"Claim: {claim}\n")

    queries = await llm.generate_search_queries(claim)
    print(f"Fact Query  : {queries[0]}")
    print(f"News Query  : {queries[1]}")
    print(f"DDG  Query  : {queries[2]}\n")

    result = await llm.analyze(
        claim,
        {"score": 0.45, "label": "Mixed"},
        None,
        None,
        queries[2]
    )
    print("=== VERDICT ===")
    for k, v in result.items():
        print(f"{k}: {v}")

asyncio.run(test())
