"""
Tanglish normalizer + rule-based router for simple intents.
"""

import re
import unicodedata
import difflib


def normalize(text):
    """
    Normalize text: NFC, lowercase, strip, collapse doubled Latin letters,
    remove consecutive duplicates, collapse whitespace.
    Keep Tamil block (U+0B80-U+0BFF) and apostrophes.
    """
    if not isinstance(text, str):
        return ""
    
    # NFC normalization
    text = unicodedata.normalize("NFC", text)
    
    # Lowercase and strip
    text = text.lower().strip()
    
    # Replace punctuation with spaces but KEEP Tamil and apostrophes
    text = re.sub(r"[^\w\s\u0B80-\u0BFF']", " ", text)
    
    # Collapse consecutive doubled Latin letters (e.g. "vanakkam" -> "vanakam", "need" stays "need")
    # \1+ means one or more repetitions of the same character, so "neeed" -> "ned" is wrong.
    # We want: replace 2+ of the same with 1. The regex ([a-z])\1+ means "a letter followed by 1+ of itself"
    # So it matches "ee" in "eeee" and replaces with "e". That's correct for vanakkam -> vanakam.
    # But "need" has only one "e" pair, which should collapse to "ne".
    # Actually re-reading the spec: "collapse doubled Latin letters"  means "neeed" type things.
    # Let's be precise: match 2+ identical letters and replace with 1.
    text = re.sub(r"([a-z])\1+", r"\1", text)  # This is correct: need has one 'e', vanakkam has two 'k'
    
    # Remove consecutive duplicate tokens
    tokens = text.split()
    deduped = []
    for tok in tokens:
        if not deduped or deduped[-1] != tok:
            deduped.append(tok)
    
    # Collapse whitespace
    text = " ".join(deduped).strip()
    return text


# ===== REPLY TABLE (exact strings) =====
REPLIES = {
    "greeting": {
        "ta": "வணக்கம்! நான் உங்களுக்கு என்ன உதவி செய்யலாம்?",
        "en": "Hello! How can I help you today?",
    },
    "how_are_you": {
        "ta": "நான் நல்லா இருக்கேன், நீங்க எப்படி இருக்கீங்க?",
        "en": "I'm doing well, thank you! How are you?",
    },
    "im_fine": {
        "ta": "கேட்டதில் மகிழ்ச்சி! நான் உங்களுக்கு என்ன உதவி செய்யலாம்?",
        "en": "Glad to hear that! How can I help you?",
    },
    "thanks": {
        "ta": "எப்போதும் வரவேற்கிறேன்!",
        "en": "You're welcome!",
    },
    "what_doing": {
        "ta": "கேப் புக் பண்ண நான் உதவுவேன், உங்களுக்கு என்ன வேண்டும்?",
        "en": "I can help you book a cab. What do you need?",
    },
    "ack": {
        "ta": "சரி! வேறு என்ன உதவி வேணும்?",
        "en": "Okay! What else can I help you with?",
    },
    "goodbye": {
        "ta": "சரி, நன்றி! மீண்டும் சந்திக்கலாம்.",
        "en": "Goodbye! Have a great day.",
    },
    "cab_request": {
        "ta": "கண்டிப்பா, உங்க பிக்கப் லொகேஷன் சொல்லுங்க?",
        "en": "Sure, what is your pickup location?",
    },
}

# ===== LEXICON (phrase -> (intent, lang)) =====
# Normalize all phrases at import time
LEXICON = {}

# greeting ta
for phrase in ["vanakam", "vanakkam", "vanakkam da", "kalai vanakkam", "வணக்கம்",
               "காலை வணக்கம்", "மாலை வணக்கம்"]:
    LEXICON[normalize(phrase)] = ("greeting", "ta")

# greeting en
for phrase in ["hello", "hi", "hey", "hai", "good morning", "good afternoon", "good evening"]:
    LEXICON[normalize(phrase)] = ("greeting", "en")

# how_are_you ta
for phrase in ["epdi irukinga", "epdi irukeenga", "eppadi irukinga", "epadi irukinga",
               "epdi iruka", "nalama", "sowkiyama", "எப்படி இருக்கீங்க",
               "எப்படி இருக்கிறீர்கள்", "எப்படி இருக்க"]:
    LEXICON[normalize(phrase)] = ("how_are_you", "ta")

# how_are_you en
for phrase in ["how are you", "how r u", "how are u", "how are you doing"]:
    LEXICON[normalize(phrase)] = ("how_are_you", "en")

# im_fine ta
for phrase in ["nalla iruken", "nalla irukken", "nan nalla iruken",
               "நான் நல்லா இருக்கேன்", "நல்லா இருக்கேன்", "நலம்"]:
    LEXICON[normalize(phrase)] = ("im_fine", "ta")

# im_fine en
for phrase in ["fine", "i am fine", "i'm fine", "im fine", "i am good", "im good"]:
    LEXICON[normalize(phrase)] = ("im_fine", "en")

# thanks ta
for phrase in ["nandri", "nanri", "romba nandri", "நன்றி", "மிக்க நன்றி"]:
    LEXICON[normalize(phrase)] = ("thanks", "ta")

# thanks en
for phrase in ["thanks", "thank you", "thank u", "thanks a lot"]:
    LEXICON[normalize(phrase)] = ("thanks", "en")

# what_doing ta
for phrase in ["enna panreenga", "enna panringa", "enna pandringa", "enna pandra",
               "enna panra", "enna seireenga", "என்ன பண்றீங்க", "என்ன செய்றீங்க"]:
    LEXICON[normalize(phrase)] = ("what_doing", "ta")

# what_doing en
for phrase in ["what are you doing", "what do you do", "what can you do"]:
    LEXICON[normalize(phrase)] = ("what_doing", "en")

# ack ta
for phrase in ["sari", "seri", "sarigna", "சரி", "சரிங்க"]:
    LEXICON[normalize(phrase)] = ("ack", "ta")

# ack en
for phrase in ["ok", "okay", "alright", "sure"]:
    LEXICON[normalize(phrase)] = ("ack", "en")

# goodbye ta
for phrase in ["poitu varen", "poitu varaen", "sari bye", "பை", "சரி பை"]:
    LEXICON[normalize(phrase)] = ("goodbye", "ta")

# goodbye en
for phrase in ["bye", "goodbye", "good bye", "see you"]:
    LEXICON[normalize(phrase)] = ("goodbye", "en")


# ===== CAB REQUEST KEYWORDS (normalized at import time) =====
CAB_WORDS = {normalize(phrase) for phrase in
    ["cab", "cabs", "taxi", "car", "caru", "cabu", "கேப்", "கேப்பு", 
     "கார்", "காரு", "காரை", "டாக்ஸி"]}

NEED_PREFIXES = {normalize(phrase) for phrase in
    ["ven", "pan", "book", "buk", "need", "ned", "want", "order", "call", 
     "get", "arrange", "anup", "வேண", "வேணு", "புக்", "பண்ண", "அனுப்"]}


def route_message(text):
    """
    Route message to intent or return None (send to LLM).
    Returns {"reply": str, "intent": str, "lang": "ta"|"en"} or None.
    """
    if not isinstance(text, str):
        return None
    
    norm = normalize(text)
    if not norm:
        return None
    
    tokens = norm.split()
    
    # ===== CAB REQUEST (wins over everything) =====
    
    has_cab_word = any(tok in CAB_WORDS for tok in tokens)
    has_need_prefix = any(any(tok.startswith(prefix) for prefix in NEED_PREFIXES) 
                          for tok in tokens)
    
    if has_cab_word and (len(tokens) <= 3 or has_need_prefix):
        # Determine language for cab_request
        is_latin_only = all(re.match(r"^[a-z0-9']+$", tok, re.IGNORECASE) for tok in tokens)
        lang_is_en = (is_latin_only and 
                      not any(tok.startswith(prefix) for prefix in ["ven", "pan", "வேண", "புக்", "பண்ண"] 
                              for tok in tokens))
        lang = "en" if lang_is_en else "ta"
        
        reply = REPLIES["cab_request"][lang]
        return {"reply": reply, "intent": "cab_request", "lang": lang}
    
    # ===== SMALL TALK (only if <= 5 tokens) =====
    if len(tokens) <= 5:
        # Try exact match
        if norm in LEXICON:
            intent, lang = LEXICON[norm]
            reply = REPLIES[intent][lang]
            return {"reply": reply, "intent": intent, "lang": lang}
        
        # Try fuzzy match
        keys = list(LEXICON.keys())
        matches = difflib.get_close_matches(norm, keys, n=1, cutoff=0.84)
        if matches:
            intent, lang = LEXICON[matches[0]]
            reply = REPLIES[intent][lang]
            return {"reply": reply, "intent": intent, "lang": lang}
    
    # ===== NO MATCH: send to LLM =====
    return None
