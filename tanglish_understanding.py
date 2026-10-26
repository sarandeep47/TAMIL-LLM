"""
tanglish_understanding.py — Compositional Tanglish understanding layer.

Converts raw user messages into structured intents with semantic meaning.

Architecture:
- Normalize input (spelling variants, whitespace)
- Tokenize and recognize Tanglish vocabulary
- Apply compositional pattern matching (subject + verb + object)
- Infer sentence type, tense, and memory operation
- Return TanglishIntent object for downstream routing

Usage:
    from tanglish_understanding import understand_tanglish
    intent = understand_tanglish("naa madurai la iruken")
    if intent.operation == 'save':
        save_memory(intent.memory_key, intent.entities['value'])
    elif intent.operation == 'retrieve':
        return get_memory(intent.memory_key)
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Optional


@dataclass
class TanglishIntent:
    """Structured representation of a Tanglish sentence's intent and meaning."""
    
    sentence_type: str           # 'statement', 'question', 'recall', 'greeting', 'unclear'
    topic: Optional[str]         # 'name', 'location', 'school', 'field_of_study', 'learning', 'workplace', 'job', None
    tense: str                   # 'current', 'past', 'unknown'
    operation: str               # 'save', 'retrieve', 'acknowledge', 'chat'
    entities: dict = field(default_factory=dict)  # {'subject': 'user', 'value': 'CSE', 'entity_type': 'field'}
    memory_key: Optional[str] = None  # Canonical fact key (user_location, user_field_of_study, etc.)
    confidence: float = 0.0      # 0.0–1.0
    language_style: str = "english"  # 'tamil', 'tanglish', 'english'
    original_message: str = ""
    
    def is_personal_fact(self) -> bool:
        """True if this intent targets a saved personal memory."""
        return self.topic in {
            'name', 'location', 'school', 'field_of_study', 'learning',
            'workplace', 'job', 'skill', 'goal', 'interest', 'language'
        }


# ── Token Normalization ──────────────────────────────────────────────────────

_SPELLING_VARIANTS = {
    # Pronoun variants
    'naa': {'naa', 'na', 'naan'},
    'en': {'en', 'ennoda', 'ennodai', 'enakku'},  # possessive/oblique variants
    'neenga': {'neenga', 'neeng', 'neeya'},
    
    # Question words
    'enna': {'enna', 'ennu'},
    'enga': {'enga', 'enge', 'engey'},
    'entha': {'entha', 'antha'},
    'yaaru': {'yaaru', 'yaru'},
    
    # Study verbs
    'padichen': {'padichen', 'padichaen', 'padichae', 'padi', 'padita'},
    'padikuren': {'padikuren', 'padikittu', 'padikitu', 'padikren'},
    'padikiren': {'padikiren', 'padikittu'},  # learning (vs. studying at college)
    
    # Location verbs
    'iruken': {'iruken', 'irukken', 'irundhen', 'irkiren'},
    'vasikiren': {'vasikiren', 'vasikittu'},
    
    # Quotative particle
    'nu': {'nu', 'nnu', 'n'},
    
    # Locative postposition
    'la': {'la', 'ile', 'il', 'ille', 'le', 'le'},
    
    # Say/tell verbs
    'sonnen': {'sonnen', 'sonna', 'sonnaen'},
    'sollu': {'sollu', 'sollunga', 'sollren'},
}

def _normalize_token(token: str) -> str:
    """
    Map spelling variant to canonical form.
    E.g., 'padichen' and 'padichaen' both map to 'padichen'.
    """
    token_lower = token.lower()
    for canonical, variants in _SPELLING_VARIANTS.items():
        if token_lower in variants:
            return canonical
    return token_lower


def _tokenize_tanglish(text: str) -> list[str]:
    """
    Split Tanglish text into tokens, preserving Tamil script words.
    Handle common punctuation.
    """
    # Replace common punctuation with spaces, preserve alphanumeric and Tamil
    text = re.sub(r'[?!.,;:]', ' ', text)
    # Split on whitespace and filter empty strings
    tokens = [t.lower() for t in text.split() if t.strip()]
    return tokens


# ── Vocabulary Recognition ──────────────────────────────────────────────────

_SUBJECTS = {'naa', 'na', 'en', 'neenga', 'yaaru'}
_QUESTION_WORDS = {'enna', 'enga', 'entha', 'yaaru', 'yeppa'}
_STUDY_VERBS_PAST = {'padichen', 'padi'}
_STUDY_VERBS_PRESENT = {'padikuren', 'padikittu', 'padikiren'}
_LOCATION_VERBS = {'iruken', 'vasikiren'}
_SAYING_VERBS = {'sonnen', 'sollu'}
_POSTPOSITIONS = {'la', 'ile', 'il'}


# ── Pattern Recognition ──────────────────────────────────────────────────────

def _detect_sentence_type(tokens: list[str], original: str) -> str:
    """
    Classify sentence as 'statement', 'question', 'recall', 'greeting', or 'unclear'.
    """
    # Check for question markers
    if '?' in original or any(qw in tokens for qw in _QUESTION_WORDS):
        # Exclude recall pattern: "... nu sonnen" (I said X)
        if 'nu' in tokens and 'sonnen' in tokens:
            return 'recall'
        return 'question'
    
    # Check for recall pattern: "nu sonnen" or "sollu" (remind me / I said / tell me)
    if ('nu' in tokens and 'sonnen' in tokens) or 'sollu' in tokens:
        return 'recall'
    
    # Check for greetings
    if any(token in {'vanakkam', 'namaskaram', 'hello', 'hi'} for token in tokens):
        return 'greeting'
    
    # Check for declarative statement patterns
    if any(v in tokens for v in _STUDY_VERBS_PAST | _STUDY_VERBS_PRESENT | _LOCATION_VERBS):
        return 'statement'
    
    # Fallback: if no clear markers, assume unclear
    return 'unclear'


def _infer_tense(tokens: list[str]) -> str:
    """
    Infer tense from verb forms.
    'past': padichen, sonnen, etc.
    'current': padikuren, iruken, vasikiren
    'unknown': if no tense verb present
    """
    if any(v in tokens for v in _STUDY_VERBS_PAST | {'sonnen'}):
        return 'past'
    if any(v in tokens for v in _STUDY_VERBS_PRESENT | _LOCATION_VERBS):
        return 'current'
    return 'unknown'


def _extract_topic_and_key(tokens: list[str], sentence_type: str, tense: str) -> tuple[str | None, str | None]:
    """
    Identify the topic (name, location, school, field_of_study, etc.) and memory key.
    
    Returns (topic, canonical_memory_key).
    """
    # Education topics (school, field)
    if 'padichen' in tokens or 'padikuren' in tokens or 'padikittu' in tokens:
        # Distinguish: school vs. field of study based on context
        # "naa CSE padichen college la" → field (CSE)
        # "naa KLNCE il padichen" → school (KLNCE)
        # Heuristic: if contains college/school keyword → school; else field
        if any(w in tokens for w in {'college', 'school', 'university', 'kalloori'}):
            if 'padichen' in tokens:
                return ('school', 'user_school')
            else:
                return ('school', 'user_school')
        else:
            return ('field_of_study', 'user_field_of_study')
    
    # Location topics
    if any(v in tokens for v in _LOCATION_VERBS) or 'la' in tokens or 'il' in tokens:
        return ('location', 'user_location')
    
    # Name topics
    if 'peru' in tokens or 'peyar' in tokens or 'peru' in tokens:
        return ('name', 'user_name')
    
    # Learning topics
    if 'padikiren' in tokens or 'kathukkiren' in tokens:
        return ('learning', 'user_learning')
    
    # Workplace topics
    if any(w in tokens for w in {'velai', 'work', 'office', 'company'}):
        return ('workplace', 'user_workplace')
    
    return (None, None)


def _extract_entity_value(tokens: list[str], original: str, topic: str | None) -> dict:
    """
    Extract the entity value (e.g., 'CSE', 'Madurai', 'Sarandeep').
    
    Heuristic: look for capitalized words, known place names, or word after "la"/"il".
    """
    entities = {}
    
    # Extract subject (usually first person: naa, en)
    if any(s in tokens for s in _SUBJECTS):
        entities['subject'] = 'user'
    
    # Extract value based on topic
    if topic == 'location':
        # Look for capitalized word or word after "la"/"il"
        for i, token in enumerate(tokens):
            if token in _POSTPOSITIONS and i + 1 < len(tokens):
                entities['value'] = tokens[i + 1].capitalize()
                break
        # Fallback: look for capitalized words in original
        if 'value' not in entities:
            capitals = [w for w in original.split() if w and w[0].isupper()]
            if capitals:
                entities['value'] = capitals[0]
    
    elif topic == 'field_of_study':
        # Look for acronyms or field names (usually capitalized, 2-4 chars)
        for token in tokens:
            if len(token) <= 5 and token not in _SUBJECTS and token not in _POSTPOSITIONS:
                if token not in _QUESTION_WORDS and token not in _LOCATION_VERBS:
                    entities['value'] = token.upper()
                    break
    
    elif topic == 'name':
        # Look for non-Tamil, non-particle words (usually proper nouns)
        for token in tokens:
            if token not in _SUBJECTS and token not in {'peru', 'peyar'} and len(token) > 2:
                entities['value'] = token.capitalize()
                break
    
    elif topic == 'school':
        # Look for capitalized acronyms or institution names
        capitals = [w for w in original.split() if w and w[0].isupper() and 'college' not in w.lower()]
        if capitals:
            entities['value'] = capitals[0]
    
    return entities


def _infer_operation(sentence_type: str, topic: str | None) -> str:
    """
    Decide the operation: 'save', 'retrieve', 'acknowledge', or 'chat'.
    """
    if sentence_type == 'statement':
        return 'save'
    elif sentence_type in {'question', 'recall'}:
        return 'retrieve'
    elif sentence_type == 'greeting':
        return 'chat'
    else:
        return 'chat'


def _detect_language_style(text: str) -> str:
    """Detect if input is Tamil script, Tanglish, or English."""
    if any('\u0B80' <= ch <= '\u0BFF' for ch in text):
        return 'tamil'
    # Check for Tanglish markers
    tokens = set(t.lower() for t in _tokenize_tanglish(text))
    if tokens & _SUBJECTS | _QUESTION_WORDS | _STUDY_VERBS_PAST | _STUDY_VERBS_PRESENT:
        return 'tanglish'
    return 'english'


# ── Main API ─────────────────────────────────────────────────────────────────

def understand_tanglish(message: str) -> TanglishIntent:
    """
    Analyze a Tanglish/Tamil/English message and return a structured intent.
    
    Pipeline:
    1. Normalize tokens
    2. Detect sentence type (statement, question, recall, greeting, unclear)
    3. Infer tense (past, current, unknown)
    4. Identify topic (name, location, school, field_of_study, etc.)
    5. Extract entity values
    6. Decide operation (save, retrieve, acknowledge, chat)
    7. Calculate confidence score
    
    Args:
        message: User input (Tanglish, Tamil script, or English)
    
    Returns:
        TanglishIntent object with structured meaning
    """
    # Normalize and tokenize
    tokens = _tokenize_tanglish(message)
    tokens = [_normalize_token(t) for t in tokens]
    
    # Detect language style
    language_style = _detect_language_style(message)
    
    # Detect sentence type
    sentence_type = _detect_sentence_type(tokens, message)
    
    # Infer tense
    tense = _infer_tense(tokens)
    
    # Extract topic and memory key
    topic, memory_key = _extract_topic_and_key(tokens, sentence_type, tense)
    
    # Extract entity values
    entities = _extract_entity_value(tokens, message, topic)
    
    # Decide operation
    operation = _infer_operation(sentence_type, topic)
    
    # Calculate confidence
    # Higher confidence if: topic detected + entities extracted + sentence type clear
    confidence = 0.0
    if sentence_type != 'unclear':
        confidence += 0.3
    if topic is not None:
        confidence += 0.3
    if entities.get('value'):
        confidence += 0.2
    if memory_key is not None:
        confidence += 0.2
    
    confidence = min(confidence, 1.0)
    
    return TanglishIntent(
        sentence_type=sentence_type,
        topic=topic,
        tense=tense,
        operation=operation,
        entities=entities,
        memory_key=memory_key,
        confidence=confidence,
        language_style=language_style,
        original_message=message,
    )


if __name__ == "__main__":
    # Quick test
    test_cases = [
        "naa madurai la iruken",
        "naa enna padichen",
        "naa cse padichen college la",
        "naa enga college la padichen",
        "en peru sarandeep",
        "naa enga iruken nu sonnen",
        "vanakkam",
    ]
    
    for msg in test_cases:
        intent = understand_tanglish(msg)
        print(f"Message: {msg}")
        print(f"  Type: {intent.sentence_type}, Topic: {intent.topic}, Tense: {intent.tense}")
        print(f"  Operation: {intent.operation}, Key: {intent.memory_key}")
        print(f"  Confidence: {intent.confidence:.2f}, Entities: {intent.entities}")
        print()
