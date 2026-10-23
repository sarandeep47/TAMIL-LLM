"""
chat_memory.py — Deterministic fact retrieval for the Tamil chatbot.

This is the SINGLE source of truth for reading personal facts.
chatbot.py imports from here and does NOT duplicate pattern logic.

Supported fact keys
-------------------
user_name, user_location, user_workplace, user_job_title,
user_learning, user_interest, user_skill, user_goal,
user_language_preference, user_response_style, favorite_colour

Language detection
------------------
* Tamil script (U+0B80–U+0BFF present) → style = 'tamil'
* Tanglish keyword match               → style = 'tanglish'
* Otherwise                            → style = 'english'

Cross-language retrieval
------------------------
If a fact was saved in English but the question was in Tamil/Tanglish,
answer_question() falls back to the English value automatically.
"""

from __future__ import annotations

import re

from memory_db import initialize_database, get_memory

initialize_database()

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

    "user_location": [
        # Tamil script
        "நான் எங்கே இருக்கிறேன்", "நான் எங்கு இருக்கிறேன்",
        "நான் எங்கே வசிக்கிறேன்", "என் ஊர் என்ன",
        # Tanglish
        "naan enga irukken", "naan enga iruken", "naan enga irukkiren",
        "naan enga vasikiren",
        # English
        "where do i live", "where am i from", "what is my location",
        "where am i based",
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
})


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

def _build_response(intent: str, value: str, style: str) -> str:
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


# ── Public API ────────────────────────────────────────────────────────────────

def answer_question(question: str) -> str | None:
    """
    Try to answer a personal-fact question from memory.

    Returns a formatted string if intent matches and fact is stored.
    Returns a polite "not saved" message if intent matches but no fact.
    Returns None if no intent matched (caller should try Ollama).

    Cross-language: if the user asks in Tamil but the fact was saved as
    English, the English value is returned (formatted in Tamil grammar).
    """
    intent = detect_intent(question)
    if intent is None:
        return None

    style = detect_language_style(question)

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

    return _build_response(intent, value, style)


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
