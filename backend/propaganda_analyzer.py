"""
propaganda_analyzer.py

Lightweight rule-based propaganda signal detector.
Feeds a suspicion context string to the master LLM prompt.
The heavy technique breakdown was removed after migrating to Groq deep analysis.
"""

import re


# ──────────────────────────────────────────────────────────────────────────────
# Signal Keyword Groups
# ──────────────────────────────────────────────────────────────────────────────

_FEAR = [
    r"\bwill die\b", r"\bdangerous\b", r"\bpoison\b", r"\bdeadly\b",
    r"\bcrisis\b", r"\bpanic\b", r"\bbeware\b", r"\bemergency\b",
    # Hindi (Devanagari)
    r"खतरा", r"मर जाएंगे", r"डरना", r"मृत्यु", r"जहर", r"सावधान",
    # Hinglish (Roman-script)
    r"\bkhatra\b", r"\bkhatarnak\b", r"\bmar jayenge\b", r"\bdarao\b", r"\bmaut\b",
]

_URGENCY = [
    r"\bforward (this|now|immediately)\b", r"\bshare (this|now)\b",
    r"\blast chance\b", r"\bbefore it.s too late\b", r"\burgent\b",
    # Hindi (Devanagari)
    r"आगे भेजें", r"तुरंत", r"अभी शेयर", r"उठाओ",
    # Hinglish
    r"\babhi share karo\b", r"\bjaldi\b", r"\bturant\b", r"\baage bhejo\b",
]

_CONSPIRACY = [
    r"\bdeep state\b", r"\bcover.?up\b", r"\bthey.re hiding\b",
    r"\bsecret (agenda|plan|plot)\b", r"\bwake up\b", r"\bopen your eyes\b",
    # Hindi (Devanagari)
    r"सरकार छुपा", r"सच्चाई छुपाई", r"साजिश", r"गुप्त योजना",
    # Hinglish
    r"\bsarkar chupa\b", r"\bsachai chupa\b", r"\bsaajish\b", r"\bankhein kholo\b",
]

_CLICKBAIT = [
    r"\byou won.t believe\b", r"\bshocking\b", r"\bhidden truth\b",
    r"\bexplosive\b", r"\bbreaking\b.{0,20}\b(revealed|exposed)\b",
    # Hindi (Devanagari)
    r"चौंकाने वाला", r"बड़ी खबर", r"सच्चाई सामने",
    # Hinglish
    r"\bchonkane wala\b", r"\bbadi khabar\b", r"\bsach samne aaya\b",
]

_FORWARDED = [
    r"forwarded\s+(as\s+)?(received|many\s+times?)",
    r"please\s+(forward|share)\s+this",
    r"\bFwd:\b", r"\bfw:\b",
    # Hindi (Devanagari)
    r"फॉरवर्ड किया", r"आगे भेजा",
    # Hinglish
    r"\bforward kiya\b", r"\bbahut logo ne bheja\b", r"\bsabko bhejo\b",
]

_UNVERIFIABLE = [
    r"\bmy (friend|relative|uncle|source)\b.*\btold me\b",
    r"\bI heard (that)?\b", r"\bapparently\b",
    r"\bthey say\b", r"\bword is\b", r"\brumor has it\b",
    # Hindi (Devanagari)
    r"मेरे दोस्त ने बताया", r"सुना है", r"अफवाह",
    # Hinglish
    r"\bmere dost ne bataya\b", r"\bsuna hai\b", r"\bkisi ne bola\b", r"\bafwaah\b",
]


def analyze_propaganda_patterns(text: str) -> dict:
    """
    Fast rule-based scan. Returns a minimal dict that:
    - feeds into the LLM prompt as context
    - is merged into the API response for completeness
    """
    text_lower = text.lower()
    signals = []

    for group_name, patterns in [
        ("Fear Appeal", _FEAR),
        ("Urgency/Pressure", _URGENCY),
        ("Conspiracy", _CONSPIRACY),
        ("Clickbait", _CLICKBAIT),
        ("Forwarded Chain", _FORWARDED),
        ("Unverifiable Source", _UNVERIFIABLE),
    ]:
        for p in patterns:
            if re.search(p, text_lower):
                signals.append(group_name)
                break  # only count each group once

    score = round(min(1.0, len(signals) * 0.18), 2)

    return {
        "signals_detected": signals,
        "signal_count": len(signals),
        "propaganda_risk_score": score,
        "risk_level": (
            "High" if score > 0.5 else
            "Medium" if score > 0.25 else
            "Low"
        ),
    }
