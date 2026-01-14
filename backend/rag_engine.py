import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class RagEngine:
    def __init__(self, kb_path="knowledge_base.json"):
        self.kb_path = kb_path
        self.knowledge_base = []
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.kb_vectors = None
        self._load_kb()

    def _load_kb(self):
        if not os.path.exists(self.kb_path):
            print(f"Warning: {self.kb_path} not found.")
            return

        with open(self.kb_path, "r", encoding="utf-8") as f:
            self.knowledge_base = json.load(f)

        if self.knowledge_base:
            # Combine topic and fact for better matching
            texts = [f"{item['topic']} {item['fact']}" for item in self.knowledge_base]
            self.kb_vectors = self.vectorizer.fit_transform(texts)
            print(f"RAG Engine loaded with {len(self.knowledge_base)} facts.")

    def retrieve(self, query, top_k=1, threshold=0.1):
        if not self.knowledge_base or self.kb_vectors is None:
            return None

        query_vector = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.kb_vectors).flatten()
        
        # Get the best match
        best_idx = similarities.argmax()
        best_score = similarities[best_idx]

        if best_score > threshold:
            return {
                "fact": self.knowledge_base[best_idx]["fact"],
                "score": round(float(best_score), 2)
            }
        
        return None

if __name__ == "__main__":
    # Quick test
    engine = RagEngine()
    test_query = "Who is the Prime Minister of India?"
    print(f"Query: {test_query} -> {engine.retrieve(test_query)}")
    
    test_query_2 = "Did UNESCO say anything about the national anthem?"
    print(f"Query: {test_query_2} -> {engine.retrieve(test_query_2)}")
