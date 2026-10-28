"""
chat_memory.py — Deterministic fact retrieval for the Tamil chatbot.

This is the SINGLE source of truth for reading personal facts.
chatbot.py imports from here and does NOT duplicate pattern logic.

Supported fact keys
-------------------
user_name, user_location, user_origin, user_workplace, user_job_title,
user_learning, user_interest, user_skill, user_goal,
user_language_preference, user_response_style, favorite_colour,
user_school (with education_status: 'current' | 'past' | None)

Language detection
------------------
* Tamil script (U+0B80–U+0BFF present) → style = 'tamil'
* Tanglish keyword match               → style = 'tanglish'
* Otherwise                            → style = 'english'

Cross-language retrieval
------------------------
If a fact was saved in English but the question was in Tamil/Tanglish,
answer_question() falls back to the English value automatically.

Tense distinction (user_school)
--------------------------------
education_status = 'current'  → "naa KLNCE il padikuren" (present-tense)
education_status = 'past'     → "naa KLNCE la padichen" (past-tense)
education_status = None        → unknown (e.g. saved via /remember)
The response template picks the correct phrasing automatically.

Personal-history safety guard
------------------------------
Questions about college, degrees, education, employment, and other
personal facts that match _PERSONAL_HISTORY_GUARD_PATTERNS are
blocked from reaching Ollama even if they don't match an intent pattern.
They return a polite "I don't have that saved" message instead.
"""

from __future__ import annotations

import re

from memory_db import initialize_database, get_memory, get_education_status
from tanglish_understanding import understand_tanglish, TanglishIntent

initialize_database()

# ── Word-by-word tokenization integration ────────────────────────────────────
#
# Uses tanglish_tokenizer.py for multi-fact extraction from single statements.
# Called by detect_intent() as a fallback when traditional pattern matching fails.
#
# STATUS: DISABLED - Tokenizer creates false positives (capitalizes ALL words as names).
#         Re-enable only after fixing: (1) capitalization heuristic (2) fact confidence
#         (3) safety rules enforcement (4) test suite passing

try:
    from model.tanglish_tokenizer import parse_tanglish, detect_intent_with_tokenization
    TOKENIZER_AVAILABLE = False  # DISABLED until safe
except ImportError:
    TOKENIZER_AVAILABLE = False
    parse_tanglish = None
    detect_intent_with_tokenization = None

# ── Intent patterns ──────────────────────────────────────────────────────────
#
# Each key maps to a list of literal phrases to look for (case-insensitive
# for ASCII, original-case for Tamil script).
# Keep the most specific phrases first to avoid early false matches.

_INTENT_PATTERNS: dict[str, list[str]] = {

    "user_name": [
        # Tamil script
        "என் பெயர் என்ன", "என்னுடைய பெயர் என்ன",
        "என் பெயர் சொல்", "என்னுடைய பெயர் சொல்",
        "என் பெயர் யாரு",
        # Tanglish
        "en peyar enna", "ennoda peyar enna",
        "en peru enna",  "ennoda peru enna",
        # English
        "what is my name", "what's my name", "whats my name",
        "tell me my name",
    ],

    "user_degree": [
        # English — specific degree questions (check before user_school to avoid conflicts)
        "what degree do i have", "what is my degree",
        "do i have a degree", "which degree have i completed",
        "have i completed my degree", "what degree did i complete",
        "what is my qualification",
        # Tanglish
        "en degree enna", "en degree ella", "naa enna degree",
    ],

      "user_location": [
        # Tamil script
        "நான் எங்கே இருக்கிறேன்",
        "நான் எங்கு இருக்கிறேன்",
        "நான் எங்கே வசிக்கிறேன்",
        "என் ஊர் என்ன",

        # Tanglish: residence
        "naan enga irukken",
        "naan enga iruken",
        "naan enga irukkiren",
        "naa enga irukken",
        "naa enga iruken",
        "naa enga irukkiren",
        "enga irukken",
        "enga iruken",
        "naan enga vasikiren",
        "naa enga vasikiren",
        "entha ooru",
        "en ooru",
        "enga ooru",

        # English: residence
        "where do i live",
        "what is my location",
        "where am i based",
    ],

    "user_origin": [
        # Tanglish: origin
        "naa enga irundhu varen",
        "naan enga irundhu varen",
        "naa enga irunthu varen",
        "naan enga irunthu varen",
        "naa entha oorula irundhu varen",
        "naan entha oorula irundhu varen",
        "naa entha oorula irunthu varen",
        "naan entha oorula irunthu varen",
        "enga irundhu varen",
        "enga irunthu varen",

        # English: origin
        "where do i come from",
        "where am i originally from",
        "where am i from",
    ],

    "user_workplace": [
        # Tamil script
        "நான் எங்கே வேலை செய்கிறேன்",
        "நான் என்ன நிறுவனத்தில் வேலை",
        "என் வேலை இடம்", "என் நிறுவனம் என்ன",
        # Tanglish
        "naan enga work panren", "naan enga velai seykiren",
        "en company enna", "en office enna",
        # English
        "where do i work", "what is my workplace", "where am i working",
        "what company do i work",
    ],

    "user_job_title": [
        # Tamil script
        "என் வேலை என்ன", "என் பதவி என்ன",
        # English
        "what is my job", "what do i do", "what is my role",
        "what is my profession",
    ],

    "user_school": [
        # Tamil script
        "நான் எந்த கல்லூரியில் படித்தேன்",
        "நான் எந்த பள்ளியில் படித்தேன்",
        "என் கல்லூரி என்ன", "என் பள்ளி என்ன",
        "எந்த கல்லூரியில் படித்தேன்",
        "நான் எந்த கல்லூரியில் படிக்கிறேன்",
        "நான் எங்கே படிக்கிறேன்",
        # Tanglish — past-tense (padichen = studied) AND present-tense (padikuren = studying)
        # "padichen"  → studied in the past
        # "padikuren" → currently studying / enrolled
        "en college enna", "en school enna",
        # past-tense patterns
        "naan enna college la padichen", "naa enna college la padichen",
        "naan endha college la padichen", "naa endha college la padichen",
        "naan enga college padichen", "naa enga college padichen",
        "naan enna school la padichen", "naa enna school la padichen",
        "naan endha school la padichen",
        # CRITICAL: BARE past-tense queries (just "padichen" without college/school word)
        # User says "naa enga padichen?" (where did I study?) — MUST match
        "naa enga padichen", "naan enga padichen",
        "naa entha padichen", "naan entha padichen",
        # present-tense patterns (currently enrolled)
        "naan enna college la padikuren", "naa enna college la padikuren",
        "naan enna college padikuren", "naa enna college padikuren",
        "naan endha college la padikuren", "naa endha college la padikuren",
        "naan enga college padikuren", "naa enga college padikuren",
        "naan enna school la padikuren", "naa enna school la padikuren",
        # present-tense bare question forms (enga = where, entha = which/what)
        "naa enga padikuren", "naan enga padikuren",
        "naa entha padikuren", "naan entha padikuren",
        "naa entha college la padikuren", "naan entha college la padikuren",
        # present-tense with "enna kalloori" / "entha kalloori" (what/which college)
        "naa enna kalloori il padikuren", "naan enna kalloori il padikuren",
        "naa entha kalloori il padikuren", "naan entha kalloori il padikuren",
        "naa enna school il padikuren", "naan enna school il padikuren",
        # present-tense short forms (naa/naan + college + padikuren)
        "naa college la padikuren", "naan college la padikuren",
        "naa college padikuren", "naan college padikuren",
        # short form with "il" postposition (e.g. "naa KLNCE il padikuren")
        "il padikuren", "il padichen",
        "en college pathi", "en school pathi",
        # CRITICAL: SIMPLE DIRECT QUERIES
        "entha college", "entha school",  # "what college", "what school"
        "naa college", "naan college",    # "my college", "my school"
        "naa school", "naan school",
        # English — degree / graduation questions map here too (temporal note in response)
        "what is my school", "what is my college", "what college did i",
        "what school did i", "where did i study", "where did i go to school",
        "which college did i", "which school did i",
        "where am i studying", "where do i study", "which college am i",
        "what college am i", "where am i going to college",
        # degree / graduation questions — routed to user_school so they get
        # a deterministic answer from stored college fact, not Ollama
        "which college degree", "college degree", "my degree",
        "did i graduate", "where did i graduate", "where did i do my",
        "my graduation", "my qualification",
        "where am i going to college",
    ],

    "user_field_of_study": [
        # Tamil script
        "நான் என்ன படித்தேன்",
        "என் பிரிவு என்ன", "என் சரியாக என்ன",
        # Tanglish — past and present tense
        "en field enna", "en major enna",
        "naa enna padichen", "naa entha padichen",
        "naa enna padikuren", "naa entha padikuren",
        "what did i study", "what do i study",
        "what is my major", "what is my field", "what is my field of study",
        "what is my specialization",
        "which field did i study",
    ],

    "user_learning": [
        # Tamil script
        "நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்",
        "நான் என்ன படிக்கிறேன்",
        "நான் என்ன கற்கிறேன்",
        "என் கற்கும் விஷயம்",
        "என் கற்கும் விஷயம் என்ன",
        # Tanglish
        "naan enna kathukkiren", "naan enna kathukittu irukken",
        "enna kathukittu irukken", "enna kathukkittu irukken",
        "naan enna padikiren",
        # English
        "what am i learning", "what am i studying",
    ],

    "user_interest": [
        # Tamil script
        "எனக்கு என்ன பிடிக்கும்", "என் விருப்பங்கள் என்ன",
        # Tanglish
        "enakku enna pidikkum", "enakku enna pudikkum",
        # English
        "what are my interests", "what do i like", "what are my hobbies",
    ],

    "user_skill": [
        # Tamil script
        "என் திறமை என்ன", "நான் என்ன செய்ய தெரியும்",
        # English
        "what are my skills", "what can i do",
    ],

    "user_goal": [
        # Tamil script
        "என் இலக்கு என்ன", "என்னுடைய இலக்கு என்ன",
        "என் குறிக்கோள் என்ன",
        # Tanglish
        "en goal enna", "en lakku enna",
        # English
        "what is my goal", "what do i want to become",
        "what is my career goal",
    ],

    "user_language_preference": [
        # Tamil script
        "எனக்கு என்ன மொழி பிடிக்கும்", "என் மொழி விருப்பம் என்ன",
        # Tanglish
        "enakku enna language pudikkum",
        # English
        "what language do i prefer", "which language do i like",
    ],

    "user_response_style": [
        "how do i prefer responses", "how should you respond to me",
    ],

    "favorite_colour": [
        # Tamil script
        "எனக்கு பிடித்த நிறம் என்ன", "எனக்குப் பிடித்த நிறம் என்ன",
        "எனக்கு பிடித்த வண்ணம் என்ன",
        # Tanglish
        "en favourite colour enna", "en favorite color enna",
        "enakku pidicha colour enna",
        # English
        "what is my favourite colour", "what is my favorite colour",
        "what's my favourite colour", "what's my favorite color",
        "my favourite colour", "my favorite color",
    ],
}

# Tanglish keywords for language-style detection
_TANGLISH_WORDS: frozenset[str] = frozenset({
    "enna", "en", "naan", "naa", "na", "neenga", "enga",
    "irukken", "iruken", "pudikkum", "peru", "peyar",
    "kathukkiren", "kathukittu", "velai", "seykiren",
    "panren", "pannren", "aaganum",
    # past-tense study/college vocabulary
    "padichen", "padichaen", "endha", "enga",
    # present-tense study vocabulary
    "padikuren", "padikittu",
})


# ── Personal-history safety guard ────────────────────────────────────────────
#
# Questions about personal facts that do NOT match any _INTENT_PATTERNS entry
# must NOT fall through to Ollama. These guard patterns catch edge cases so
# that personal-history questions always get a deterministic response.

_PERSONAL_HISTORY_GUARD_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        # Education / degree
        r"\b(?:my|what(?:'s|\s+is)|which|where|did\s+i)\b[^?]*\b(?:degree|graduation|graduate|college|school|university|qualification|field\s+of\s+study|major|course|program)\b",
        # Bare "what degree" / "do i have a degree"
        r"\b(?:what|which)\s+degree\b",
        r"\bdo\s+i\s+have\s+(?:a\s+)?degree\b",
        r"\bhave\s+(?:i\s+)?done\s+(?:my\s+)?(?:degree|graduation|college)\b",
        # Employment
        r"\b(?:my|what(?:'s|\s+is)|where|did\s+i)\b[^?]*\b(?:job|work|workplace|employer|company|office|career|profession|role|position)\b",
        # Tanglish education guard
        r"\b(?:en|naa|naan)\b[^?]*\b(?:college|school|degree|padichen|padikuren|padichaen)\b",
        # Tanglish job guard
        r"\b(?:en|naa|naan)\b[^?]*\b(?:velai|work|job|office|company)\b",
        # Tamil script guard (rough)
        r"[\u0B80-\u0BFF].*(?:கல்லூரி|பள்ளி|படிக்கிறேன்|படித்தேன்|வேலை|பதவி|நிறுவன)",
    ]
]


# ── Language detection ───────────────────────────────────────────────────────

def detect_language_style(text: str) -> str:
    """Return 'tamil', 'tanglish', or 'english'."""
    if any("\u0B80" <= ch <= "\u0BFF" for ch in text):
        return "tamil"
    tokens = frozenset(re.findall(r"\b\w+\b", text.lower()))
    if tokens & _TANGLISH_WORDS:
        return "tanglish"
    return "english"


# ── Intent detection ─────────────────────────────────────────────────────────

def _is_tamil(phrase: str) -> bool:
    return any("\u0B80" <= ch <= "\u0BFF" for ch in phrase)


def detect_intent(question: str) -> str | None:
    """
    Return the canonical fact key for a recognized question, or None.

    Tamil-script phrases are matched against the original text.
    ASCII phrases are matched against the lowercased text.
    """
    q_lower = question.lower().strip()
    q_orig  = question.strip()
    for key, phrases in _INTENT_PATTERNS.items():
        for phrase in phrases:
            if _is_tamil(phrase):
                if phrase in q_orig:
                    return key
            else:
                if phrase in q_lower:
                    return key
    return None


# ── Response templates ────────────────────────────────────────────────────────

def _build_response(intent: str, value: str, style: str, question: str = "") -> str:
    """
    Build a language-matched response for a fact retrieval.
    For user_school, phrasing adapts to education_status or question tense.
    """
    # Tense-aware school responses
    if intent == "user_school":
        # 1. Try to read stored education_status
        edu_status = get_education_status("user_school")
        # 2. Override from the question text if possible
        if question:
            inferred = _infer_school_tense_from_message(question)
            if inferred == "user_school_current":
                edu_status = "current"
            elif inferred == "user_school":
                edu_status = edu_status or "past"

        if edu_status == "current":
            _SC = {
                "tamil":    f"நீங்கள் தற்போது {value}-இல் படிக்கிறீர்கள்.",
                "tanglish": f"Neenga ippo {value}-la padikureengga.",
                "english":  f"You are currently studying at {value}.",
            }
            return _SC.get(style, f"You are currently studying at {value}.")
        else:
            _SP = {
                "tamil":    f"உங்கள் கல்லூரி {value}.",
                "tanglish": f"Unga college {value}.",
                "english":  f"Your college/school is {value}.",
            }
            return _SP.get(style, f"Your college/school is {value}.")

    _T: dict[str, dict[str, str]] = {
        "user_name": {
            "tamil":    f"உங்கள் பெயர் {value}.",
            "tanglish": f"Unga peyar {value}.",
            "english":  f"Your name is {value}.",
        },
        "user_location": {
            "tamil":    f"நீங்கள் {value} பகுதியில் வசிக்கிறீர்கள்.",
            "tanglish": f"Neenga {value}-la vasikkireenga.",
            "english":  f"You live in {value}.",
        },
        "user_origin": {
            "tamil":    f"நீங்கள் {value}-லிருந்து வருகிறீர்கள்.",
            "tanglish": f"Neenga {value}-la irundhu vareenga.",
            "english":  f"You are originally from {value}.",
        },
        "user_workplace": {
            "tamil":    f"நீங்கள் {value}-இல் வேலை செய்கிறீர்கள்.",
            "tanglish": f"Neenga {value}-la velai seykireengga.",
            "english":  f"You work at {value}.",
        },
        "user_job_title": {
            "tamil":    f"உங்கள் பதவி {value}.",
            "tanglish": f"Unga job {value}.",
            "english":  f"Your job title is {value}.",
        },
        "user_learning": {
            "tamil":    f"நீங்கள் {value} கற்கிறீர்கள்.",
            "tanglish": f"Neenga {value} kathukkireengga.",
            "english":  f"You are learning {value}.",
        },
        "user_school": {
            "tamil":    f"உங்கள் கல்லூரி {value}.",
            "tanglish": f"Unga college {value}.",
            "english":  f"Your college/school is {value}.",
        },
        "user_field_of_study": {
            "tamil":    f"உங்கள் படிப்பு {value}.",
            "tanglish": f"Unga field of study {value}.",
            "english":  f"Your field of study is {value}.",
        },
        "user_degree": {
            "tamil":    f"உங்கள் பட்டம் {value}.",
            "tanglish": f"Unga degree {value}.",
            "english":  f"Your degree is {value}.",
        },
        "user_interest": {
            "tamil":    f"உங்களுக்கு {value} பிடிக்கும்.",
            "tanglish": f"Ungalukku {value} pudikkum.",
            "english":  f"Your interests include {value}.",
        },
        "user_skill": {
            "tamil":    f"உங்கள் திறமை {value}.",
            "tanglish": f"Unga skill {value}.",
            "english":  f"Your skills include {value}.",
        },
        "user_goal": {
            "tamil":    f"உங்கள் இலக்கு {value}.",
            "tanglish": f"Unga goal {value}.",
            "english":  f"Your goal is {value}.",
        },
        "user_language_preference": {
            "tamil":    f"உங்களுக்கு {value} மொழி பிடிக்கும்.",
            "tanglish": f"Ungalukku {value} pudikkum.",
            "english":  f"You prefer {value}.",
        },
        "user_response_style": {
            "tamil":    f"நீங்கள் {value} பாணியில் பதில்களை விரும்புகிறீர்கள்.",
            "tanglish": f"Neenga {value} style response prefer paneengga.",
            "english":  f"You prefer {value} style responses.",
        },
        "favorite_colour": {
            "tamil":    f"உங்களுக்கு பிடித்த நிறம் {value}.",
            "tanglish": f"Ungalukku pidicha colour {value}.",
            "english":  f"Your favourite colour is {value}.",
        },
    }
    group = _T.get(intent, {})
    return group.get(style, f"Your {intent.replace('_', ' ')} is {value}.")


# ── Statement-acknowledgment map ─────────────────────────────────────────────
#
# When the user makes a personal-fact statement (not a question), the chatbot
# should acknowledge it briefly and in the correct language/style.
# These templates are keyed by (intent_key, language_style).

_ACK_TEMPLATES: dict[str, dict[str, str]] = {
    "user_name": {
        "tamil":    "சரி! உங்கள் பெயர் {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga peyar {value} nu note panniten.",
        "english":  "Got it! I'll remember your name is {value}.",
    },
    "user_location": {
        "tamil":    "சரி! நீங்கள் {value} பகுதியில் வசிக்கிறீர்கள் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Neenga {value}-la irukkeenga nu save panniten.",
        "english":  "Got it! I'll remember you live in {value}.",
    },
    "user_origin": {
        "tamil":    "சரி! நீங்கள் {value}-லிருந்து வருகிறீர்கள் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Neenga {value}-la irundhu vareenga nu save panniten.",
        "english":  "Got it! I'll remember you're originally from {value}.",
    },
    "user_workplace": {
        "tamil":    "சரி! நீங்கள் {value}-இல் வேலை செய்கிறீர்கள் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Neenga {value}-la velai seykireengga nu save panniten.",
        "english":  "Got it! I'll remember you work at {value}.",
    },
    "user_learning": {
        "tamil":    "சரி! நீங்கள் {value} கற்கிறீர்கள் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Neenga {value} kathukureengga nu save panniten.",
        "english":  "Got it! I'll remember you're learning {value}.",
    },
    "user_school": {
        "tamil":    "சரி! நீங்கள் {value}-இல் படித்தீர்கள் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Neenga {value}-la padicheenga nu save panniten.",
        "english":  "Got it! I'll remember you studied at {value}.",
    },
    # Separate templates for present-tense school (padikuren / am studying)
    "user_school_current": {
        "tamil":    "சரி! நீங்கள் தற்போது {value}-இல் படிக்கிறீர்கள் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Neenga ippo {value}-la padikureengga nu save panniten.",
        "english":  "Got it! I'll remember you're currently studying at {value}.",
    },
    "user_field_of_study": {
        "tamil":    "சரி! உங்கள் படிப்பு {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga field of study {value} nu save panniten.",
        "english":  "Got it! I'll remember your field of study is {value}.",
    },
    "user_degree": {
        "tamil":    "சரி! உங்கள் பட்டம் {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga degree {value} nu save panniten.",
        "english":  "Got it! I'll remember your degree is {value}.",
    },
    "user_goal": {
        "tamil":    "சரி! உங்கள் இலக்கு {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga goal {value} nu save panniten.",
        "english":  "Got it! I'll remember your goal is {value}.",
    },
    "user_interest": {
        "tamil":    "சரி! உங்களுக்கு {value} பிடிக்கும் என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Ungalukku {value} pudikkum nu save panniten.",
        "english":  "Got it! I'll remember you're interested in {value}.",
    },
    "user_skill": {
        "tamil":    "சரி! உங்கள் திறமை {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga skill {value} nu save panniten.",
        "english":  "Got it! I'll remember your skill is {value}.",
    },
    "user_job_title": {
        "tamil":    "சரி! உங்கள் பதவி {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga job {value} nu save panniten.",
        "english":  "Got it! I'll remember your job title is {value}.",
    },
    "user_language_preference": {
        "tamil":    "சரி! உங்கள் மொழி விருப்பம் {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Unga language preference {value} nu save panniten.",
        "english":  "Got it! I'll remember you prefer {value}.",
    },
    "user_response_style": {
        "english":  "Got it! I'll respond in {value} style.",
        "tanglish": "Seri! {value} style-la respond pannuvom.",
        "tamil":    "சரி! {value} பாணியில் பதிலளிக்கிறேன்.",
    },
    "favorite_colour": {
        "tamil":    "சரி! உங்களுக்கு பிடித்த நிறம் {value} என்று நினைவில் வைத்துக்கொள்கிறேன்.",
        "tanglish": "Seri! Ungalukku pidicha colour {value} nu save panniten.",
        "english":  "Got it! I'll remember your favourite colour is {value}.",
    },
}

# ── Statement-intent patterns ─────────────────────────────────────────────────
#
# Mirror of _INTENT_PATTERNS but for *statements* (declarative, not questions).
# Used by acknowledge_statement() to detect which fact was just stated.

_STATEMENT_PATTERNS: dict[str, list[str]] = {
    "user_name": [
        # Tamil
        "என் பெயர் ", "என்னுடைய பெயர் ",
        # Tanglish
        "en peyar ", "en peru ", "ennoda peyar ", "ennoda peru ",
        # English
        "my name is ",
    ],
    # user_school MUST come before user_learning so "i'm studying at X"
    # matches school before learning's "i'm studying " prefix fires.
    "user_school": [
        # Tamil
        "படித்தேன்", "கல்லூரியில் படித்தேன்", "பள்ளியில் படித்தேன்",
        # Tamil present-tense
        "படிக்கிறேன்", "கல்லூரியில் படிக்கிறேன்",
        # Tanglish — past-tense study verbs ("padichen" = I studied)
        "la padichen", "la padichaen", "college la padi", "school la padi",
        "college padichen", "school padichen",
        # Tanglish — present-tense study verbs ("padikuren" = I am studying)
        "la padikuren", "college padikuren", "school padikuren",
        "il padikuren", "college il padikuren", "school il padikuren",
        # English — more specific "studying AT" before learning's "studying "
        "i am studying at ", "i'm studying at ", "i study at ",
        "i studied at ", "i went to college ", "i went to school ",
        "my college is ", "my school is ",
    ],
    "user_field_of_study": [
        # Tanglish — field of study patterns with "padichen" (studied) or "padikuren" (studying)
        "padichen college", "padikuren college",
        # Alternative: explicit field+verb patterns
        "cse padichen", "cse padikuren",
        "it padichen", "it padikuren",
        "ece padichen", "ece padikuren",
        "mechanical padichen", "mechanical padikuren",
        # English
        "i studied ", "i'm studying ", "i studied at ",
        "my major is ", "my field is ", "my specialization is ",
    ],
    "user_learning": [
        # Tamil substrings (check learning BEFORE location to avoid "naan" clash)
        "கற்றுக்கொண்டு இருக்கிறேன்", "கற்கிறேன்",
        # Tanglish — specific present-tense verb endings
        "kathukittu irukken", "kathukkittu irukken",
        "kathukkiren", "kathukiren", "padikiren", "padikittu",
        # English — only bare "studying" without "at" (school catches "studying at")
        "i'm learning ", "i am learning ",
        "i'm studying ", "i am studying ",
    ],
    "user_workplace": [
        "i work at ", "i work for ", "i work in ",
        "i am working at ", "i'm working at ",
        "வேலை செய்கிறேன்",
        "la work panren", "la velai seykiren",
    ],
    "user_goal": [
        "my goal is ", "i want to become ",
        "en goal ", "என் இலக்கு ", "என்னுடைய இலக்கு ", "ஆக வேண்டும்",
    ],
    "user_location": [
        # English residence statements
        "i live in ", "i am based in ",
        # Tanglish residence statements; city name may appear before these endings
        " la irukken", " la iruken", " la vasikkiren", " la vasikiren",
        " il irukken", " il iruken",
    ],
    "user_origin": [
        # English origin statements
        "i am from ", "i'm from ", "i come from ",
        # Tanglish origin statements
        " la irundhu varen", " la irunthu varen",
        " irundhu varen", " irunthu varen",
    ],
    "user_interest": [
        "i like ", "i love ", "i enjoy ", "my hobby is ", "my interest is ",
        "எனக்கு பிடிக்கும்", "எனக்குப் பிடிக்கும்",
        "enakku ", # combined with pudikkum
    ],
    "user_skill": [
        "i can ", "my skill is ", "i know how to ",
        "என் திறமை ",
    ],
}


def _detect_statement_intent(message: str) -> str | None:
    """
    Return the canonical fact key if the message is a personal-fact *statement*
    (not a question). Returns None if no known statement pattern matches.
    """
    msg_lower = message.lower()
    msg_orig  = message

    for key, phrases in _STATEMENT_PATTERNS.items():
        for phrase in phrases:
            if _is_tamil(phrase):
                if phrase in msg_orig:
                    return key
            else:
                if phrase in msg_lower:
                    return key
    
    # Fallback: try tanglish_understanding
    tanglish_intent = understand_tanglish(message)
    
    # Only process if it's clearly a save operation (statement)
    if tanglish_intent.operation == 'save' and tanglish_intent.is_personal_fact():
        memory_key = _tanglish_intent_to_memory_key(tanglish_intent)
        if memory_key:
            # High confidence only
            if tanglish_intent.confidence >= 0.7:
                return memory_key
    
    return None


def _infer_school_tense_from_message(message: str) -> str:
    """
    Infer whether a school statement/question is present- or past-tense.
    Returns 'user_school_current' (present) or 'user_school' (past/unknown).

    Present markers: padikuren, padikittu, am studying, study at, currently
    Past markers:    padichen, padichaen, studied at, did i study, went to
    """
    m = message.lower()
    present_markers = [
        "padikuren", "padikittu", "am studying", "i'm studying",
        "i study at", "currently study", "study at",
        "படிக்கிறேன்", "படிக்கிறீர்கள்",
    ]
    past_markers = [
        "padichen", "padichaen", "studied at", "went to", "did i study",
        "padicheenga", "படித்தேன்", "படித்தீர்கள்",
    ]
    for pm in present_markers:
        if pm in m or pm in message:
            return "user_school_current"
    for pm in past_markers:
        if pm in m or pm in message:
            return "user_school"
    # Fall back to stored education_status
    stored = get_education_status("user_school")
    if stored == "current":
        return "user_school_current"
    return "user_school"


# ── Tanglish intent integration ───────────────────────────────────────────────

def _tanglish_intent_to_memory_key(intent: TanglishIntent) -> str | None:
    """
    Convert a TanglishIntent to a canonical memory key if applicable.
    Returns None if the intent is not a personal-fact operation.
    """
    if not intent.is_personal_fact():
        return None
    
    # Direct mapping from TanglishIntent.memory_key (already canonical)
    return intent.memory_key


# ── Public API ────────────────────────────────────────────────────────────────


def extract_and_save_multi_facts_tanglish(message: str) -> dict[str, str] | None:
    """
    Use word-by-word tokenization to extract and save multiple facts from a single message.
    
    SAFETY REQUIREMENTS:
    1. Message must NOT be a question (end with ?)
    2. Message must NOT be a greeting-only (just "vannakam")
    3. Message must match personal-fact statement patterns
    4. NO facts extracted from: commands, gibberish, generic requests
    
    Returns:
        Dictionary of {memory_key: saved_value} for each fact extracted and saved,
        or None if no facts were extracted or message invalid.
    """
    if not TOKENIZER_AVAILABLE or not parse_tanglish:
        return None
    
    # SAFETY: Pre-validation before tokenization
    # 1. Reject questions (end with ?)
    if message.strip().endswith('?'):
        return None
    
    # 2. Reject slash commands
    if message.strip().startswith('/'):
        return None
    
    # 3. Reject very short messages (likely greetings only)
    if len(message.split()) <= 1:
        return None
    
    # 4. Check if it looks like a personal fact statement
    from fact_extractor import _looks_like_personal_statement
    if not _looks_like_personal_statement(message):
        return None
    
    # SAFETY: Also check personal history guard (should not be saving personal history questions)
    if is_personal_history_question(message):
        return None
    
    try:
        tokens, stmt = parse_tanglish(message)
    except Exception:
        return None
    
    if not stmt.has_facts():
        return None
    
    saved_facts = {}
    
    # Save extracted name (ONLY if marked with "en peru" or "en peyar", never just capitalized)
    if stmt.name:
        from memory_db import save_memory
        save_memory(
            "user_name", stmt.name,
            category="identity", confidence=0.85,
            source="regex",
        )
        saved_facts["user_name"] = stmt.name
    
    # Save extracted location/origin
    if stmt.location:
        from memory_db import save_memory
        save_memory(
            "user_location", stmt.location,
            category="identity", confidence=0.85,
            source="regex",
        )
        saved_facts["user_location"] = stmt.location
    
    # Save education fact if detected
    if stmt.education:
        from memory_db import save_memory
        education_status = None
        if stmt.verb_tense == "continuous" or "padikuren" in message.lower():
            education_status = "current"
        elif stmt.verb_tense == "past" or "padichen" in message.lower():
            education_status = "past"
        
        save_memory(
            "user_school", stmt.education,
            category="education", confidence=0.85,
            source="regex",
            education_status=education_status,
        )
        saved_facts["user_school"] = stmt.education
    
    return saved_facts if saved_facts else None


def acknowledge_statement(message: str) -> str | None:
    """
    When the user makes a personal-fact statement (not a question), return a
    brief, language-matched acknowledgment using the just-saved fact value from
    the DB.  Returns None if the message is not a recognisable statement.

    This prevents statements from being passed to Ollama for an uncontrolled
    free-form response, which is the root cause of wrong-language replies after
    saving a fact.

    For user_school statements, the tense is inferred from the message:
    present-tense markers (padikuren, am studying, study at) produce a
    'currently studying' acknowledgment; past-tense markers produce a
    'previously studied' acknowledgment.
    """
    intent = _detect_statement_intent(message)
    
    # If no pattern match, try tanglish_understanding as a fallback
    if intent is None:
        tanglish_intent = understand_tanglish(message)
        
        # Only process if it's clearly a save/acknowledge operation
        if tanglish_intent.operation in ('save', 'acknowledge') and tanglish_intent.is_personal_fact():
            memory_key = _tanglish_intent_to_memory_key(tanglish_intent)
            if memory_key:
                # High confidence only
                if tanglish_intent.confidence >= 0.7:
                    intent = memory_key

    if intent is None:
        return None

    # Only acknowledge if we can confirm the fact is actually in the DB
    value = get_memory(intent, language="english")
    if value is None:
        return None

    style = detect_language_style(message)

    # For school, use tense-specific template
    if intent == "user_school":
        tmpl_key = _infer_school_tense_from_message(message)
        tmpl = _ACK_TEMPLATES.get(tmpl_key, {}).get(style)
        if not tmpl:
            tmpl = _ACK_TEMPLATES.get("user_school", {}).get(style)
        if tmpl:
            return tmpl.format(value=value)
    else:
        tmpl = _ACK_TEMPLATES.get(intent, {}).get(style)
        if tmpl:
            return tmpl.format(value=value)

    # Fallback: generic English ack
    key_label = intent.replace("user_", "").replace("_", " ")
    return f"Got it! I'll remember your {key_label} is {value}."


def answer_question(question: str) -> str | None:
    """
    Try to answer a personal-fact question from memory.

    Returns a formatted string if intent matches and fact is stored.
    Returns a polite "not saved" message if intent matches but no fact.
    Returns None if:
      - The input is a statement (not a question), so acknowledge_statement() can handle it
      - It's a true general question (no personal-fact keywords)

    Cross-language: if the user asks in Tamil but the fact was saved as
    English, the English value is returned (formatted in Tamil grammar).
    
    CRITICAL FIX FOR BUG 1: Only treat as a memory question if:
    1. Intent pattern matches (high confidence), OR
    2. Tanglish intent is high-confidence (0.8+) AND the fact actually exists in DB
    
    This prevents casual questions like "Naa nalla iruken, nee?" from being
    incorrectly routed to "not saved" responses when they're just small talk.
    """
    # Import here to avoid circular dependency
    from fact_extractor import _looks_like_personal_statement
    
    intent = detect_intent(question)
    style  = detect_language_style(question)

    # If no pattern match, try tanglish_understanding as a fallback
    if intent is None:
        tanglish_intent = understand_tanglish(question)
        
        # Only process if it's clearly a retrieval operation (question/recall)
        if tanglish_intent.operation in ('retrieve', 'acknowledge') and tanglish_intent.is_personal_fact():
            memory_key = _tanglish_intent_to_memory_key(tanglish_intent)
            if memory_key:
                # FIX: Only accept high-confidence tanglish intents (0.8+)
                # AND verify the fact actually exists in the DB
                if tanglish_intent.confidence >= 0.8:
                    # Check if fact is actually in DB
                    test_value = get_memory(memory_key, language=style)
                    if test_value is None and style != "english":
                        test_value = get_memory(memory_key, language="english")
                    
                    # Only treat as a memory question if fact is in DB
                    if test_value is not None:
                        intent = memory_key
                    # else: fact not in DB, let it fall through to Ollama
                # else: low confidence, continue with safety guard below instead

    if intent is None:
        # If this looks like a statement (not a question), don't handle it here
        # — let acknowledge_statement() process it instead
        if _looks_like_personal_statement(question):
            return None
        
        # Safety guard: QUESTIONS about personal facts that don't match a specific
        # pattern must not reach Ollama. But don't block statements or casual questions.
        # CRITICAL FIX: Only block if the fact is actually in DB
        # This prevents "how are you" from triggering "not saved" responses
        if is_personal_history_question(question):
            # Check if we should block this or let it go to Ollama
            # Heuristic: if question looks like it's asking about well-being or how someone is,
            # let it go to Ollama (it's probably "how are you?" not a memory question)
            if any(word in question.lower() for word in ['iruken', 'irukka', 'irundhen', 'nalla', 'well', 'how']):
                # This might be casual conversation, not a memory question
                # Check if the detected intent actually has a fact in DB
                # If we couldn't find a pattern match above, don't return "not saved"
                return None
            
            _not_saved = {
                "tamil":    "இந்தத் தகவல் இன்னும் சேமிக்கப்படவில்லை.",
                "tanglish": "Antha thakaval innama save aagalai.",
                "english":  "That information hasn't been saved yet.",
            }
            return _not_saved.get(style, "That information hasn't been saved yet.")
        return None

    # Try requested language first, then fall back to English
    value = get_memory(intent, language=style)
    if value is None and style != "english":
        value = get_memory(intent, language="english")

    if value is None:
        _not_saved = {
            "tamil":    "இந்தத் தகவல் இன்னும் சேமிக்கப்படவில்லை.",
            "tanglish": "Antha thakaval innama save aagalai.",
            "english":  "That information hasn't been saved yet.",
        }
        return _not_saved.get(style, "That information hasn't been saved yet.")

    return _build_response(intent, value, style, question=question)


def is_personal_history_question(text: str) -> bool:
    """
    Return True if the text looks like a personal-history question
    (college, degree, job, etc.) that should NOT fall through to Ollama.

    Used by chatbot.py as a second-tier safety net after detect_intent().
    """
    return any(p.search(text) for p in _PERSONAL_HISTORY_GUARD_PATTERNS)


def handle_greeting(message: str) -> str | None:
    """
    Recognize greetings and return a simple Tamil greeting response.
    
    Returns a simple greeting if detected, None otherwise.
    """
    from tanglish_understanding import understand_tanglish
    
    tanglish_intent = understand_tanglish(message)
    
    # Check if it's classified as a greeting
    if tanglish_intent.sentence_type != 'greeting':
        return None
    
    # Return a simple Tamil greeting
    style = detect_language_style(message)
    
    if style == 'tamil':
        return "வணக்கம்!"
    elif style == 'tanglish':
        return "Vanakkam!"
    else:
        return "Hello!"


def learn_fact(message: str) -> str | None:
    """
    Legacy explicit-learn path for colour statements:
    'En favourite colour blue.' / 'My favourite colour is red.'

    Kept for backward compatibility; the AI extractor handles broader cases.
    Returns a confirmation string or None.
    """
    from memory_db import save_memory

    q = message.lower().strip()
    if q.endswith("?") or " enna" in q:
        return None

    prefixes = [
        "en favourite colour ",
        "my favourite colour is ",
        "my favorite color is ",
    ]
    for prefix in prefixes:
        if q.startswith(prefix):
            colour = message[len(prefix):].strip().rstrip(".!?")
            if not colour or colour.lower() in {"enna", "what", "unknown"}:
                return None

            _translations = {
                "blue": "நீலம்", "red": "சிவப்பு",
                "green": "பச்சை", "yellow": "மஞ்சள்",
                "black": "கருப்பு", "white": "வெள்ளை",
                "orange": "ஆரஞ்சு", "purple": "ஊதா",
            }
            tamil_colour = _translations.get(colour.lower())
            save_memory(
                "favorite_colour", colour, tamil_colour,
                category="preference", source="manual",
            )
            return (
                f"சரி! உங்கள் விருப்பமான நிறம் {colour} "
                "என்று நினைவில் வைத்துக்கொள்கிறேன்."
            )
    return None


# ── Standalone demo ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    _tests = [
        "En favourite colour blue.",
        "En favourite colour enna?",
        "எனக்கு பிடித்த நிறம் என்ன?",
        "What is my favourite colour?",
        "What is my name?",
        "Where do I work?",
        "What am I learning?",
        "நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?",
        "En goal enna?",
        "நான் எங்கே வேலை செய்கிறேன்?",
    ]
    for q in _tests:
        print(f"\nYou: {q}")
        result = learn_fact(q) or answer_question(q)
        print(f"Assistant: {result or '(no match — goes to Ollama)'}")
