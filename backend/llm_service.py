import asyncio
import os
import json
from datetime import datetime
from groq import Groq
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()


class LLMService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
            print("Groq LLM (llama-3.3-70b-versatile) initialized successfully.")
        else:
            self.client = None
            print("Warning: GROQ_API_KEY not found in environment variables.")

    def _live_search(self, query: str, max_results: int = 3) -> str:
        """Run a real-time DuckDuckGo search and return top snippet text."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No live search results found."
            snippets = [f"- {r['title']}: {r['body']}" for r in results]
            return "Live Web Search Results:\n" + "\n".join(snippets)
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return "Live search temporarily unavailable."

    async def generate_search_queries(self, text: str) -> list[str]:
        """
        Uses a fast small model to generate 3 optimized, context-aware
        search queries for the given claim. Replaces the stop-word extractor.
        Falls back to a basic slice if the LLM call fails.
        """
        if not self.client:
            # Fallback: basic 4-word slice
            words = text.split()
            q = " ".join(words[:5])
            return [q, q, q]

        today = datetime.now().strftime("%B %Y")
        current_year = datetime.now().year
        prompt = f"""You are a search query optimizer. Given a claim to fact-check, generate exactly 3 short, targeted English search queries that would help verify it.

Claim: "{text}"
Today's date: {today}

Rules:
- Each query must be 3-6 words maximum
- Focus on the core subject, entity, and action
- ALWAYS include "{current_year}" in at least 2 of the 3 queries to bias toward recent results
- Make queries distinct (different angles: e.g., entity/source, event details, outcome)
- Return ONLY a JSON array of 3 strings, nothing else

Example output: ["Iran IRGC Hormuz 2026", "Strait Hormuz shipping disruption 2026", "Iran blocks Hormuz strait"]"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                    max_tokens=150,
                ),
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            # Handle both {"queries": [...]} and ["q1", "q2"] formats
            if isinstance(parsed, list):
                queries = parsed
            else:
                queries = parsed.get("queries", parsed.get("search_queries", list(parsed.values())[0]))
            if isinstance(queries, list) and len(queries) >= 1:
                # Ensure exactly 3
                while len(queries) < 3:
                    queries.append(queries[0])
                return queries[:3]
        except Exception as e:
            print(f"Researcher LLM error (falling back to basic slice): {e}")

        words = text.split()
        q = " ".join(words[:5])
        return [q, q, q]

    async def _classify_claim(self, text: str) -> str:
        """
        Uses the fast model to classify the type of claim.
        Returns one of: news_headline | political_statement | statistic |
                        whatsapp_forward | attributed_quote | general_claim
        """
        if not self.client:
            return "general_claim"
        prompt = f"""Classify this text into exactly one category. Return ONLY a JSON object with key 'type'.

Categories:
- news_headline: A factual news report or headline from a media outlet
- political_statement: A statement, threat, or declaration by an official body (government, military, party)
- statistic: A claim centered around a number, percentage, or dataset
- whatsapp_forward: Sensationalist, uses emojis/caps/urgency, viral-style message
- attributed_quote: A quote explicitly attributed to a named person
- general_claim: Anything else

Text: "{text}"

Return: {{"type": "<one of the 6 categories>"}}"""  
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=30,
                ),
            )
            parsed = json.loads(response.choices[0].message.content.strip())
            return parsed.get("type", "general_claim")
        except Exception:
            return "general_claim"

    async def analyze(self, text, pattern_result, fact_check_result=None, live_news=None, ddg_query=None, claim_type: str = None):
        """
        Synthesizes all evidence layers into a single Groq master LLM call.
        Falls back to simulation if no API key is provided.
        """
        if not self.client:
            return await self._simulate_analyze(text, pattern_result, fact_check_result)

        # If claim_type not pre-computed by caller, classify now
        if claim_type is None:
            claim_type = await self._classify_claim(text)
        # Build type-specific verdict guidance
        type_guidance = {
            "political_statement": "CLAIM TYPE = political_statement: This is an official statement/threat/declaration by a named body. Even if the exact quote cannot be verified, if the organisation exists and the geopolitical context is confirmed, use 'Suspicious' not 'Unverified'. Reserve 'Unverified/Exaggerated' only if the attributed body is fictional or actively contradicted.",
            "statistic": "CLAIM TYPE = statistic: Scrutinise the number carefully. Check if the source is named and credible. A statistic from 'a study' with no named author/journal should default to 'Suspicious'. Fabricated impossible numbers (e.g., >100%) should be 'Confirmed Fake / Misleading'.",
            "whatsapp_forward": "CLAIM TYPE = whatsapp_forward: This exhibits viral/forward characteristics. Apply heightened scepticism. Emojis, urgency and shouting caps are manipulation markers. Require strong DDG confirmation to give 'Verified / Safe'.",
            "attributed_quote": "CLAIM TYPE = attributed_quote: Verify whether the named person actually said this. If DDG has no record of the quote, it is likely fabricated — use 'Unverified / Exaggerated'. If confirmed, 'Verified / Safe'.",
            "news_headline": "CLAIM TYPE = news_headline: Treat as a factual assertion. Use DDG to confirm the key facts (who, what, when). If confirmed, 'Verified / Safe'. If the event happened but a specific detail is off, 'Suspicious'.",
            "general_claim": ""
        }
        claim_type_note = type_guidance.get(claim_type, "")
        fact_str = ""
        if fact_check_result:
            fact_str = (
                f"Fact Check found: {fact_check_result['claimant']} claimed "
                f"'{fact_check_result['claim_text']}'. "
                f"Reviewer {fact_check_result['reviewer']} rated it: {fact_check_result['rating']}."
            )
        else:
            fact_str = "No specific fact-check record found for this claim."

        news_str = ""
        if live_news:
            headlines = [f"- {a['source']}: {a['title']}" for a in live_news[:3]]
            news_str = "Recent Live News:\n" + "\n".join(headlines)
        else:
            news_str = "No related recent news found."

        # DuckDuckGo live search
        search_term = ddg_query or text
        loop = asyncio.get_event_loop()
        ddg_str = await loop.run_in_executor(None, self._live_search, search_term, 5)

        today = datetime.now().strftime("%B %Y")

        prompt = f"""You are an expert Fake News Detector and Propaganda Analyst. Today's date is {today}.
You have access to four layers of evidence, listed in order of priority (highest to lowest):
1. DuckDuckGo Live Web Search (MOST TRUSTED — real-time search results, always current)
2. Google Fact Check Explorer (Official debunkings by verified fact-checkers)
3. Live News (NewsAPI Current Events)
4. Stylistic Pattern Analysis (LIAR Dataset Model — LEAST TRUSTED, purely stylistic)

{claim_type_note}
USER INPUT TO VERIFY: "{text}"

---- EVIDENCE PACKET ----
FORENSIC ANALYSIS (Stylistic Model):
- Suspicion Score: {pattern_result['score']} (0.0=Safe, 1.0=Highly Suspicious)
- Label: {pattern_result['label']}

GOOGLE FACT CHECK EXPLORER RESULT:
{fact_str}

LIVE NEWS (NewsAPI):
{news_str}

LIVE WEB SEARCH (DuckDuckGo — Most Relevant & Current):
{ddg_str}

CRITICAL REASONING RULES:
- ORDINAL TITLES: In positional/tenure-based contexts (Presidents, Prime Ministers, CEOs, Champions), the person associated with the highest ordinal number in recent search results is the CURRENT holder of that title. Example: "47th president" = current president. Apply this principle globally for any country or organization.
- SOURCE CREDIBILITY: Prioritize information in this order: (1) Official Government Portals (.gov, .nic.in, etc.), (2) Global News Agencies (BBC, Reuters, AP), (3) Reputable Encyclopedias (Wikipedia). Forcibly discount or flag information from anonymous blogs, unverified social media threads, or known misinformation domains.
- CITATION RULE: In your 'explanation', you MUST explicitly cite your sources by name. Do not say "sources say"; say "According to [Official Source Name]..." or "As reported by [News Agency]...".
- TRUST ORDER: Always trust DuckDuckGo live search over your own training knowledge. If DuckDuckGo says something is true today, accept it as ground truth.
- RELEVANCE CHECK: If the Fact Check or Live News is about a different topic, discard it and rely solely on DuckDuckGo.
- VERDICT RULES (apply in strict order):
  1. Fact-Check explicitly says 'False' for THIS exact claim → "Confirmed Fake / Misleading"
  2. DuckDuckGo DIRECTLY contradicts a core fact in the claim (e.g., says the person is alive, event didn't happen) → "Unverified / Exaggerated"
  3. DuckDuckGo CONFIRMS the specific people, events, and key details in the claim → "Verified / Safe"
  4. DuckDuckGo confirms the CONTEXT of the claim is real, but a specific detail or future statement cannot be confirmed (e.g., official body made a statement, the situation exists, but an exact quote or prediction is unverified) → "Suspicious"
  5. No relevant evidence found, or claim is internally inconsistent → "Unverified / Exaggerated"
  6. No strong evidence either way → rely on stylistic suspicion score

- POLITICAL STATEMENTS RULE: If a claim is a political threat, warning, or future prediction attributed to a named official body (e.g., IRGC, NATO, US Government), AND DuckDuckGo confirms that body exists and the underlying geopolitical context is real, use "Suspicious" NOT "Unverified / Exaggerated". The claim is unverifiable by design (it's a political position), not false. Example: "Iran says X will never happen" → the Strait of Hormuz situation is real, so verdict = "Suspicious", not "Unverified/Exaggerated".

- GENUINE NEWS RULE: If the verdict is "Verified / Safe" or "Likely Safe", set manipulation_intent to "None / Genuine Reporting" and target_audience to "General News Audience". Do NOT invent psychological intent for factual news.

Return ONLY a valid JSON object with EXACTLY these keys (no markdown, no extra text):
{{
    "verdict": "Confirmed Fake / Misleading" | "Verified / Safe" | "Unverified / Exaggerated" | "Suspicious" | "Likely Safe",
    "explanation": "2-3 sentence summary that EXPLICITLY CITES sources by name (e.g., 'As confirmed by the BBC and ISRO official site...')",
    "gemini_analysis": "Deep forensic analysis. If genuine news, confirm what makes it credible.",
    "manipulation_intent": "'None / Genuine Reporting' for verified true news. Otherwise: the specific psychological goal (e.g., Fear Mongering, Political Propaganda).",
    "target_audience": "'General News Audience' for verified true news. Otherwise: who this is targeting.",
    "news_correlation": "Does this align with or contradict real events? (1 sentence with source name)",
    "counter_narrative": "For fake/suspicious: a debunking statement. For verified news: 'This appears to be factual reporting.'",
    "sources_used": ["list only sources you ACTUALLY cited in your explanation — from: 'duckduckgo', 'fact_check', 'news_api'. Leave empty [] if none were relevant."]
}}
"""

        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                ),
            )
            res_text = response.choices[0].message.content.strip()
            return json.loads(res_text)
        except Exception as e:
            print(f"Groq API Error: {e}")
            return await self._simulate_analyze(text, pattern_result, fact_check_result)

    async def _simulate_analyze(self, text, pattern_result, fact_check_result=None):
        """Simulation logic for fallback"""
        await asyncio.sleep(1.0)
        score = pattern_result["score"]
        verdict = "Likely Safe"
        explanation = "Standard information. No obvious manipulation detected."

        if score > 0.7:
            verdict = "Suspicious"
            explanation = "Exhibits strong characteristics of typical misinformation styles."

        if fact_check_result:
            if "false" in fact_check_result['rating'].lower() or "fake" in fact_check_result['rating'].lower():
                verdict = "Confirmed Fake / Misleading"
                explanation = f"Fact-checked by {fact_check_result['reviewer']} as {fact_check_result['rating']}."
            else:
                verdict = "Verified / Safe"
                explanation = f"Fact check rated this: {fact_check_result['rating']}."

        return {
            "verdict": verdict,
            "explanation": explanation,
            "gemini_analysis": "LLM unavailable. Fallback analysis active.",
            "manipulation_intent": "Determined by fallback rules (Score: " + str(score) + ").",
            "target_audience": "General audience.",
            "news_correlation": "Unable to verify without LLM.",
            "counter_narrative": "Evaluate factually without assuming deceptive intent."
        }
