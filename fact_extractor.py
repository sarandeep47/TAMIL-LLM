"""
fact_extractor.py — Personal fact extraction for the Tamil chatbot.

Architecture
------------
Two-layer extraction (fastest first):
  1. Deterministic regex — covers the most common patterns for all three
     dialects (Tamil script, Tanglish, English) with no network calls.
  2. Ollama LLM — fallback for phrasings the regex cannot handle.

Supported canonical fact keys
------------------------------
identity    : user_name, user_location
work        : user_workplace, user_job_title
education   : user_school, user_field_of_study
learning    : user_learning
interest    : user_interest
skill       : user_skill
goal        : user_goal
preference  : user_language_preference, user_response_style

Design rules
------------
* Personal-statement heuristic runs first; questions are skipped silently.
* Regex runs before the LLM — Ollama is never called when regex succeeds.
* AI extractions never overwrite manual facts.
* Regex extractions never overwrite manual facts.
* A higher-confidence regex can overwrite a lower-confidence AI fact.
* Values that are empty, null-like, or below minimum length are discarded.
* Technical terms (Python, AI Engineer) are preserved as-is.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from memory_db import get_memory, save_memory
from tanglish_understanding import understand_tanglish

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "llama3.2:3b"

logger = logging.getLogger(__name__)

# ── Canonical key → category ────────────────────────────────────────────────

KNOWN_KEYS: dict[str, str] = {
    "user_name":                "identity",
    "user_location":            "identity",
    "user_workplace":           "work",
    "user_job_title":           "work",
    "user_school":              "education",
    # Pseudo-keys used internally during regex extraction only;
    # they are normalized to user_school before writing to the DB.
    "user_school_past":         "education",   # padichen / studied at (past)
    "user_school_current":      "education",   # padikuren / am studying (present)
    "user_field_of_study":      "education",
    "user_degree":              "education",   # BE, BTech, MSc, etc.
    "user_learning":            "learning",
    "user_interest":            "interest",
    "user_skill":               "skill",
    "user_goal":                "goal",
    "user_language_preference": "preference",
    "user_response_style":      "preference",
}

# ── Data model ───────────────────────────────────────────────────────────────

_BAD_VALUES = {
    "unknown", "n/a", "none", "null", "", "yes", "no",
    "enna", "what", "something", "anything", "x", "y",
}


@dataclass
class Fact:
    key:              str
    value:            str
    category:         str
    confidence:       float = 0.75
    source:           str   = "ai"
    education_status: str | None = None  # 'current' | 'past' | None

    def is_valid(self) -> bool:
        if not self.key or not self.value:
            return False
        v = self.value.strip()
        if len(v) < 2:
            return False
        if v.lower() in _BAD_VALUES:
            return False
        if not (0.0 <= self.confidence <= 1.0):
            return False
        return True


# ── Utility ──────────────────────────────────────────────────────────────────

def _has_tamil_script(text: str) -> bool:
    return any("\u0B80" <= ch <= "\u0BFF" for ch in text)


# ── Personal-statement heuristics ────────────────────────────────────────────
#
# Goal: filter OUT questions and unrelated messages BEFORE doing any work.
# Separate paths for Tamil-script vs ASCII to avoid false positives.

# Substrings that indicate a Tamil-script PERSONAL STATEMENT
_TAMIL_STMT_SUBSTRS: list[str] = [
    "என் பெயர் ",          # en peyar — "my name is"
    "என்னுடைய பெயர் ",
    "என் இலக்கு ",          # en ilakku — "my goal"
    "என்னுடைய இலக்கு ",
    "ஆக வேண்டும்",          # aaka vendum — "want to become"
    "கற்றுக்கொண்டு இருக்",  # katrukkandu irukk — "am learning"
    "கற்கிறேன்",             # kathukiren — "I learn"
    "படிக்கிறேன்",           # padikkiren — "I study" (present)
    "படித்தேன்",             # padittaen — "I studied" (past)
    "வேலை செய்கிறேன்",      # work doing
    "நிறுவனத்தில் வேலை",   # at company, work
    "நான் வசிக்கிறேன்",
    "எனக்கு பிடிக்கும்",
    "எனக்குப் பிடிக்கும்",
    "என் திறமை",
    # School statements (Tamil)
    "கல்லூரியில் படிக்கிறேன்",  # currently studying at college
    "கல்லூரியில் படித்தேன்",    # studied at college (past)
    "பள்ளியில் படித்தேன்",      # studied at school (past)
]

# Substrings that indicate a Tamil-script QUESTION — exact match needed
# (must end with ? to avoid blocking mixed statements that share words)
_TAMIL_QUESTION_SUBSTRS: list[str] = [
    "என்ன?",
    "எங்கே?",
    "எப்படி?",
    "யார்?",
    "எது?",
    "எந்த?",
]

# English/Tanglish personal-statement patterns
_STMT_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bmy name is\s+\S",
        r"\ben peyar\s+\S",
        r"\ben peru\s+\S",
        r"\bmy goal is\b",
        r"\ben goal\s+\S",
        r"\bi want to become\b",
        r"\ben goal\s+\w+\s+aaganum\b",
        r"\bi work (at|for|in)\b",
        r"\bi('m| am) working (at|for|in)\b",
        r"\bmy (job|workplace|employer|company) is\b",
        r"\bnaan\s+\S+\s+(?:la\s+)?work\s+pan",          # naan X la work panren
        r"\bi('m| am) (learning|studying)\b",
        r"\bnaan\s+\w+\s+(?:kathukittu|kathukkitu|kathukkiren|kathukiren|padikiren|padikittu)\b",
        r"\bi (like|love|enjoy)\b",
        r"\bmy (hobby|interest|passion)\b",
        r"\benakku\s+\w+\s*pudikkum\b",
        r"\bi (can|know how to)\b",
        r"\bmy skill\b",
        r"\bi live in\b",
        r"\bi('m| am) (from|based in)\b",
        r"\bi prefer\b",
        # School — past tense (padichen / studied at)
        r"\b(?:naa|naan)\s+[A-Za-z].{1,60}?\s+(?:la|il|le)\s+padichen\b",
        r"\b(?:naa|naan)\s+[A-Za-z].{1,60}?\s+padichen\b",
        r"\bi studied at\b",
        r"\bi went to (?:college|school|university)\b",
        r"\bmy (?:college|school) is\b",
        # School — present tense (padikuren / am studying at)
        r"\b(?:naa|naan)\s+[A-Za-z].{1,60}?\s+(?:la|il|le)\s+padikuren\b",
        r"\b(?:naa|naan)\s+[A-Za-z].{1,60}?\s+padikuren\b",
        r"\bi(?:'m| am) studying at\b",
        r"\bi study at\b",
        # Degree (must have explicit keywords to avoid false positives with field of study)
        r"\bi have\s+(?:a\s+)?[A-Z]{2,8}\s+(?:degree|qualification)\b",
        r"\bi(?:'m| am) (?:doing|pursuing)\s+(?:my\s+)?[A-Z]{2,8}\s+degree\b",
    ]
]

# English/Tanglish question patterns — skip extraction
_QUESTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\?$",
        r"^(what|where|who|when|how|why|do|does|did|can|could|would|should)\b",
    ]
]

_MIN_LEN = 8


def _looks_like_personal_statement(message: str) -> bool:
    """
    Returns True only when the message clearly contains a personal fact
    statement (not a question, not a command, not too short).
    
    EXTRACTION GATE: Blocks questions and recalls before they reach Ollama.
    """
    s = message.strip()
    if len(s) < _MIN_LEN:
        return False
    if s.startswith("/"):
        return False

    # Handle Tamil script messages first
    if _has_tamil_script(s):
        # A trailing '?' always means it's a question — skip extraction
        if s.endswith("?"):
            return False
        # Also skip on known Tamil question-ending words
        if any(q in s for q in _TAMIL_QUESTION_SUBSTRS):
            return False
        # Tamil statements that match patterns should be extracted
        return any(sub in s for sub in _TAMIL_STMT_SUBSTRS)

    # For non-Tamil (Tanglish/English), first check if it's a QUESTION or RECALL
    # These should NOT be extracted. Only statements get facts extracted.
    tanglish_intent = understand_tanglish(s)
    
    # EXTRACTION GATE: Block questions, recalls, greetings
    if tanglish_intent.sentence_type in ('question', 'recall', 'greeting'):
        return False
    
    # Also check for explicit question markers
    if any(p.search(s) for p in _QUESTION_PATTERNS):
        return False
    
    # Try pattern matching for statement detection
    if any(p.search(s) for p in _STMT_PATTERNS):
        return True
    
    # Fallback: use tanglish_understanding to classify
    # This catches patterns like "naa Madurai la iruken" that don't match regex patterns
    if (tanglish_intent.sentence_type == 'statement' and 
        tanglish_intent.is_personal_fact() and
        tanglish_intent.confidence >= 0.7):
        return True
    
    return False


# ── Known Tamil name → English transliteration ───────────────────────────────

_TAMIL_NAME_MAP: dict[str, str] = {
    "சரண்தீப்":   "Sarandeep",
    "அருண்":      "Arun",
    "ராம்":       "Ram",
    "கார்த்திக்": "Karthik",
    "பிரியா":     "Priya",
    "தேவி":       "Devi",
    "வேல்":       "Vel",
    "முரளி":      "Murali",
    "சுரேஷ்":     "Suresh",
    "கவிதா":      "Kavitha",
    "அனிதா":      "Anitha",
    "சந்தியா":    "Sandhya",
    "வினோத்":     "Vinoth",
    "தினேஷ்":     "Dinesh",
    "மணி":        "Mani",
}

# ── Tamil-script regex patterns ───────────────────────────────────────────────

_TAMIL_REGEXES: list[tuple[str, re.Pattern]] = [
    # Name: "என் பெயர் X" / "என்னுடைய பெயர் X"
    ("user_name", re.compile(
        r"(?:என் பெயர்|என்னுடைய பெயர்)\s+(.+?)(?:\s*[.!])?$"
    )),
    # Goal: "என் இலக்கு X ஆக வேண்டும்" / "என்னுடைய இலக்கு X ஆக வேண்டும்"
    ("user_goal", re.compile(
        r"(?:என் இலக்கு|என்னுடைய இலக்கு)\s+(.+?)(?:\s*ஆக வேண்டும்|[.!])?$"
    )),
    # Learning: "நான் X கற்றுக்கொண்டு இருக்கிறேன்" / "X கற்கிறேன்" / "X படிக்கிறேன்"
    # Captures the subject (may be ASCII like "Python")
    ("user_learning", re.compile(
        r"(?:நான்\s+)?([A-Za-z][\w+#.-]{0,30}|[\u0B80-\u0BFF]+)\s+"
        r"(?:கற்றுக்கொண்டு இருக்கிறேன்|கற்கிறேன்)"
    )),
    # School (Tamil present): "நான் X கல்லூரியில் படிக்கிறேன்"
    ("user_school_current", re.compile(
        r"நான்\s+([A-Za-z][\w\s.,\-]{1,60}?)\s+(?:கல்லூரியில்|பள்ளியில்)\s+படிக்கிறேன்"
    )),
    # School (Tamil past): "நான் X கல்லூரியில் படித்தேன்"
    ("user_school_past", re.compile(
        r"நான்\s+([A-Za-z][\w\s.,\-]{1,60}?)\s+(?:கல்லூரியில்|பள்ளியில்)\s+படித்தேன்"
    )),
    # Workplace: "நான் X நிறுவனத்தில் வேலை செய்கிறேன்" / "நான் X-ல் வேலை செய்கிறேன்"
    ("user_workplace", re.compile(
        r"நான்\s+([A-Za-z][\w\s&.,\-]{1,60}?)(?:\s+(?:நிறுவனத்தில்|ல்|லே|இல்)\s+)?வேலை செய்கிறேன்"
    )),
]

# ── English/Tanglish regex patterns ──────────────────────────────────────────

_ASCII_REGEXES: list[tuple[str, re.Pattern]] = [
    # Name
    ("user_name", re.compile(
        r"(?:my name is|en peyar|en peru|ennoda peyar|ennoda peru)\s+([A-Za-z][A-Za-z .'`\-]{1,40})",
        re.IGNORECASE,
    )),
    # Goal (English)
    ("user_goal", re.compile(
        r"(?:my goal is(?:\s+to\s+become)?|i want to become)\s+(.+?)[\.\!\?]?$",
        re.IGNORECASE,
    )),
    # Goal (Tanglish): "En goal AI Engineer aaganum"
    ("user_goal", re.compile(
        r"en goal\s+(.+?)\s+aaganum\b",
        re.IGNORECASE,
    )),
    # Goal (Tanglish short): "En goal X" where X is at least 2 words or has capital
    ("user_goal", re.compile(
        r"en goal\s+([A-Z][A-Za-z]+(?:\s+[A-Za-z]+)*)",
    )),
    # Field of Study — PAST tense (padichen)
    # Pattern 1: "naa CSE padichen college la" — field before "padichen college"
    ("user_field_of_study", re.compile(
        r"(?:naa|naan)\s+([a-z]+(?:\s+[a-z]+)?)\s+padichen\s+college\b",
        re.IGNORECASE,
    )),
    ("user_field_of_study", re.compile(
        r"(?:naa|naan)\s+([a-z]+(?:\s+[a-z]+)?)\s+padichen\s+(?:la|il|le)\s+college\b",
        re.IGNORECASE,
    )),
    # Pattern 2: Alternative word order - "naa college la CSE padichen"
    # (field after postposition+college keyword)
    ("user_field_of_study", re.compile(
        r"(?:naa|naan)\s+college\s+(?:la|il|le)\s+([a-z]+(?:\s+[a-z]+)?)\s+padichen\b",
        re.IGNORECASE,
    )),
    # Field of Study — PRESENT tense (padikuren)
    # Pattern 1: "naa CSE padikuren college la"
    ("user_field_of_study", re.compile(
        r"(?:naa|naan)\s+([a-z]+(?:\s+[a-z]+)?)\s+padikuren\s+college\b",
        re.IGNORECASE,
    )),
    ("user_field_of_study", re.compile(
        r"(?:naa|naan)\s+([a-z]+(?:\s+[a-z]+)?)\s+padikuren\s+(?:la|il|le)\s+college\b",
        re.IGNORECASE,
    )),
    # Pattern 2: Alternative word order - "naa college la CSE padikuren"
    ("user_field_of_study", re.compile(
        r"(?:naa|naan)\s+college\s+(?:la|il|le)\s+([a-z]+(?:\s+[a-z]+)?)\s+padikuren\b",
        re.IGNORECASE,
    )),
    # School — PAST tense (padichen = I studied)
    # Must come AFTER field-of-study to avoid mis-classifying field as school
    # Only match words with UPPERCASE FIRST LETTER (institutions)
    # Require 4+ chars to avoid matching 3-letter field acronyms like "CSE"
    # Pattern 1: "naa <Institution> la padichen" (with postposition + la/il/le)
    ("user_school_past", re.compile(
        r"(?:naa|naan)\s+(?=[A-Z])([A-Za-z][\w\s.,\-]{2,}?)\s+(?:la|il|le)\s+padichen\b",
    )),
    # Pattern 2: "naa <Institution> padichen" (without postposition, requires full name)
    ("user_school_past", re.compile(
        r"(?:naa|naan)\s+(?=[A-Z])([A-Za-z][\w\s.,\-]{3,})\s+padichen\b",
    )),
    ("user_school_past", re.compile(
        r"i\s+studied\s+at\s+([A-Za-z][\w\s.,&\-]{1,60}?)(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    ("user_school_past", re.compile(
        r"i\s+went\s+to\s+(?:college|school|university)\s+(?:at\s+)?([A-Za-z][\w\s.,&\-]{1,60}?)(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    ("user_school_past", re.compile(
        r"my\s+(?:college|school)\s+(?:is|was)\s+([A-Za-z][\w\s.,&\-]{1,60}?)(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    # School — PRESENT tense (padikuren = I am studying)
    # Capture college name, stopping at postpositions (la, il, le)
    # School (Tanglish current) - require 4+ chars to avoid matching 3-letter field acronyms like "CSE"
    # Pattern 1: "naa <Institution> la padikuren" (with postposition + la/il/le)
    ("user_school_current", re.compile(
        r"(?:naa|naan)\s+(?=[A-Z])([A-Za-z][\w\s.,\-]{2,}?)\s+(?:la|il|le)\s+padikuren\b",
    )),
    # Pattern 2: "naa <Institution> padikuren" (without postposition, requires full name)
    ("user_school_current", re.compile(
        r"(?:naa|naan)\s+(?=[A-Z])([A-Za-z][\w\s.,\-]{3,})\s+padikuren\b",
    )),
    # "I'm studying at X" — must come BEFORE the bare "i'm studying X" learning pattern
    ("user_school_current", re.compile(
        r"i(?:'m| am)\s+studying\s+at\s+([A-Za-z][\w\s.,&\-]{1,60}?)(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    ("user_school_current", re.compile(
        r"i\s+study\s+at\s+([A-Za-z][\w\s.,&\-]{1,60}?)(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    # Learning (Tanglish verb forms: padikiren = learning, NOT padikuren = studying at college)
    # Explicitly exclude padikuren to avoid confusion
    ("user_learning", re.compile(
        r"naan\s+([A-Za-z][\w+#.-]{0,30})\s+(?:kathukittu|kathukkitu|kathukkiren|kathukiren|padikiren|padikittu)\b",
        re.IGNORECASE,
    )),
    # Learning (English) — must NOT match "studying at" (that's school)
    # Only match "learning X" or "studying X" where X is not "at"
    ("user_learning", re.compile(
        r"i(?:'m| am)\s+learning\s+([A-Za-z][\w+# .-]{1,40})(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    # Studying without "at" — for cases like "I'm studying Python"
    ("user_learning", re.compile(
        r"i(?:'m| am)\s+studying\s+(?!at\s)([A-Za-z][\w+# .-]{1,40})(?:[.!,]|$)",
        re.IGNORECASE,
    )),
    # Learning (Tanglish: "naan X padikiren" — note: padikiren not padikuren)
    ("user_learning", re.compile(
        r"naan\s+([A-Za-z][\w+#.-]{0,30})\s+padikiren\b",
        re.IGNORECASE,
    )),
    # Degree (English) — must have explicit keywords like "degree", "have", "doing", etc.
    ("user_degree", re.compile(
        r"i\s+(?:have|got|completed)\s+(?:a\s+)?(?:my\s+)?([A-Z]{2,10})\s+(?:degree|qualification|degreee?)",
        re.IGNORECASE,
    )),
    # Degree (English) — "I'm doing my BE"
    ("user_degree", re.compile(
        r"i(?:'m| am)\s+(?:doing|pursuing|working on)\s+(?:my\s+)?([A-Z]{2,10})\s+(?:degree)?",
        re.IGNORECASE,
    )),
    # Degree (Tanglish) — explicit degree keywords only, NOT "padichen" (which is for field-of-study)
    ("user_degree", re.compile(
        r"(?:naa|na|naan)\s+([A-Z]{2,10})\s+(?:degree|qualification)\b",
        re.IGNORECASE,
    )),
    # Workplace (English)
    ("user_workplace", re.compile(
        r"i\s+(?:work|am working)\s+(?:at|for|in)\s+([A-Za-z][\w\s&.,\-]{1,60}?)(?:\s*[.!,]|$)",
        re.IGNORECASE,
    )),
    # Workplace (Tanglish): "Naan X la work panren"
    ("user_workplace", re.compile(
        r"naan\s+([A-Za-z][\w\s&.,\-]{1,60}?)\s+la\s+work\s+pan",
        re.IGNORECASE,
    )),
    # Location
    ("user_location", re.compile(
        r"i\s+(?:live in|am from|am based in)\s+([A-Za-z][A-Za-z ,\-]{1,40}?)(?:[.!,]|$)",
        re.IGNORECASE,
    )),
]

# Words that should not be treated as extracted values
_CLIP_WORDS = re.compile(
    r"\s+(?:and|but|because|since|i |my |en |naan )\b",
    re.IGNORECASE,
)


def _clip_value(raw: str) -> str:
    """Remove trailing filler and trim."""
    raw = raw.strip().rstrip(".!?,;")
    # Stop at obvious conjunctions
    m = _CLIP_WORDS.search(raw)
    if m:
        raw = raw[:m.start()]
    return raw.strip()


def _normalize_school_key(pseudo_key: str) -> tuple[str, str | None]:
    """
    Convert a school pseudo-key to the canonical DB key and education_status.
    Returns (canonical_key, education_status).
    """
    if pseudo_key == "user_school_current":
        return "user_school", "current"
    if pseudo_key == "user_school_past":
        return "user_school", "past"
    return pseudo_key, None


def _extract_by_regex(message: str) -> list[Fact]:
    """
    Deterministic regex extraction — no network calls.
    Returns validated Fact objects or [].
    """
    s = message.strip()
    facts: list[Fact] = []

    if _has_tamil_script(s):
        for key, pattern in _TAMIL_REGEXES:
            m = pattern.search(s)
            if not m:
                continue
            raw = m.group(1).strip()

            if key == "user_name":
                # Prefer known map; fall back to raw if it contains ASCII
                value = _TAMIL_NAME_MAP.get(raw)
                if not value:
                    if re.search(r"[A-Za-z]", raw):
                        value = raw
                    else:
                        value = raw   # store Tamil as-is; user can correct later
                conf = 0.97 if value in _TAMIL_NAME_MAP.values() else 0.85
                facts.append(Fact(key=key, value=value,
                                  category=KNOWN_KEYS[key],
                                  confidence=conf, source="regex"))
                break  # only one name per message

            elif key == "user_goal":
                value = re.sub(r"\s*ஆக வேண்டும்.*$", "", raw).strip()
                value = _clip_value(value)
                if value:
                    facts.append(Fact(key=key, value=value,
                                      category=KNOWN_KEYS[key],
                                      confidence=0.95, source="regex"))
                break

            elif key == "user_learning":
                value = _clip_value(raw)
                if value and len(value) > 1:
                    facts.append(Fact(key=key, value=value,
                                      category=KNOWN_KEYS[key],
                                      confidence=0.93, source="regex"))
                break

            elif key in ("user_school_current", "user_school_past"):
                value = _clip_value(raw)
                if value and len(value) > 1:
                    canon_key, edu_status = _normalize_school_key(key)
                    facts.append(Fact(key=canon_key, value=value,
                                      category="education",
                                      confidence=0.93, source="regex",
                                      education_status=edu_status))
                break

            elif key == "user_workplace":
                value = _clip_value(raw)
                if value and len(value) > 1:
                    facts.append(Fact(key=key, value=value,
                                      category=KNOWN_KEYS[key],
                                      confidence=0.93, source="regex"))
                break

    else:
        # Track which canonical keys we've already extracted to avoid duplicates
        extracted_keys = set()
        for key, pattern in _ASCII_REGEXES:
            m = pattern.search(s)
            if not m:
                continue
            
            # Determine canonical key (for school, normalize pseudo-key)
            if key in ("user_school_current", "user_school_past"):
                canon_key, edu_status = _normalize_school_key(key)
            else:
                canon_key = key
                edu_status = None
            
            # Skip if we already extracted this canonical key
            if canon_key in extracted_keys:
                continue
            
            raw = m.group(1)
            value = _clip_value(raw)
            if not value or len(value) < 2:
                continue
            
            if key in ("user_school_current", "user_school_past"):
                facts.append(Fact(key=canon_key, value=value,
                                  category="education",
                                  confidence=0.97, source="regex",
                                  education_status=edu_status))
            else:
                facts.append(Fact(key=key, value=value,
                                  category=KNOWN_KEYS[key],
                                  confidence=0.97, source="regex"))
            
            extracted_keys.add(canon_key)

    # If regex found nothing but the message looks like a personal fact statement,
    # try tanglish_understanding as a final fallback
    if not facts:
        tanglish_intent = understand_tanglish(message)
        
        # Only extract if it's a statement about a personal fact with high confidence
        if (tanglish_intent.sentence_type == 'statement' and
            tanglish_intent.is_personal_fact() and
            tanglish_intent.confidence >= 0.7 and
            tanglish_intent.memory_key and
            tanglish_intent.entities.get('value')):
            
            # Additional gate: don't extract field_of_study without college context
            # "naa cse padichen" is ambiguous, require college keyword
            if (tanglish_intent.memory_key == 'user_field_of_study' and
                'college' not in message.lower() and
                'school' not in message.lower() and
                'university' not in message.lower()):
                # Skip field_of_study extraction without college context
                pass
            else:
                value = tanglish_intent.entities['value']
                # Ensure value is valid
                if value and len(value) > 1 and value.lower() not in _BAD_VALUES:
                    facts.append(Fact(
                        key=tanglish_intent.memory_key,
                        value=value,
                        category=KNOWN_KEYS.get(tanglish_intent.memory_key, "other"),
                        confidence=min(tanglish_intent.confidence, 0.85),  # Slightly lower than regex
                        source="tanglish"
                    ))
    
    return [f for f in facts if f.is_valid()]


# ── Ollama LLM extraction (fallback) ────────────────────────────────────────

_EXTRACTION_PROMPT = """\
You are a personal-fact extractor. Given a user message, find only explicitly
stated personal facts and return them as JSON.

Return exactly this shape (and nothing else):
{"facts": [{"key": "KEY", "value": "VALUE", "confidence": FLOAT}]}

Allowed keys:
  user_name, user_location, user_workplace, user_job_title,
  user_school, user_field_of_study, user_learning, user_interest,
  user_skill, user_goal, user_language_preference, user_response_style

Rules:
1. Return {"facts": []} if no personal fact is clearly stated.
2. NEVER guess, infer, or hallucinate.
3. Return {"facts": []} for ANY question.
4. Keep values concise — the thing itself, not the whole sentence.
5. Preserve technical terms in English (Python, AI Engineer, Madurai, etc.).
6. No markdown, no explanations — only the JSON object.

Examples:
  "My name is Sarandeep"
  → {"facts": [{"key": "user_name", "value": "Sarandeep", "confidence": 0.98}]}

  "என் பெயர் சரண்தீப்"
  → {"facts": [{"key": "user_name", "value": "Sarandeep", "confidence": 0.95}]}

  "என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்"
  → {"facts": [{"key": "user_goal", "value": "AI Engineer", "confidence": 0.95}]}

  "Naan Python kathukittu irukken"
  → {"facts": [{"key": "user_learning", "value": "Python", "confidence": 0.92}]}

  "I work at Tarcin Robotics"
  → {"facts": [{"key": "user_workplace", "value": "Tarcin Robotics", "confidence": 0.97}]}

  "Naan Tarcin Robotics la work panren"
  → {"facts": [{"key": "user_workplace", "value": "Tarcin Robotics", "confidence": 0.93}]}

  "En goal AI Engineer aaganum"
  → {"facts": [{"key": "user_goal", "value": "AI Engineer", "confidence": 0.93}]}

  "En goal enna?" → {"facts": []}
  "What am I learning?" → {"facts": []}
"""


def _call_ollama(message: str) -> list[dict[str, Any]]:
    """Call Ollama extraction endpoint. Returns [] on any failure."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": _EXTRACTION_PROMPT},
                    {"role": "user",   "content": message},
                ],
                "stream": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()

        # Strip markdown fences
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        # Extract the first JSON object in case the model added prose
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)

        data = json.loads(raw)
        return data.get("facts", [])

    except requests.exceptions.ConnectionError:
        logger.debug("Ollama not reachable for fact extraction.")
        return []
    except requests.exceptions.Timeout:
        logger.debug("Ollama timed out for fact extraction.")
        return []
    except requests.exceptions.RequestException as e:
        logger.debug("Ollama request error: %s", e)
        return []
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.debug("Bad JSON from Ollama fact extractor: %s", e)
        return []


def _validate(raw_facts: list[dict]) -> list[Fact]:
    """Validate raw dicts from Ollama into Fact objects."""
    valid: list[Fact] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip().lower()
        value = str(item.get("value", "")).strip()
        try:
            conf = float(item.get("confidence", 0.75))
        except (TypeError, ValueError):
            conf = 0.75

        if key not in KNOWN_KEYS:
            continue

        f = Fact(key=key, value=value, category=KNOWN_KEYS[key],
                 confidence=conf, source="ai")
        if f.is_valid():
            valid.append(f)
    return valid


# Alias used by tests and external callers; _validate was the original
# internal name before it was documented as part of the public helper API.
_validate_raw_facts = _validate


# ── Persistence ──────────────────────────────────────────────────────────────

def _get_db_row(key: str) -> dict | None:
    """Read the full row for a key (used for confidence gating)."""
    import sqlite3
    from memory_db import DB_PATH
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT fact_value, source, confidence FROM memories WHERE fact_key = ?",
            (key,),
        ).fetchone()
    if row is None:
        return None
    return {"value": row[0], "source": row[1], "confidence": row[2]}


def _persist(facts: list[Fact]) -> list[Fact]:
    """
    Persist facts, applying these write rules:
    - Manual facts are NEVER overwritten by regex or AI.
    - AI facts are only written if confidence is higher than existing.
    - Regex facts can overwrite AI facts (regex > AI in trust hierarchy).
    - education_status is stored alongside user_school facts.
    """
    written: list[Fact] = []
    for fact in facts:
        existing = _get_db_row(fact.key)
        if existing:
            ex_src  = existing.get("source", "manual")
            ex_conf = existing.get("confidence", 1.0)
            if ex_src == "manual":
                logger.debug("Skipping overwrite of manual fact '%s'.", fact.key)
                continue
            # Regex can overwrite AI; AI cannot overwrite regex or itself at >= confidence
            if fact.source == "ai" and ex_conf >= fact.confidence:
                logger.debug(
                    "Skipping AI update of '%s': existing conf %.2f >= %.2f.",
                    fact.key, ex_conf, fact.confidence,
                )
                continue

        save_memory(
            fact_key=fact.key,
            fact_value=fact.value,
            category=fact.category,
            confidence=fact.confidence,
            source=fact.source,
            education_status=fact.education_status,
        )
        written.append(fact)
        logger.debug("Saved fact: %s = %s (src=%s, conf=%.2f, edu=%s)",
                     fact.key, fact.value, fact.source, fact.confidence,
                     fact.education_status)
    return written


# ── Public API ────────────────────────────────────────────────────────────────

def extract_facts(message: str) -> list[Fact]:
    """
    Main entry point. Returns facts that were actually written to the DB.

    Pipeline:
      1. Heuristic gate — skip if not a personal statement.
      2. Regex extraction — deterministic, no network.
      3. If regex found nothing → Ollama LLM extraction.
      4. Validate → persist → return written facts.
    """
    if not _looks_like_personal_statement(message):
        return []

    regex_facts = _extract_by_regex(message)
    if regex_facts:
        return _persist(regex_facts)

    # LLM fallback
    raw = _call_ollama(message)
    if not raw:
        return []
    validated = _validate(raw)
    if not validated:
        return []
    return _persist(validated)


def extract_facts_dry_run(message: str) -> list[Fact]:
    """Like extract_facts() but does NOT write to the DB. For testing."""
    if not _looks_like_personal_statement(message):
        return []
    regex_facts = _extract_by_regex(message)
    if regex_facts:
        return regex_facts
    raw = _call_ollama(message)
    return _validate(raw)
