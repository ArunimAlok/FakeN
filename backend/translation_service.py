"""
translation_service.py

Two-stage input pre-processor:
  Stage 1 — Language Detection (llama-3.1-8b-instant, JSON mode)
             Classifies input as: "english" | "hindi" | "hinglish"
  Stage 2 — Translation (llama-3.1-8b-instant, if not English)
             Translates to natural English while:
               - Preserving proper nouns (names, places, parties) exactly
               - Preserving all claim qualifiers (adjectives/adverbs)
               - Never paraphrasing or summarising — verbatim intent only

Kept as a standalone service so it can be swapped for IndicTrans2
or Google Cloud Translate later without touching the pipeline.
"""

import asyncio
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_DEVANAGARI_RE = None  # lazy init


def _has_devanagari(text: str) -> bool:
    """Fast regex check for any Devanagari codepoint (U+0900–U+097F)."""
    import re
    global _DEVANAGARI_RE
    if _DEVANAGARI_RE is None:
        import re as _re
        _DEVANAGARI_RE = _re.compile(r"[\u0900-\u097F]")
    return bool(_DEVANAGARI_RE.search(text))


def _quick_classify(text: str) -> str | None:
    """
    Rule-based pre-classifier so we don't waste an LLM call on obvious English.
    Returns "hindi", "hinglish", or None (= unknown, let LLM decide).
    """
    if _has_devanagari(text):
        # Contains Devanagari — could be pure Hindi or mixed Hindi+English
        ascii_words = sum(1 for w in text.split() if w.isascii() and w.isalpha())
        total_words = max(len(text.split()), 1)
        if ascii_words / total_words > 0.35:
            return "hinglish"   # substantial Roman-script mix
        return "hindi"
    return None  # could be Hinglish (all-Roman) or English — need LLM


# ─────────────────────────────────────────────────────────────────────────────
# TranslationService
# ─────────────────────────────────────────────────────────────────────────────

class TranslationService:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key) if api_key else None
        if self.client:
            print("TranslationService initialized (Groq / llama-3.1-8b-instant).")
        else:
            print("Warning: TranslationService — GROQ_API_KEY missing. Translation disabled.")

    # ── Public entry point ────────────────────────────────────────────────────

    async def detect_and_translate(self, text: str) -> dict:
        """
        Returns:
        {
            "original_text":     str,   # raw user input
            "english_text":      str,   # translated (or original if already English)
            "detected_language": str,   # "english" | "hindi" | "hinglish"
            "was_translated":    bool,
            "translation_note":  str    # human-readable label for UI badge
        }
        """
        if not self.client or not text.strip():
            return self._passthrough(text, "english")

        # Fast rule-based pre-check (avoids an LLM call for obvious Hindi)
        quick_lang = _quick_classify(text)

        if quick_lang is None:
            # Ambiguous — let the LLM decide (English vs all-Roman Hinglish)
            detected = await self._llm_detect_language(text)
        else:
            detected = quick_lang

        if detected == "english":
            return self._passthrough(text, "english")

        # Needs translation
        english_text = await self._llm_translate(text, detected)
        label = "🇮🇳 Hindi detected" if detected == "hindi" else "🇮🇳 Hinglish detected"

        return {
            "original_text":     text,
            "english_text":      english_text,
            "detected_language": detected,
            "was_translated":    True,
            "translation_note":  f"{label} — translated to English for analysis",
        }

    # ── Stage 1: Language Detection ───────────────────────────────────────────

    async def _llm_detect_language(self, text: str) -> str:
        """
        Uses the fast model to decide if all-Roman text is English or Hinglish.
        Pure Devanagari is already handled by _quick_classify.
        """
        prompt = f"""You are a language classifier. Classify the language of the following text.

Text: "{text}"

Rules:
- "english" — purely English text with no Hindi words mixed in
- "hindi"   — written in Devanagari script (e.g., अभिजीत दीपके ने प्रदर्शन किया)
- "hinglish" — Hindi meaning expressed using Roman script, possibly mixed with English
               (e.g., "CJP leader ne hinsa wala protest kiya", "aaj ka news sunno")

Return ONLY a JSON object: {{"language": "english" | "hindi" | "hinglish"}}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=20,
                ),
            )
            parsed = json.loads(response.choices[0].message.content.strip())
            lang = parsed.get("language", "english").lower()
            if lang not in ("english", "hindi", "hinglish"):
                lang = "english"
            return lang
        except Exception as e:
            print(f"[TranslationService] Language detection error: {e}")
            return "english"   # safe fallback

    # ── Stage 2: Translation ──────────────────────────────────────────────────

    async def _llm_translate(self, text: str, source_lang: str) -> str:
        """
        Translates Hindi or Hinglish to English using llama-3.1-8b-instant.

        Critical rules baked into the prompt:
        1. Proper nouns (names, parties, places) are preserved verbatim
        2. Qualifier adjectives/adverbs (violent, secret, forced, illegal) are NEVER dropped
        3. No paraphrasing or summarising — output has the same factual content
        4. Numbers, dates, and statistics are kept exactly as-is
        """
        script_note = (
            "Devanagari script Hindi" if source_lang == "hindi"
            else "Hinglish (Hindi written in Roman script, mixed with English)"
        )

        prompt = f"""You are a precise fact-preserving translator. Translate the following {script_note} text into natural English.

STRICT TRANSLATION RULES — follow every rule or the translation is invalid:
1. PROPER NOUNS: Translate proper nouns (person names, political party names, place names, organisation names) from Devanagari to their standard Roman-script spelling. Do NOT translate them into English words — just transliterate or use the known English name.
   Examples: "अभिजीत दीपके" → "Abhijeet Dipke" | "भारतीय जनता पार्टी" → "BJP" | "दिल्ली" → "Delhi"
2. QUALIFIERS (most important): NEVER drop or weaken adjectives or adverbs that modify the claim.
   Examples: "हिंसक प्रदर्शन" → "violent protest" (NOT just "protest") | "गुप्त रूप से" → "secretly"
3. NUMBERS & DATES: Keep all numbers, percentages, and dates exactly as stated.
4. NO PARAPHRASING: Do not summarise, reword the intent, or add your own interpretation.
5. TONE: Preserve the original tone (sensational, neutral, alarming, etc.).

Text to translate: "{text}"

Return ONLY a JSON object: {{"english": "<translated text>"}}"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    max_tokens=300,
                ),
            )
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            translated = parsed.get("english", "").strip()
            if not translated:
                raise ValueError("Empty translation returned")
            return translated
        except Exception as e:
            print(f"[TranslationService] Translation error: {e}. Using original text.")
            return text   # fallback: use original so pipeline doesn't break

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _passthrough(text: str, lang: str) -> dict:
        return {
            "original_text":     text,
            "english_text":      text,
            "detected_language": lang,
            "was_translated":    False,
            "translation_note":  "",
        }
