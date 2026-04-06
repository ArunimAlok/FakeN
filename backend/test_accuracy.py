from pattern_model import PropagandaDetector

detector = PropagandaDetector()

test_cases = [
    # Should be SAFE (real/neutral)
    ("The Prime Minister of India announced a new infrastructure project in Delhi today.", "safe"),
    ("NASA's Perseverance rover has successfully collected its first rock sample on Mars.", "safe"),
    ("The Federal Reserve kept interest rates steady at its latest meeting.", "safe"),
    ("India's GDP grew by 6.8 percent in the last quarter according to government data.", "safe"),
    ("The Supreme Court ruled on a case involving digital privacy rights today.", "safe"),

    # Should be SUSPICIOUS / HIGHLY SUSPICIOUS (fake/sensational)
    ("🚨 EMERGENCY ALERT: YOU WON'T BELIEVE WHAT THE GOVERNMENT IS HIDING! CLICK NOW!!! 😱🇮🇳", "fake"),
    ("SHOCKING TRUTH!! This simple fruit cures cancer in 3 days but doctors hate it!", "fake"),
    ("BREAKING: Global banks are collapsing, withdraw all your money immediately!!", "fake"),
    ("Forward this to 10 people! The government is secretly poisoning water supplies!!!", "fake"),
    ("Scientists PROVED vaccines cause autism, mainstream media is HIDING this!!!", "fake"),

    # Edge cases - calm-sounding but fake
    ("Statistics show that 95% of people regret getting the latest vaccine according to a hidden study.", "fake"),
    ("A leaked document confirms that the city will be under lockdown starting next Friday.", "fake"),
]

print(f"\n{'Result':<20} {'Score':<6} {'Expected':<10} {'Status'}")
print("-" * 70)

correct = 0
for text, expected in test_cases:
    res = detector.predict(text)
    predicted = "fake" if res["score"] > 0.35 else "safe"
    status = "✓" if predicted == expected else "✗ WRONG"
    if predicted == expected:
        correct += 1
    print(f"{res['label']:<20} {res['score']:<6} {expected:<10} {status}  |  {text[:50]}...")

print(f"\nAccuracy: {correct}/{len(test_cases)} = {round(correct/len(test_cases)*100)}%")
