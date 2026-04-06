import os
import re
import requests

class FactCheckService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        print(f"FactCheckService initialized — API Key: {'✓' if self.api_key else '✗'}")

    def _relevance_score(self, query: str, claim_text: str) -> float:
        """
        Returns a 0-1 overlap score between two strings.
        Strips common stop words and checks how many key query terms appear in the claim.
        """
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at',
                      'of', 'for', 'to', 'and', 'or', 'not', 'this', 'that', 'it', 'by'}
        def keywords(text):
            words = re.findall(r'\b[a-z]+\b', text.lower())
            return {w for w in words if w not in stop_words and len(w) > 2}

        q_kw = keywords(query)
        c_kw = keywords(claim_text)
        if not q_kw:
            return 0.0
        return len(q_kw & c_kw) / len(q_kw)

    def search_claims(self, query):
        """
        Queries the Google Fact Check Tools API for verified fact-checks on a specific claim.
        Returns the top matching claim review if relevant, or None if no relevant match is found.
        """
        if not self.api_key:
            return None

        try:
            params = {
                "query": query,
                "key": self.api_key,
                "languageCode": "en-US",
                "pageSize": 3
            }
            resp = requests.get(self.base_url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                claims = data.get("claims", [])
                for claim in claims:
                    claim_text = claim.get("text", "")
                    # Relevance gate: skip claims that don't match the query topic
                    if self._relevance_score(query, claim_text) < 0.25:
                        continue
                    review = claim.get("claimReview", [{}])[0]
                    return {
                        "claim_text": claim_text,
                        "claimant": claim.get("claimant", "Unknown Source"),
                        "reviewer": review.get("publisher", {}).get("name", "Unknown Reviewer"),
                        "rating": review.get("textualRating", "Unknown Rating"),
                        "url": review.get("url", ""),
                        "review_date": review.get("reviewDate", "Unknown Date")
                    }
        except Exception as e:
            print(f"Fact Check API Error: {e}")
        return None
