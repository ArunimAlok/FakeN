"""
propaganda_analyzer.py

Deep propaganda pattern detection using rule-based signals + Gemini LLM.
Detects 12 classic propaganda/manipulation techniques used in fake news and
WhatsApp forwards.
"""

import re
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# Rule-Based Pattern Detectors
# Each returns { matched: bool, confidence: 0.0-1.0, evidence: [str] }
# ──────────────────────────────────────────────────────────────────────────────

FEAR_KEYWORDS = [
    r"\bwill die\b", r"\bdangerous\b", r"\bkill you\b", r"\bpoison\b",
    r"\bdeadly\b", r"\bthreat\b", r"\bcrisis\b", r"\bpanic\b",
    r"\bbeware\b", r"\bwarning\b", r"\balert\b", r"\bemergency\b",
    r"\bcancer\b.*\bcauses\b", r"\b100%\s*fatal\b"
]

URGENCY_KEYWORDS = [
    r"\bforward (this|now|immediately|asap)\b", r"\bshare (this|now|immediately)\b",
    r"\blast chance\b", r"\bonly \d+ hours?\b", r"\btoday only\b",
    r"\bbefore it.s too late\b", r"\bdo it now\b", r"\bright now\b",
    r"\bact immediately\b", r"\burgent\b", r"\bexpires? (today|tonight|soon)\b"
]

AUTHORITY_KEYWORDS = [
    r"\b(WHO|UN|UNESCO|UNICEF|NASA|FBI|CIA|RBI|PM|government)\b.*\b(says?|confirms?|declares?|announces?)\b",
    r"\baccording to (WHO|UN|UNESCO|NASA|government|ministry|supreme court)\b",
    r"\bofficial(ly)?\b.{0,30}\bconf(irm|ess)\b",
    r"\bdoctor(s)?\b.*\bsays?\b", r"\bscientists?\b.*\bprove[sd]?\b"
]

BANDWAGON_KEYWORDS = [
    r"\beveryone (knows?|is|should|must)\b", r"\ball indians?\b",
    r"\bwhole (country|world|nation)\b", r"\bmillions? (of people)?\b",
    r"\bgoing viral\b", r"\btrending\b", r"\b\d{2,} lakh (people|users)\b"
]

EMOTIONAL_MANIPULATION = [
    r"\bnational pride\b", r"\bjay hind\b", r"\bvande mataram\b",
    r"\b(save|protect) (india|hinduism|our culture)\b",
    r"\bthey don.t want you to know\b", r"\bthe truth (they|media) (hide|hides?|is hiding)\b",
    r"\bmainstream media\b.{0,30}\b(lies?|hiding|corrupt)\b",
    r"\bwake up\b", r"\bopen your eyes\b"
]

FALSE_DILEMMA = [
    r"\beither.+or\b", r"\bif you.re not with us.+against us\b",
    r"\bonly two choices?\b", r"\bthere.s no other way\b",
    r"\bno alternative\b"
]

LOADED_LANGUAGE = [
    r"\b(terrorist|radical|extremist|traitor|anti-national|jihadi)\b",
    r"\b(genocide|invasion|occupation|enslavement)\b",
    r"\b(brainwash|indoctrinate|propaganda)\b",
    r"\b(corrupt|scam|fraud)\b.{0,20}\b(government|leader|party)\b"
]

UNVERIFIABLE_SOURCES = [
    r"\bmy (friend|relative|uncle|source)\b.*\btold me\b",
    r"\bI heard (that)?\b", r"\bapparently\b",
    r"\bthey say\b", r"\bword is\b", r"\brumor has it\b",
    r"\bsome sources?\b.*\bclaim\b", r"\bsomeone (told|said)\b"
]

CONSPIRACY_PATTERNS = [
    r"\bdeep state\b", r"\bnew world order\b", r"\bshadow government\b",
    r"\bthey.re hiding\b", r"\bcover.?up\b", r"\bcontrolled by\b",
    r"\b5g\b.{0,30}\b(virus|radiation|chip)\b",
    r"\bvaccine.{0,30}(microchip|bill gates|depopulation)\b",
    r"\bsecret (agenda|plan|plot)\b"
]

CLICKBAIT_PATTERNS = [
    r"\byou won.t believe\b", r"\bshocking\b", r"\bamazing\b",
    r"\bexplosive\b", r"\bbreaking\b.{0,20}\b(revealed|exposed)\b",
    r"\bthe (biggest|worst|best ever)\b", r"\bnobody talks about\b",
    r"\bhidden truth\b", r"\bexclusive\b.*\bsecret\b"
]

STATISTICS_MANIPULATION = [
    r"\b1\d{2}%\b",  # percentages over 100
    r"\b(studies|research) (show|proves?)\b(?!.{0,100}(published|journal|doi))",
    r"\b\d+ (crore|lakh|million) (dead|killed|affected)\b",
    r"\bstatistics?\b.{0,30}\b(prove|show|confirm)\b.{0,30}\bfake\b"
]

FORWARDED_MARKER = [
    r"forwarded\s+(as\s+)?(received|many\s+times?|from\s+\w+)",
    r"please\s+(forward|share)\s+this",
    r"copy\s+paste\s+(and\s+)?forward",
    r"\bFwd:\b", r"\bfw:\b"
]


def _match_patterns(text: str, patterns: list[str]) -> tuple[bool, float, list[str]]:
    """Returns (matched, confidence, evidence snippets)"""
    text_lower = text.lower()
    evidence = []
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            evidence.append(f"…{text[start:end].strip()}…")
    if not evidence:
        return False, 0.0, []
    # Confidence scales with number of matches
    confidence = min(1.0, 0.3 + (len(evidence) * 0.25))
    return True, round(confidence, 2), evidence[:3]  # Cap evidence to 3


def analyze_propaganda_patterns(text: str) -> dict:
    """
    Full rule-based propaganda analysis.
    Returns a structured dict with detected techniques.
    """
    techniques_detected = []
    total_score = 0.0

    checks = [
        ("Fear Appeal", FEAR_KEYWORDS, "Uses fear, danger, or death to manipulate emotions"),
        ("Urgency / Pressure", URGENCY_KEYWORDS, "Creates artificial time pressure to prevent critical thinking"),
        ("False Authority", AUTHORITY_KEYWORDS, "Falsely claims endorsement from official/respected bodies"),
        ("Bandwagon Effect", BANDWAGON_KEYWORDS, "Implies 'everyone believes this' to push conformity"),
        ("Emotional Manipulation", EMOTIONAL_MANIPULATION, "Exploits patriotism, religion, or identity for bias"),
        ("False Dilemma", FALSE_DILEMMA, "Presents only two options when more exist"),
        ("Loaded Language", LOADED_LANGUAGE, "Uses emotionally charged words to inflame rather than inform"),
        ("Unverifiable Source", UNVERIFIABLE_SOURCES, "Claims information from unnamed or untraceable sources"),
        ("Conspiracy Theory", CONSPIRACY_PATTERNS, "Promotes baseless conspiracy narratives"),
        ("Clickbait / Sensationalism", CLICKBAIT_PATTERNS, "Uses exaggerated, shocking language for engagement"),
        ("Statistics Manipulation", STATISTICS_MANIPULATION, "Uses unverified or impossible statistics as 'proof'"),
        ("Forwarded Chain", FORWARDED_MARKER, "Typical 'forward this message' viral chain pattern"),
    ]

    for name, patterns, description in checks:
        matched, confidence, evidence = _match_patterns(text, patterns)
        if matched:
            total_score += confidence
            techniques_detected.append({
                "technique": name,
                "description": description,
                "confidence": confidence,
                "evidence": evidence
            })

    # Normalize overall score to 0-1
    max_possible = len(checks)  # if all triggered at max confidence
    normalized_score = round(min(1.0, total_score / max(1, max_possible * 0.7)), 2)

    return {
        "techniques_found": len(techniques_detected),
        "techniques": sorted(techniques_detected, key=lambda x: x["confidence"], reverse=True),
        "propaganda_risk_score": normalized_score,
        "risk_level": (
            "Critical" if normalized_score > 0.7 else
            "High" if normalized_score > 0.5 else
            "Medium" if normalized_score > 0.3 else
            "Low"
        )
    }


# Secondary LLM deep_analyze merged into llm_service.py to save API limits.
