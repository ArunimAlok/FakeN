import os
import requests
import asyncio
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWSAPI_BASE = "https://newsapi.org/v2"

# Fallback if no NewsAPI key: use GNews public RSS-style API (no auth needed)
GNEWS_BASE = "https://gnews.io/api/v4"
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")


class NewsService:
    def __init__(self):
        self.has_newsapi = bool(NEWS_API_KEY)
        self.has_gnews = bool(GNEWS_API_KEY)
        print(f"NewsService initialized — NewsAPI: {'✓' if self.has_newsapi else '✗'} | GNews: {'✓' if self.has_gnews else '✗'}")

    def get_top_headlines(self, country="in", category=None, page_size=10):
        """
        Fetches top headlines. Tries NewsAPI first, then GNews, 
        then returns mock structured data so UI never breaks.
        """
        if self.has_newsapi:
            res = self._fetch_newsapi_headlines(country, category, page_size)
            if not res and country == "in":
                # Fallback to US if India feed is empty on free tier
                res = self._fetch_newsapi_headlines("us", category, page_size)
            if res:
                return res
                
        if self.has_gnews:
            res = self._fetch_gnews_headlines(page_size)
            if res:
                return res
                
        # Fallback: curated real-looking demo articles
        return self._get_demo_articles()

    def search_news(self, query, page_size=5):
        """Searches for articles related to a query to cross-reference a claim."""
        if self.has_newsapi:
            return self._search_newsapi(query, page_size)
        if self.has_gnews:
            return self._search_gnews(query, page_size)
        return []

    # ──────────────────────────────────────────────
    # NewsAPI.org
    # ──────────────────────────────────────────────
    def _fetch_newsapi_headlines(self, country, category, page_size):
        try:
            params = {
                "country": country,
                "pageSize": page_size,
                "apiKey": NEWS_API_KEY
            }
            if category:
                params["category"] = category
            resp = requests.get(f"{NEWSAPI_BASE}/top-headlines", params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return self._normalize_newsapi(data.get("articles", []))
        except Exception as e:
            print(f"NewsAPI headlines error: {e}")
        return self._get_demo_articles()

    def _search_newsapi(self, query, page_size):
        try:
            params = {
                "q": query,
                "pageSize": page_size,
                "sortBy": "relevancy",
                "language": "en",
                "apiKey": NEWS_API_KEY
            }
            resp = requests.get(f"{NEWSAPI_BASE}/everything", params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return self._normalize_newsapi(data.get("articles", []))
        except Exception as e:
            print(f"NewsAPI search error: {e}")
        return []

    def _normalize_newsapi(self, articles):
        result = []
        for a in articles:
            if not a.get("title") or a["title"] == "[Removed]":
                continue
            result.append({
                "title": a.get("title", ""),
                "description": a.get("description") or "",
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown"),
                "published_at": a.get("publishedAt", ""),
                "image": a.get("urlToImage"),
            })
        return result

    # ──────────────────────────────────────────────
    # GNews (backup)
    # ──────────────────────────────────────────────
    def _fetch_gnews_headlines(self, page_size):
        try:
            params = {
                "token": GNEWS_API_KEY,
                "lang": "en",
                "country": "in",
                "max": page_size
            }
            resp = requests.get(f"{GNEWS_BASE}/top-headlines", params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return self._normalize_gnews(data.get("articles", []))
        except Exception as e:
            print(f"GNews headlines error: {e}")
        return self._get_demo_articles()

    def _search_gnews(self, query, page_size):
        try:
            params = {
                "q": query,
                "token": GNEWS_API_KEY,
                "lang": "en",
                "max": page_size
            }
            resp = requests.get(f"{GNEWS_BASE}/search", params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                return self._normalize_gnews(data.get("articles", []))
        except Exception as e:
            print(f"GNews search error: {e}")
        return []

    def _normalize_gnews(self, articles):
        result = []
        for a in articles:
            result.append({
                "title": a.get("title", ""),
                "description": a.get("description") or "",
                "url": a.get("url", ""),
                "source": a.get("source", {}).get("name", "Unknown"),
                "published_at": a.get("publishedAt", ""),
                "image": a.get("image"),
            })
        return result

    # ──────────────────────────────────────────────
    # Demo data (when no API key)
    # ──────────────────────────────────────────────
    def _get_demo_articles(self):
        return [
            {
                "title": "Government Launches New AI Policy Framework for Digital India",
                "description": "The Ministry of Electronics and IT unveiled a comprehensive AI policy aiming to position India as a global AI hub by 2030.",
                "url": "https://example.com/ai-policy",
                "source": "The Hindu",
                "published_at": datetime.utcnow().isoformat(),
                "image": None
            },
            {
                "title": "Supreme Court Passes Landmark Ruling on Digital Privacy",
                "description": "The Supreme Court ruled that citizens have a fundamental right to digital privacy, impacting how tech companies handle user data.",
                "url": "https://example.com/privacy-ruling",
                "source": "Times of India",
                "published_at": datetime.utcnow().isoformat(),
                "image": None
            },
            {
                "title": "ISRO Successfully Tests Reusable Launch Vehicle",
                "description": "India's space agency ISRO conducted a successful autonomous landing test of its reusable launch vehicle prototype.",
                "url": "https://example.com/isro-rlv",
                "source": "NDTV",
                "published_at": datetime.utcnow().isoformat(),
                "image": None
            },
            {
                "title": "RBI Keeps Repo Rate Steady at 6.5%, Cuts GDP Forecast",
                "description": "The Reserve Bank of India's Monetary Policy Committee voted unanimously to hold the repo rate, citing global uncertainty.",
                "url": "https://example.com/rbi-rates",
                "source": "Mint",
                "published_at": datetime.utcnow().isoformat(),
                "image": None
            },
            {
                "title": "WhatsApp Viral Forward About Free Government Laptops is Fake",
                "description": "Fact-checkers confirm that a widely-shared WhatsApp message claiming free laptops are being distributed is completely false.",
                "url": "https://example.com/whatsapp-fake",
                "source": "AltNews",
                "published_at": datetime.utcnow().isoformat(),
                "image": None
            },
            {
                "title": "India-Pakistan Relations: New Diplomatic Talks Underway",
                "description": "Senior diplomatic officials from both countries met for back-channel discussions in a Gulf nation.",
                "url": "https://example.com/india-pak-talks",
                "source": "Indian Express",
                "published_at": datetime.utcnow().isoformat(),
                "image": None
            },
        ]
