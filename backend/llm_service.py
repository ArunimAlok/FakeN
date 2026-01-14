import asyncio
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            print("Gemini 2.5 Flash initialized successfully.")
        else:
            self.model = None
            print("Warning: GEMINI_API_KEY not found in environment variables.")

    async def analyze(self, text, pattern_result, retrieved_context=None):
        """
        Synthesizes the pattern result and retrieved context using Google Gemini 1.5 Flash.
        Falls back to simulation if no API key is provided.
        """
        
        # If no API key, use the enhanced simulation logic we built
        if not self.model:
            return await self._simulate_analyze(text, pattern_result, retrieved_context)

        # Build the prompt for Gemini
        context_str = retrieved_context["fact"] if retrieved_context else "No specific fact-check record found for this claim."
        
        prompt = f"""
        You are an expert Fake News Detector specialized in Indian social media contexts (WhatsApp forwards, news snippets).
        Analyze the following user input and provide a verdict based on the provided style analysis and factual context.

        USER INPUT: "{text}"
        
        FORENSIC ANALYSIS (Writing Style):
        - Suspicion Score: {pattern_result['score']} (0.0 to 1.0, where 1.0 is highly suspicious style)
        - Style Label: {pattern_result['label']}

        RETRIEVED FACTUAL CONTEXT:
        "{context_str}"

        INSTRUCTIONS:
        1. Compare the USER INPUT against the RETRIEVED FACTUAL CONTEXT.
        2. Consider the writing style score.
        3. Determine if the claim is:
           - "Verified / Safe": Claim is supported by fact.
           - "Confirmed Fake / Misleading": Fact explicitly contradicts the claim.
           - "Unverified / Exaggerated": Topic is real but the specific claim is unproven or hyperbolic.
           - "Suspicious": Style is manipulative and no factual support was found.
           - "Likely Safe": Style is neutral and no factual contradiction was found.
        4. Provide a concise explanation (1-2 sentences).

        Return ONLY a JSON object in this format:
        {{
            "verdict": "Verdict Name",
            "explanation": "concise explanation"
        }}
        """

        try:
            # Use loop.run_in_executor for synchronous genai call in async method
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: self.model.generate_content(prompt))
            
            # Extract JSON from response
            res_text = response.text.strip()
            # Clean possible markdown formatting
            if "```json" in res_text:
                res_text = res_text.split("```json")[1].split("```")[0].strip()
            
            result = json.loads(res_text)
            return result
        except Exception as e:
            with open("gemini_error.txt", "w") as f:
                f.write(str(e))
            print(f"Gemini API Error: {e}. Falling back to simulation.")
            return await self._simulate_analyze(text, pattern_result, retrieved_context)

    async def _simulate_analyze(self, text, pattern_result, retrieved_context=None):
        """Original skeptical simulation logic for fallback"""
        await asyncio.sleep(1.0) # Sim delay
        score = pattern_result["score"]
        verdict = "Likely Safe"
        explanation = "Standard information. No obvious manipulation detected."

        if score > 0.7:
            verdict = "High Risk of Fake News"
            explanation = "Exhibits strong characteristics of viral misinformation."
        elif score > 0.4:
            verdict = "Suspicious"
            explanation = "Has some elements often seen in unverified forwards."

        if retrieved_context:
            fact = retrieved_context["fact"]
            fact_lower = fact.lower()
            text_lower = text.lower()
            
            if any(word in fact_lower for word in ["fake", "never", "false", "misleading", "hoax"]):
                verdict = "Confirmed Fake / Misleading"
                explanation = f"FACT CHECK: {fact}"
            else:
                claims = ["richest", "best", "fastest", "first", "declared", "award", "highest"]
                found_claims = [c for c in claims if c in text_lower]
                actually_supports = any(c in fact_lower for c in found_claims)
                
                if found_claims and not actually_supports:
                    verdict = "Unverified / Exaggerated"
                    explanation = f"While we found info, the claim ('{found_claims[0]}') is unverified. Fact: {fact}"
                elif score < 0.3:
                    verdict = "Verified / Safe"
                    explanation = f"Consistent with verified facts: {fact}"
        
        return {"verdict": verdict, "explanation": explanation}
