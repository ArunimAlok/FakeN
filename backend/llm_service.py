import asyncio
import os
import json
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

    async def analyze(self, text, pattern_result, fact_check_result=None, live_news=None):
        """
        Synthesizes the pattern result, Fact Check API result, Live News,
        and DuckDuckGo live search into a single Groq LLM master call.
        Falls back to simulation if no API key is provided.
        """
        if not self.client:
            return await self._simulate_analyze(text, pattern_result, fact_check_result)

        # Build context blocks
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

        # Run DuckDuckGo live search in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        ddg_str = await loop.run_in_executor(None, self._live_search, text, 3)

        prompt = f"""
You are an expert Fake News Detector and Propaganda Analyst. Today's date is April 2025.
You have access to four layers of evidence, listed in order of priority (highest to lowest):
1. DuckDuckGo Live Web Search (MOST TRUSTED — real-time search results, always current)
2. Google Fact Check Explorer (Official debunkings by verified fact-checkers)
3. Live News (NewsAPI Current Events)
4. Stylistic Pattern Analysis (LIAR Dataset Model — LEAST TRUSTED, purely stylistic)

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
- ORDINAL NUMBERS: If DuckDuckGo results say someone is "the Xth president", it means they ARE CURRENTLY the president. For example, "Donald Trump is the 47th president of the United States" means Trump IS the current president in 2025. Do NOT confuse ordinal counting with historical references.
- TRUST ORDER: Always trust DuckDuckGo live search over your own training knowledge. If DuckDuckGo says something is true today, accept it as ground truth.
- RELEVANCE CHECK: Determine if the Fact Check or Live News is directly about the specific claim. If irrelevant, discard and use DuckDuckGo as primary source.
- VERDICT RULES: If DuckDuckGo contradicts claim -> "Unverified / Exaggerated". If DuckDuckGo confirms claim -> "Verified / Safe". If Fact-Check says 'False' for the exact claim -> "Confirmed Fake / Misleading". Otherwise use stylistic suspicion.

Return ONLY a valid JSON object with EXACTLY these keys (no markdown, no extra text):
{{
    "verdict": "Confirmed Fake / Misleading" | "Verified / Safe" | "Unverified / Exaggerated" | "Suspicious" | "Likely Safe",
    "explanation": "Clear explanation of the verdict based on relevant evidence",
    "gemini_analysis": "2-3 sentence nuanced analysis of propaganda or trustworthiness based on the evidence",
    "manipulation_intent": "What is the psychological goal? (e.g., Fear Mongering, Political Propaganda, Genuine News)",
    "target_audience": "Who is this targeting? (e.g., General public, nationalist audiences)",
    "news_correlation": "Does this twist or align with real recent events? (Yes/No with 1 sentence proof)",
    "counter_narrative": "A 1-sentence logical counter-argument or debunking statement"
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
