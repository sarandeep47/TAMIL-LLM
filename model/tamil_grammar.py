"""
tamil_grammar.py — Tamil/Tanglish word vocabulary with fuzzy similarity matching.

This module provides:
1. Tamil particles, verbs, and common words with fuzzy similarity groups
2. Similarity threshold for matching word variations
3. Functions to retrieve memory facts using fuzzy matching

Used by tanglish_tokenizer.py to parse and understand Tanglish utterances.
"""

from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional

# ── Fuzzy similarity threshold ───────────────────────────────────────────────
# Words within this threshold are considered similar (variations of the same word)
# 0.75 catches common misspellings and regional variations
FUZZY_THRESHOLD = 0.75

# ── Tamil/Tanglish vocabulary with similarity groups ──────────────────────────
# Each key is the canonical form; value is a list of known variations
# Similarity matching is done via SequenceMatcher for unknown words

TAMIL_WORDS = {
    # Pronouns
    "naan": ["naa", "na", "nahn"],  # I (nominative)
    "neenga": ["neengga", "neenga", "neega"],  # You (formal)
    "avan": ["avan", "avan"],  # He
    "aval": ["aval", "aval"],  # She
    "avarkal": ["avarkal"],  # They (formal)
    
    # Common particles and postpositions
    "la": ["la", "le"],  # at/in (locative postposition)
    "il": ["il"],  # in/at (alternate locative)
    "mai": ["mai"],  # onto/towards
    "pathi": ["pathi", "pathai"],  # about/regarding
    "oda": ["oda", "da"],  # with (possessive/instrumental)
    "ukku": ["ukku"],  # to (dative)
    
    # Greetings
    "vannakam": ["vannakam", "vanakkam", "vanakam"],  # hello/greetings
    "hi": ["hi", "hey"],
    "goodbye": ["goodbye", "bye"],
    "namaskaram": ["namaskaram"],  # respectful greeting
    
    # Personal pronouns (object forms)
    "en": ["en", "enn"],  # my
    "enoda": ["enoda", "ennoda"],  # my (emphatic)
    "ennai": ["ennai"],  # me (object)
    
    # Common verbs — present tense (suffix "-ren" or "-kiren")
    "irukken": ["irukken", "irukkiren", "iruken"],  # am/is (present)
    "irundhu": ["irundhu", "irundu", "irunthoo"],  # from (postposition of "iru" past)
    "varen": ["varen", "vareen"],  # come (present, 1st person) / came
    "vandhu": ["vandhu", "vanthu"],  # came (past participle of "va-")
    "seipen": ["seipen", "seppen"],  # do (1st person)
    "panniren": ["panniren", "panireen"],  # do/make
    "solipen": ["solipen", "solppen"],  # say/tell
    
    # Common verbs — past tense
    "padichen": ["padichen", "padichaen"],  # studied (1st person past)
    "padicheenga": ["padicheenga"],  # studied (you formal past)
    "padichen": ["padichen"],  # studied (past)
    "sonnana": ["sonnana", "sonna"],  # said (past)
    "vanthu": ["vanthu", "vanthu"],  # came (past)
    
    # Common verbs — present continuous
    "padikuren": ["padikuren", "padikittu"],  # studying (present continuous)
    "kathukiren": ["kathukiren", "kathukkiren"],  # learning (present)
    "kathukittu": ["kathukittu", "kathukkittu"],  # learning (continuous)
    "seikittu": ["seikittu", "saikittu"],  # doing (continuous)
    
    # Names/personal identifiers
    "peru": ["peru", "peyar"],  # name
    "peyar": ["peyar", "peru"],  # name (alternate spelling)
    
    # Location/origin markers
    "enga": ["enga", "eggai"],  # where
    "endha": ["endha", "enda"],  # which/what
    "madurai": ["madurai", "madura"],  # Madurai (city, canonical form)
    "chennai": ["chennai", "madras"],  # Chennai
    "bangalore": ["bangalore", "bengaluru"],  # Bangalore
    "coimbatore": ["coimbatore", "coimbatore"],  # Coimbatore
    
    # Education-related
    "college": ["college", "kalloori"],  # college
    "kalloori": ["kalloori", "college"],  # college (Tamil)
    "school": ["school", "palli"],  # school
    "degree": ["degree", "pattam"],  # degree
    "padam": ["padam", "padippu"],  # lesson/course
    
    # Occupations/roles
    "engineer": ["engineer", "enginaar"],  # engineer
    "doctor": ["doctor", "vaidya"],  # doctor
    "teacher": ["teacher", "gurukulam"],  # teacher
    "student": ["student", "padipali"],  # student
    "velai": ["velai", "nokkam"],  # work/job
    
    # Descriptors
    "nalla": ["nalla", "nalladu"],  # good
    "seri": ["seri", "sorkkum"],  # okay/fine
    "periya": ["periya", "periyadu"],  # big
    "chinna": ["chinna", "chinnadhu"],  # small
    
    # Question markers
    "enna": ["enna", "ennadi"],  # what
    "yaar": ["yaar", "yar"],  # who
    "evvandu": ["evvandu", "yevvandu"],  # when
    "enga": ["enga", "yenga"],  # where
    
    # Affirmatives/negatives
    "aama": ["aama", "aamam", "ama"],  # yes
    "illa": ["illa", "illai"],  # no
}

# Reverse mapping: variation → canonical form (for quick lookup)
WORD_VARIATIONS: Dict[str, str] = {}
for canonical, variations in TAMIL_WORDS.items():
    for var in variations:
        WORD_VARIATIONS[var.lower()] = canonical.lower()


def find_similar_word(word: str, threshold: float = FUZZY_THRESHOLD) -> Optional[Tuple[str, float]]:
    """
    Find the most similar word in TAMIL_WORDS vocabulary using fuzzy matching.
    
    Returns:
        (canonical_word, similarity_score) if score >= threshold, else None
    
    Uses difflib.SequenceMatcher for edit-distance-like similarity.
    """
    word_lower = word.lower()
    
    # Exact match first
    if word_lower in WORD_VARIATIONS:
        return (WORD_VARIATIONS[word_lower], 1.0)
    
    # Fuzzy search through all canonical words
    best_match = None
    best_score = 0.0
    
    for canonical in TAMIL_WORDS.keys():
        ratio = SequenceMatcher(None, word_lower, canonical.lower()).ratio()
        if ratio > best_score:
            best_score = ratio
            best_match = canonical
    
    if best_score >= threshold:
        return (best_match, best_score)
    
    return None


def get_word_category(word: str) -> Optional[str]:
    """
    Return the semantic category of a word (pronoun, verb, location, etc.).
    
    Categories:
        pronoun, particle, greeting, verb_present, verb_past, verb_continuous,
        name, location, education, occupation, descriptor, question, affirmative
    """
    word_lower = word.lower()
    canonical = WORD_VARIATIONS.get(word_lower, word_lower)
    
    # Categorize by prefix matching
    if canonical in ["naan", "neenga", "avan", "aval", "en", "enoda"]:
        return "pronoun"
    elif canonical in ["la", "il", "mai", "pathi", "oda", "ukku"]:
        return "particle"
    elif canonical in ["vannakam", "hi", "goodbye", "namaskaram"]:
        return "greeting"
    elif canonical in ["irukken", "varen", "seipen", "panniren", "solipen"]:
        return "verb_present"
    elif canonical in ["padichen", "padicheenga", "vanthu", "sonnana"]:
        return "verb_past"
    elif canonical in ["padikuren", "kathukiren", "kathukittu", "seikittu"]:
        return "verb_continuous"
    elif canonical in ["peru", "peyar"]:
        return "name"
    elif canonical in ["madurai", "chennai", "bangalore", "coimbatore"]:
        return "location"
    elif canonical in ["college", "kalloori", "school", "degree", "padam"]:
        return "education"
    elif canonical in ["engineer", "doctor", "teacher", "student", "velai"]:
        return "occupation"
    elif canonical in ["nalla", "seri", "periya", "chinna"]:
        return "descriptor"
    elif canonical in ["enna", "yaar", "evvandu", "enga"]:
        return "question"
    elif canonical in ["aama", "illa"]:
        return "affirmative"
    
    return None


def extract_possible_facts_from_word(word: str) -> Dict[str, Optional[str]]:
    """
    Given a single word, infer what facts might be present.
    
    Returns a dict like:
        {
            "greeting": canonical_word or None,
            "name": word_if_might_be_name or None,
            "location": canonical_location or None,
            "education": canonical_education or None,
            "verb": canonical_verb or None,
        }
    """
    word_lower = word.lower()
    facts = {
        "greeting": None,
        "name": None,
        "location": None,
        "education": None,
        "verb": None,
        "pronoun": None,
    }
    
    # Try fuzzy match
    similar = find_similar_word(word)
    if similar:
        canonical, score = similar
        category = get_word_category(canonical)
        
        if category == "greeting":
            facts["greeting"] = canonical
        elif category == "location":
            facts["location"] = canonical
        elif category == "education":
            facts["education"] = canonical
        elif category in ("verb_present", "verb_past", "verb_continuous"):
            facts["verb"] = canonical
        elif category == "pronoun":
            facts["pronoun"] = canonical
    else:
        # If no fuzzy match, assume it might be a name or unknown noun
        # Names are often capital or standalone proper nouns
        if word and word[0].isupper():
            facts["name"] = word
    
    return facts


# ── Integration with memory_db ──────────────────────────────────────────────

def get_memory_fuzzy(key: str, threshold: float = 0.80) -> Optional[Tuple[str, str, float]]:
    """
    Retrieve a fact from memory using fuzzy matching on the stored key.
    
    This is a placeholder for integration with memory_db.py's get_memory().
    
    Returns:
        (value, retrieval_method, confidence_score) or None
    
    Retrieval methods: 'exact', 'fuzzy', 'similar_key'
    """
    # This will be integrated with actual memory_db calls
    # For now, it's a stub that can be called by the chat flow
    try:
        from memory_db import get_memory
        value = get_memory(key, language="english")
        if value:
            return (value, "exact", 1.0)
    except ImportError:
        pass
    
    return None
