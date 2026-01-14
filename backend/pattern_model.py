import json
import os
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

class PropagandaDetector:
    def __init__(self, data_path="seed_data.json"):
        self.data_path = data_path
        self.model = None
        self._train_model()

    def _train_model(self):
        # Load data
        if not os.path.exists(self.data_path):
            print(f"Warning: {self.data_path} not found. Model will be uninitialized.")
            return

        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        texts = [item["text"] for item in data]
        labels = [1 if item["label"] == "fake" else 0 for item in data]

        # Create Protocol
        # TF-IDF -> Logistic Regression
        self.model = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2))), # 1-2 ngrams to catch phrases like "forward to"
            ('clf', LogisticRegression(solver='liblinear'))
        ])

        self.model.fit(texts, labels)
        print("Model trained on seed data.")

    def predict(self, text):
        if not self.model:
            return {"score": 0.5, "label": "Unsure (Model not loaded)"}
        
        # Probability of class 1 (fake)
        prob = self.model.predict_proba([text])[0][1]
        
        label = "Safe"
        if prob > 0.7:
            label = "Highly Suspicious"
        elif prob > 0.4:
            label = "Suspicious"
        
        return {
            "score": round(prob, 2),
            "label": label
        }

if __name__ == "__main__":
    # Quick test
    detector = PropagandaDetector()
    sample = "UNESCO declared India best country 🇮🇳"
    print(f"Sample: '{sample}' -> {detector.predict(sample)}")
