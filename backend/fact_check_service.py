import os
import requests

class FactCheckService:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        print(f"FactCheckService initialized — API Key: {'✓' if self.api_key else '✗'}")

    def search_claims(self, query):
        """
        Queries the Google Fact Check Tools API for verified fact-checks on a specific claim.
        Returns the top matching claim review, or None if no match is found.
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
                if claims:
                    # Return top match with the most relevant review details
                    top_claim = claims[0]
                    review = top_claim.get("claimReview", [{}])[0]
                    return {
                        "claim_text": top_claim.get("text", "Unknown Claim"),
                        "claimant": top_claim.get("claimant", "Unknown Source"),
                        "reviewer": review.get("publisher", {}).get("name", "Unknown Reviewer"),
                        "rating": review.get("textualRating", "Unknown Rating"),
                        "url": review.get("url", ""),
                        "review_date": review.get("reviewDate", "Unknown Date")
                    }
        except Exception as e:
            print(f"Fact Check API Error: {e}")
        return None
