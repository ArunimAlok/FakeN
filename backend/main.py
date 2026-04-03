from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pattern_model import PropagandaDetector
from llm_service import LLMService
from news_service import NewsService
from fact_check_service import FactCheckService
from propaganda_analyzer import analyze_propaganda_patterns
import os

app = FastAPI(title="FakeN TruthSeeker API", version="3.0.0")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize all services at startup
detector = PropagandaDetector()
llm_service = LLMService()
news_service = NewsService()
fact_check_service = FactCheckService()
# ──────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    text: str

# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "FakeN TruthSeeker v3.0 Backend is Running", "endpoints": [
        "/api/verify", "/api/news-feed", "/api/news-search"
    ]}


@app.post("/api/verify")
async def verify_message(request: VerifyRequest):
    """
    Full compound AI verification pipeline:
    1. TF-IDF Pattern Recognition (stylistic suspicion score from LIAR dataset)
    2. Google Fact Check Explorer AP retrieval
    3. Rule-based propaganda technique detection
    4. Real-time news search for cross-reference
    5. Gemini synthesis (verdict + propaganda deep analysis + Google Grounding)
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # Step 1: Stylistic pattern score (LIAR Dataset trained)
    pattern_result = detector.predict(text)

    # Step 2: Researcher LLM — generate 3 smart, context-aware search queries
    # Uses a fast small model (llama-3.1-8b-instant) to extract entities & intent
    queries = await llm_service.generate_search_queries(text)
    fact_query   = queries[0]   # Most precise — for official fact-check lookup
    news_query   = queries[1]   # Broader — for live news article search
    ddg_query    = queries[2]   # Open search — for DuckDuckGo web grounding

    print(f"AI Queries → Fact: '{fact_query}' | News: '{news_query}' | DDG: '{ddg_query}'")

    # Step 3: Google Fact Check API
    fact_check_result = fact_check_service.search_claims(fact_query)

    # Step 4: Rule-based propaganda pattern detection
    propaganda_result = analyze_propaganda_patterns(text)

    # Step 5: Real-time news cross-reference
    live_news = news_service.search_news(news_query, page_size=3)

    # Step 6: Master LLM synthesis (Verdict + Deep Propaganda Analysis)
    llm_response = await llm_service.analyze(text, pattern_result, fact_check_result, live_news, ddg_query)

    return {
        "pattern_analysis": pattern_result,
        "final_verdict": llm_response.get("verdict", "Unknown"),
        "explanation": llm_response.get("explanation", "No explanation provided."),
        "fact_check_match": fact_check_result is not None,

        "propaganda_analysis": {
            **propaganda_result,
            "gemini_analysis": llm_response.get("gemini_analysis", ""),
            "manipulation_intent": llm_response.get("manipulation_intent", ""),
            "target_audience": llm_response.get("target_audience", ""),
            "news_correlation": llm_response.get("news_correlation", ""),
            "counter_narrative": llm_response.get("counter_narrative", "")
        },
        "live_news_context": live_news,
        "fact_check_context": fact_check_result,
    }


@app.get("/api/news-feed")
def get_news_feed(
    country: str = Query("in", description="Country code e.g. 'in', 'us'"),
    category: str = Query(None, description="Category: business, technology, health, etc."),
    page_size: int = Query(10, ge=1, le=20)
):
    """
    Returns top current news headlines (used by the Live News Feed panel in the UI).
    """
    articles = news_service.get_top_headlines(country=country, category=category, page_size=page_size)
    return {"articles": articles, "total": len(articles)}


@app.get("/api/news-search")
def search_news(
    q: str = Query(..., description="Search query"),
    page_size: int = Query(5, ge=1, le=10)
):
    """
    Searches for news articles related to a query.
    """
    articles = news_service.search_news(query=q, page_size=page_size)
    return {"articles": articles, "query": q}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
