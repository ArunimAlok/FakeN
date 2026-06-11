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
        results = []
        try:
            with DDGS() as ddgs:
                # Try getting latest news first for recent events
                try:
                    news_res = list(ddgs.news(query, max_results=max_results))
                    if news_res:
                        results.extend(news_res)
                except Exception as e:
                    print(f"DDG news error: {e}")
                
                # If no news or ratelimited, fallback to regular text search
                if not results:
                    try:
                        text_res = list(ddgs.text(query, max_results=max_results, timelimit='w'))
                        if text_res:
                            results.extend(text_res)
                    except Exception as e:
                        print(f"DDG text error: {e}")
                
                if not results:
                    # One more try without timelimit
                    try:
                        text_res = list(ddgs.text(query, max_results=max_results))
                        if text_res:
                            results.extend(text_res)
                    except Exception as e:
                        pass

            if not results:
                return "No live search results found."
            
            snippets = []
            seen = set()
            for r in results:
                title = r.get('title', '')
                if title in seen:
                    continue
                seen.add(title)
                body = r.get('body', r.get('snippet', ''))
                snippets.append(f"- {title}: {body}")
            
            return "Live Web Search Results:\n" + "\n".join(snippets[:max_results*2])
        except Exception as e:
            print(f"DuckDuckGo search error: {e}")
            return "Live search temporarily unavailable."

    async def generate_search_queries(self, text: str, qualifiers: list[str] | None = None) -> list[str]:
        """
        Uses a fast small model to generate 3 optimized, context-aware
        search queries for the given claim, PLUS an optional 4th qualifier-
        specific query when qualifiers (e.g. 'violent', 'secret') are present.

        Returns a list of 3 strings (or 4 if qualifier query was added):
          [0] = fact-check precision query
          [1] = broad news query
          [2] = DDG open query
          [3] = qualifier-specific query (ONLY if qualifiers exist)
        """
        if not self.client:
            words = text.split()
            q = " ".join(words[:5])
            return [q, q, q]

        today = datetime.now().strftime("%B %Y")
        current_year = datetime.now().year

        qualifier_instruction = ""
        if qualifiers:
            q_list = ", ".join(f'"{q}"' for q in qualifiers)
            qualifier_instruction = (
                f"\n- IMPORTANT: The claim contains qualifier(s): {q_list}. "
                f"One of your 3 queries MUST specifically verify this qualifier "
                f"(e.g., if qualifier is 'violent', search for 'CJP protest violent {current_year}')."
            )

        prompt = f"""You are a search query optimizer. Given a claim to fact-check, generate exactly 3 short, targeted English search queries.

Claim: "{text}"
Today's date: {today}

Rules:
- Each query must be 3-6 words maximum
- Focus on the core subject, entity, and action
- ALWAYS include "{current_year}" in at least 2 of the 3 queries to bias toward recent results
- Make queries distinct (different angles: entity/source, event details, outcome)
- Return ONLY a JSON array of 3 strings, nothing else{qualifier_instruction}

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
                    max_tokens=200,
                ),
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                queries = parsed
            else:
                queries = parsed.get("queries", parsed.get("search_queries", list(parsed.values())[0]))
            if isinstance(queries, list) and len(queries) >= 1:
                while len(queries) < 3:
                    queries.append(queries[0])
                queries = queries[:3]

                # Append a dedicated qualifier query if qualifiers exist
                if qualifiers:
                    q_terms = " ".join(qualifiers[:2])   # max 2 qualifier words
                    # Extract key nouns from text (first 3 words) + qualifier
                    core = " ".join(text.split()[:3])
                    qualifier_query = f"{core} {q_terms} {current_year}"
                    queries.append(qualifier_query)

                return queries
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

    async def extract_qualifiers(self, text: str) -> list[str]:
        """
        Extracts claim-modifying qualifiers (adjectives/adverbs) from the text
        that could be the actual misinformation vector — e.g., a protest happened
        but was it VIOLENT? A deal was signed but was it SECRET?

        Returns a list of qualifier strings (may be empty for neutral claims).
        Examples:
          "CJP called for a violent protest"  → ["violent"]
          "PM Modi secretly signed a deal"     → ["secretly"]
          "Iran-US ceasefire reached"          → []   (no qualifying modifier)
        """
        if not self.client:
            return []

        prompt = f"""You are a claim qualifier extractor for a fake news detector.

Given a factual claim, identify ONLY the adjectives or adverbs that MODIFY or QUALIFY the core event/action in a way that could change its truth value.

Think of it this way: if you remove these words, does the core claim become much more ordinary and likely true? If yes, those words are qualifiers.

Examples:
- "CJP leader called for a violent protest" → qualifiers: ["violent"]
- "PM Modi secretly signed a trade deal"    → qualifiers: ["secretly"]
- "Police brutally beat peaceful protesters" → qualifiers: ["brutally", "peaceful"]
- "Iran-US ceasefire was reached"           → qualifiers: []  (no suspicious modifier)
- "BJP won the election"                    → qualifiers: []  (plain factual claim)
- "SHOCKING: Government hiding truth"       → qualifiers: ["hiding"]  (core qualifier)

Rules:
- Only return qualifiers that represent a FACTUAL CLAIM that can be independently verified
- Do NOT return generic sentiment words (e.g., 'big', 'great', 'important')
- Do NOT return words that are part of the core event noun itself
- Return an EMPTY array if no meaningful qualifiers exist
- Maximum 4 qualifiers

Claim: "{text}"

Return ONLY a JSON object: {{"qualifiers": ["word1", "word2"]}} or {{"qualifiers": []}}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=80,
                ),
            )
            parsed = json.loads(response.choices[0].message.content.strip())
            qualifiers = parsed.get("qualifiers", [])
            if isinstance(qualifiers, list):
                return [str(q).lower().strip() for q in qualifiers if q]
        except Exception as e:
            print(f"[LLMService] Qualifier extraction error: {e}")
        return []

    async def analyze(self, text, pattern_result, fact_check_result=None, live_news=None, ddg_query=None, claim_type: str = None, qualifiers: list[str] | None = None, detected_language: str = "english", qualifier_ddg_results: str | None = None):
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
            "political_statement": "CLAIM TYPE = political_statement: This is an official statement/threat/declaration by a named body. CRITICAL DISTINCTION: (A) If the claim describes a concrete real-world EVENT (ceasefire, treaty, meeting, attack, agreement) AND DuckDuckGo confirms that event actually happened → use 'Verified / Safe'. (B) If the claim is a future prediction or unverifiable exact quote from an official and DDG only confirms the broader context (the body exists, tensions are real) but NOT the specific event → use 'Suspicious'. Do NOT use Suspicious for confirmed factual events just because they involve governments.",
            "statistic": "CLAIM TYPE = statistic: Scrutinise the number carefully. Check if the source is named and credible. A statistic from 'a study' with no named author/journal should default to 'Suspicious'. Fabricated impossible numbers (e.g., >100%) should be 'Confirmed Fake / Misleading'.",
            "whatsapp_forward": "CLAIM TYPE = whatsapp_forward: This exhibits viral/forward characteristics. Apply heightened scepticism. Emojis, urgency and shouting caps are manipulation markers. Require strong DDG confirmation to give 'Verified / Safe'.",
            "attributed_quote": "CLAIM TYPE = attributed_quote: Verify whether the named person actually said this. If DDG has no record of the quote, it is likely fabricated — use 'Unverified / Exaggerated'. If confirmed, 'Verified / Safe'.",
            "news_headline": "CLAIM TYPE = news_headline: Treat as a factual assertion. Use DDG to confirm the key facts (who, what, when). If DDG confirms the core event occurred (e.g., a ceasefire happened, a meeting took place, an agreement was signed), use 'Verified / Safe' even if DDG does not reproduce the exact wording of the headline. Only use 'Suspicious' if a SPECIFIC FACTUAL DETAIL (a number, a date, a named person) is contradicted or absent. Do not require verbatim quote confirmation to give Verified.",
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

        # If qualifier-specific DDG results were pre-fetched by the caller, append them
        if qualifier_ddg_results:
            ddg_str += "\n\nQUALIFIER-SPECIFIC SEARCH RESULTS:\n" + qualifier_ddg_results

        today = datetime.now().strftime("%B %Y")

        # Build qualifier section for the prompt
        qualifier_note = ""
        if qualifiers:
            q_formatted = ", ".join(f'"{q}"' for q in qualifiers)
            qualifier_note = f"""
QUALIFIER VERIFICATION RULE (CRITICAL — read before issuing verdict):
The claim contains qualifier(s): {q_formatted}.
These qualifiers MODIFY the core event and represent a SEPARATE factual assertion that must be independently verified.
Step 1: Verify the CORE EVENT (did the protest/meeting/deal happen at all?)
Step 2: Verify EACH QUALIFIER (was the protest violent? was the deal secret? were people forced?)
If Step 1 is confirmed BUT Step 2 has NO evidence for the qualifier(s) → verdict MUST be "Suspicious" or "Unverified / Exaggerated".
Do NOT return "Verified / Safe" if ONLY the core event is confirmed but the qualifier is unverified.
If the qualifier search (see QUALIFIER-SPECIFIC SEARCH RESULTS section below) also returns nothing → even stronger signal for "Suspicious".
"""

        # Language context
        lang_note = ""
        if detected_language in ("hindi", "hinglish"):
            lang_note = f"\nINPUT LANGUAGE: The original claim was in {detected_language.capitalize()} and has been machine-translated to English for analysis. Proper nouns (names, parties, places) may have minor transliteration variations — treat near-matches as the same entity."

        prompt = f"""You are an expert Fake News Detector and Propaganda Analyst. Today's date is {today}.
You have access to four layers of evidence, listed in order of priority (highest to lowest):
1. DuckDuckGo Live Web Search (MOST TRUSTED — real-time search results, always current)
2. Google Fact Check Explorer (Official debunkings by verified fact-checkers)
3. Live News (NewsAPI Current Events)
4. Stylistic Pattern Analysis (LIAR Dataset Model — LEAST TRUSTED, purely stylistic)

{claim_type_note}{qualifier_note}{lang_note}
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
  3. DuckDuckGo CONFIRMS the core event or facts in the claim (the thing happened, the people were involved, the agreement/ceasefire/meeting/attack occurred) → "Verified / Safe". NOTE: You do NOT need verbatim quote reproduction. If DDG confirms a ceasefire happened between Iran and the US, a claim saying 'Iran-US ceasefire reached' is VERIFIED even if DDG doesn't use the exact same words.
  4. DuckDuckGo confirms ONLY the background context (the parties exist, there are ongoing tensions) but does NOT confirm the specific event or action claimed (no ceasefire, no meeting, no stated outcome found) → "Suspicious"
  5. No relevant evidence found, or claim is internally inconsistent → "Unverified / Exaggerated"
  6. No strong evidence either way → rely on stylistic suspicion score

- POLITICAL STATEMENTS RULE: If a claim is a political threat, warning, or future prediction attributed to a named official body, AND DuckDuckGo confirms that body exists and the geopolitical context is real BUT the exact quote is unverified, use "Suspicious" NOT "Unverified / Exaggerated". HOWEVER, if the statement refers to a concrete factual event (like a ceasefire, treaty, attack, or meeting) that DuckDuckGo CONFIRMS has happened, ALWAYS use "Verified / Safe".
- IRAN-US / GEOPOLITICAL NEWS RULE: Claims about Iran-US ceasefires, negotiations, diplomatic events, or military developments are ESPECIALLY prone to false Suspicious classification. If DuckDuckGo returns multiple recent news sources (especially BBC, Reuters, AP, Al Jazeera) reporting the same Iran-US event as fact, treat it as "Verified / Safe". Do not demand that DDG reproduce the exact headline wording. A convergence of multiple credible sources reporting the same event = confirmed.
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
