import json
import os
import pickle
import numpy as np
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.base import BaseEstimator, TransformerMixin

class StylisticFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extracts structural and stylistic features from text."""
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        features = []
        for text in X:
            text_str = str(text)
            # Basic counts
            length = len(text_str)
            caps_count = sum(1 for c in text_str if c.isupper())
            excl_count = text_str.count('!')
            ques_count = text_str.count('?')
            
            # Clickbait markers
            clickbait_words = ['SHOCKING', 'BREAKING', 'ALERT', 'EMERGENCY', 'SECRET', 'MUST SEE', 'REVEALED', 'FACTS']
            clickbait_score = sum(1 for word in clickbait_words if word in text_str.upper())
            
            # Emoji detection
            emoji_count = len(re.findall(r'[^\w\s,.]', text_str))
            
            # Normalized features
            features.append([
                caps_count / (length + 1),
                excl_count / (length + 1),
                ques_count / (length + 1),
                clickbait_score / 5.0,
                emoji_count / (length + 1),
                length / 500.0  # Normalized length
            ])
        return np.array(features)

class PropagandaDetector:
    def __init__(self, data_path="seed_data.json", model_path="propaganda_model.pkl"):
        self.data_path = data_path
        self.model_path = model_path
        self.model = None
        
        if os.path.exists(self.model_path):
            self._load_model()
        else:
            self._train_model()

    def _train_model(self):
        if not os.path.exists(self.data_path):
            print(f"Warning: {self.data_path} not found.")
            return

        print("Training new pattern recognition model...")
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        texts = [item["text"] for item in data]
        labels = [1 if item["label"] == "fake" else 0 for item in data]

        from sklearn.pipeline import FeatureUnion
        from sklearn.preprocessing import StandardScaler

        # Feature Union for combining lexical and stylistic features
        features = FeatureUnion([
            ('lexical', TfidfVectorizer(ngram_range=(1, 2), max_features=2500, min_df=2)),
            ('stylistic', Pipeline([
                ('ext', StylisticFeatureExtractor()),
                ('scaler', StandardScaler())
            ]))
        ])

        self.model = Pipeline([
            ('features', features),
            ('clf', RandomForestClassifier(n_estimators=80, max_depth=12, n_jobs=-1, class_weight='balanced', random_state=42))
        ])

        self.model.fit(texts, labels)
        self._save_model()
        print("Model trained and saved.")

    def _save_model(self):
        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)

    def _load_model(self):
        try:
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
            print("Loaded pre-trained pattern recognition model.")
        except Exception as e:
            print(f"Error loading model: {e}. Retraining...")
            self._train_model()

    def _calculate_sensationalism_score(self, text: str) -> float:
        """
        Rule-based sensationalism scorer. Works independently of LIAR training data.
        Catches WhatsApp-style propaganda the ML model never saw.
        """
        score = 0.0
        t = text.strip()
        
        # 1. Repeated exclamation marks (each extra '!' adds a lot of suspicion)
        excl = t.count('!')
        score += min(excl * 0.12, 0.40)

        # 2. Emoji density: flag posts with 2+ emojis
        emoji_count = len(re.findall(r'[\U00010000-\U0010ffff]|[\U0001F300-\U0001F9FF]|[^\w\s,.!?\'\"()\-]', t))
        score += min(emoji_count * 0.08, 0.30)
        
        # 3. ALL-CAPS ratio: check ratio of uppercase letters
        alpha_chars = [c for c in t if c.isalpha()]
        if alpha_chars:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio > 0.4:  # >40% caps = shouting
                score += caps_ratio * 0.50

        # 4. Hard clickbait keywords (high weight) — English
        hard_clickbait = ['SHOCKING', 'BREAKING', 'EMERGENCY ALERT', 'MUST READ', 'FORWARD THIS',
                          'DOCTORS HATE', 'SECRET REVEALED', 'GOVERNMENT HIDING', 'BANNED VIDEO',
                          'SHARE BEFORE DELETED', 'WAKE UP', "WON'T BELIEVE"]
        for kw in hard_clickbait:
            if kw in t.upper():
                score += 0.25

        # 4b. Hindi/Hinglish clickbait keywords (Devanagari)
        hindi_clickbait = ['सावधान', 'खतरा', 'सच्चाई', 'वायरल', 'ध्यान दें', 'सरकार छुपा',
                           'चौंकाने वाला', 'बड़ी खबर', 'तुरंत', 'आगे भेजें', 'शेयर करें']
        for kw in hindi_clickbait:
            if kw in t:
                score += 0.20

        # 4c. Hinglish clickbait keywords (Roman-script)
        hinglish_clickbait = ['dhyan do', 'khatre mein', 'viral karo', 'share karo',
                              'seedha forward', 'sachai', 'sarkar chupa', 'badi khabar',
                              'turant', 'jaldi share', 'aage bhejo', 'sach samne aaya']
        t_lower = t.lower()
        for kw in hinglish_clickbait:
            if kw in t_lower:
                score += 0.18

        # 5. Viral urgency phrases
        urgency = ['forward to', 'share now', 'tell everyone', 'spread the word', 'before it gets deleted']
        for u in urgency:
            if u.lower() in t.lower():
                score += 0.20

        return min(score, 1.0)

    def predict(self, text):
        if not self.model:
            return {"score": 0.5, "label": "Unsure"}

        text_str = str(text)

        # Stage 1: Rule-based sensationalism check (catches WhatsApp-style content)
        sensationalism = self._calculate_sensationalism_score(text_str)

        # Stage 2: ML model score (trained on LIAR political claims dataset)
        ml_prob = self.model.predict_proba([text_str])[0][1]

        # Neutrality dampener — calm, long text with no markers is likely factual
        has_excl = '!' in text_str
        has_emoji = bool(re.findall(r'[^\w\s,.]', text_str))
        if not has_excl and not has_emoji and len(text_str) > 60:
            ml_prob *= 0.55

        # Combine: sensationalism overrides when strong, otherwise blend
        if sensationalism > 0.40:
            prob = 0.6 * sensationalism + 0.4 * ml_prob
        else:
            prob = 0.3 * sensationalism + 0.7 * ml_prob

        prob = min(prob, 1.0)

        if prob > 0.65:
            label = "Highly Suspicious"
        elif prob > 0.30:
            label = "Suspicious"
        else:
            label = "Safe"

        return {
            "score": round(float(prob), 2),
            "label": label
        }

if __name__ == "__main__":
    detector = PropagandaDetector()
    samples = [
        "The Prime Minister shared a neutral update on the budget.",
        "🚨 SHOCKING REVEALED: GOVERNMENT SECRET LEAKED!! CLICK NOW!!! 😱🇮🇳"
    ]
    for s in samples:
        print(f"'{s[:50]}...' -> {detector.predict(s)}")
