from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from pattern_model import PropagandaDetector
from llm_service import LLMService
from news_service import NewsService
from fact_check_service import FactCheckService
from propaganda_analyzer import analyze_propaganda_patterns
from translation_service import TranslationService
import asyncio
import sys

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc))


app = FastAPI(title="FakeN TruthSeeker API", version="3.1.0")

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
translation_service = TranslationService()
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
    Agentic RAG verification pipeline (v3.2):
    0. Language Detection + Translation  (Hindi/Hinglish → English via Groq)
    1. Stylistic Pattern Recognition     (LIAR dataset + rule-based sensationalism, original text)
    2. Qualifier Extraction              (llama-3.1-8b-instant — catches 'violent', 'secretly', etc.)
    3. Researcher LLM Query Generation   (llama-3.1-8b-instant — 4 queries when qualifiers exist)
    4. Google Fact Check Explorer API
    5. Rule-based propaganda signal detection (runs on ORIGINAL text to catch Hindi signals)
    6. Live News cross-reference         (NewsAPI)
    7. Qualifier-specific DDG search     (dedicated search for qualifier verification)
    8. Groq Master LLM synthesis         (llama-3.3-70b-versatile + DuckDuckGo grounding)
    """
    raw_text = request.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    # ── Step 0: Language Detection + Translation ─────────────────────────────
    translation = await translation_service.detect_and_translate(raw_text)
    text = translation["english_text"]          # all downstream steps use English
    detected_language = translation["detected_language"]
    was_translated = translation["was_translated"]

    safe_print(f"Language: {detected_language} | Translated: {was_translated}")
    if was_translated:
        safe_print(f"  Original : {raw_text[:80]}")
        safe_print(f"  Translated: {text[:80]}")


    # ── Step 1: Stylistic pattern score (on English text) ────────────────────
    pattern_result = detector.predict(text)

    # ── Step 2: Qualifier Extraction + Claim Classifier in parallel ──────────
    qualifiers, claim_type = await asyncio.gather(
        llm_service.extract_qualifiers(text),
        llm_service._classify_claim(text)
    )
    print(f"Claim Type: {claim_type} | Qualifiers: {qualifiers}")

    # ── Step 3: Qualifier-aware query generation ─────────────────────────────
    queries = await llm_service.generate_search_queries(text, qualifiers if qualifiers else None)
    fact_query = queries[0]    # precision query → fact-check
    news_query = queries[1]    # broad query → live news
    ddg_query  = queries[2]    # open query → DuckDuckGo
    qualifier_query = queries[3] if len(queries) > 3 else None

    print(f"Queries | Fact: '{fact_query}' | News: '{news_query}' | DDG: '{ddg_query}'" +
          (f" | Qualifier: '{qualifier_query}'" if qualifier_query else ""))

    # ── Step 4: Google Fact Check API ────────────────────────────────────────
    fact_check_result = fact_check_service.search_claims(fact_query)

    # ── Step 5: Rule-based propaganda on ORIGINAL text (catches Hindi signals)
    propaganda_result = analyze_propaganda_patterns(raw_text)

    # ── Step 6: Real-time news cross-reference ───────────────────────────────
    live_news = news_service.search_news(news_query, page_size=3)

    # ── Step 7: Qualifier-specific DDG search (async, if qualifiers present) ─
    qualifier_ddg_results = None
    if qualifier_query and qualifiers:
        loop = asyncio.get_event_loop()
        qualifier_ddg_results = await loop.run_in_executor(
            None, llm_service._live_search, qualifier_query, 3
        )
        print(f"Qualifier DDG results fetched for: '{qualifier_query}'")

    # ── Step 8: Master LLM synthesis ─────────────────────────────────────────
    llm_response = await llm_service.analyze(
        text, pattern_result, fact_check_result, live_news, ddg_query,
        claim_type,
        qualifiers=qualifiers,
        detected_language=detected_language,
        qualifier_ddg_results=qualifier_ddg_results
    )

    return {
        "pattern_analysis": pattern_result,
        "final_verdict": llm_response.get("verdict", "Unknown"),
        "explanation": llm_response.get("explanation", "No explanation provided."),
        "fact_check_match": fact_check_result is not None,
        "sources_used": llm_response.get("sources_used", []),
        "claim_type": claim_type,
        "qualifiers_detected": qualifiers,

        # Language metadata for the frontend badge
        "language_info": {
            "detected_language": detected_language,
            "was_translated": was_translated,
            "original_text": raw_text if was_translated else None,
            "translation_note": translation.get("translation_note", ""),
        },

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
