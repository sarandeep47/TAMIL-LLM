"""
tanglish_tokenizer.py — Word-by-word tokenization for Tanglish with fuzzy matching.

This module provides:
1. tokenize_tanglish() — Break Tanglish text into word tokens with metadata
2. extract_statements_from_tokens() — Parse tokens into facts (greeting, name, location, etc.)
3. Integration with tamil_grammar.py for fuzzy word similarity

Example:
    Input: "vannakam en peru sarandeep naa madurai la irundhu varen"
    Tokens: [
        {"word": "vannakam", "canonical": "vannakam", "category": "greeting", "confidence": 1.0},
        {"word": "en", "canonical": "en", "category": "pronoun", "confidence": 1.0},
        {"word": "peru", "canonical": "peru", "category": "name", "confidence": 1.0},
        {"word": "sarandeep", "canonical": None, "category": "name", "confidence": 0.9},
        ...
    ]
    
    Facts extracted: {
        "greeting": "vannakam",
        "name": "sarandeep",
        "origin": "madurai",
        "verb": "varen"  (came)
    }
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from model.tamil_grammar import find_similar_word, get_word_category, extract_possible_facts_from_word


# ── Token structure ────────────────────────────────────────────────────────

class Token:
    """Represents a single word token with linguistic metadata."""
    
    def __init__(
        self,
        word: str,
        canonical: Optional[str] = None,
        category: Optional[str] = None,
        similarity_score: float = 1.0,
        is_proper_noun: bool = False,
    ):
        self.word = word
        self.canonical = canonical  # Keep as None if not provided
        self.category = category
        self.similarity_score = similarity_score
        self.is_proper_noun = is_proper_noun
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert token to dictionary for serialization."""
        return {
            "word": self.word,
            "canonical": self.canonical,
            "category": self.category,
            "similarity": self.similarity_score,
            "proper_noun": self.is_proper_noun,
        }
    
    def __repr__(self):
        return f"Token({self.word}, canon={self.canonical}, cat={self.category}, sim={self.similarity_score:.2f})"


# ── Tokenization ───────────────────────────────────────────────────────────

def tokenize_tanglish(text: str) -> List[Token]:
    """
    Break Tanglish text into tokens with fuzzy word matching.
    
    Process:
        1. Split text into words
        2. For each word, try exact/fuzzy match against tamil_grammar vocabulary
        3. Assign category and confidence based on similarity
        4. Mark likely proper nouns (capitalized, unknown, etc.)
    
    Args:
        text: Tanglish or Tamil text
    
    Returns:
        List of Token objects with canonical forms and categories
    """
    # Normalize whitespace and split
    words = text.strip().split()
    tokens = []
    
    for word in words:
        # Remove punctuation from word edges (but keep internal structure)
        word_clean = re.sub(r'^[^\w\u0B80-\u0BFF]+|[^\w\u0B80-\u0BFF]+$', '', word)
        if not word_clean:
            continue
        
        # Try to find similar word in vocabulary
        similar = find_similar_word(word_clean)
        
        if similar:
            canonical, score = similar
            category = get_word_category(canonical)
            token = Token(
                word=word_clean,
                canonical=canonical,
                category=category,
                similarity_score=score,
                is_proper_noun=False,
            )
        else:
            # Unknown word — assume it might be a name or proper noun
            is_proper = word_clean[0].isupper() if word_clean else False
            token = Token(
                word=word_clean,
                canonical=None,
                category="unknown",
                similarity_score=0.0,
                is_proper_noun=is_proper,
            )
        
        tokens.append(token)
    
    return tokens


# ── Statement extraction ──────────────────────────────────────────────────────

class Statement:
    """Represents extracted facts from a sequence of tokens."""
    
    def __init__(self):
        self.greeting: Optional[str] = None
        self.subject_pronoun: Optional[str] = None  # naan, neenga, etc.
        self.name: Optional[str] = None
        self.object_pronoun: Optional[str] = None  # en (my), etc.
        self.location: Optional[str] = None
        self.origin: Optional[str] = None  # irundhu (from)
        self.education: Optional[str] = None
        self.verb: Optional[str] = None
        self.verb_tense: Optional[str] = None  # present, past, continuous
        self.other_facts: Dict[str, str] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert statement to dictionary."""
        result = {
            "greeting": self.greeting,
            "subject_pronoun": self.subject_pronoun,
            "name": self.name,
            "object_pronoun": self.object_pronoun,
            "location": self.location,
            "origin": self.origin,
            "education": self.education,
            "verb": self.verb,
            "verb_tense": self.verb_tense,
        }
        result.update(self.other_facts)
        return {k: v for k, v in result.items() if v is not None}
    
    def has_facts(self) -> bool:
        """Check if at least one fact was extracted."""
        return any([
            self.greeting,
            self.name,
            self.location,
            self.origin,
            self.education,
            self.verb,
        ])
    
    def __repr__(self):
        facts = self.to_dict()
        return f"Statement({facts})"


def extract_statements_from_tokens(tokens: List[Token]) -> Statement:
    """
    Parse tokens into extracted facts (statement).
    
    Heuristics:
        1. First "greeting" category token → greeting fact
        2. Pronouns (naan, neenga) → subject_pronoun
        3. "en" or "enoda" or "peru"/"peyar" → object pronoun or name marker
        4. Unknown/capitalized word after possessive/name marker → name
        5. "irundhu" marker → next location word is origin
        6. Location category tokens → location
        7. Verb tokens → verb + infer tense from category
    
    Args:
        tokens: List of Token objects from tokenize_tanglish()
    
    Returns:
        Statement object with extracted facts
    """
    stmt = Statement()
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        # Greetings
        if token.category == "greeting":
            stmt.greeting = token.canonical
            i += 1
            continue
        
        # Subject pronouns (naan, neenga, etc.)
        if token.category == "pronoun" and token.canonical in ["naan", "neenga", "avan", "aval"]:
            stmt.subject_pronoun = token.canonical
            i += 1
            continue
        
        # Possessive markers (en, enoda = my, your) or name markers (peru, peyar = name)
        if token.canonical in ["en", "enoda", "peru", "peyar"]:
            if token.canonical in ["en", "enoda"]:
                stmt.object_pronoun = token.canonical
            
            # Next word is likely the name
            if i + 1 < len(tokens):
                next_token = tokens[i + 1]
                if next_token.is_proper_noun or next_token.category == "unknown":
                    stmt.name = next_token.word
                    i += 2
                    continue
            i += 1
            continue
        
        # Origin markers (irundhu = from)
        if token.canonical in ["irundhu"]:
            stmt.origin = token.canonical
            # Next location token is the origin place
            if i + 1 < len(tokens):
                next_token = tokens[i + 1]
                if next_token.category == "location":
                    stmt.location = next_token.canonical
                    i += 2
                    continue
            i += 1
            continue
        
        # Locations
        if token.category == "location":
            if not stmt.location:
                stmt.location = token.canonical
            i += 1
            continue
        
        # Education-related
        if token.category == "education":
            stmt.education = token.canonical
            i += 1
            continue
        
        # Verbs (with tense inference)
        if token.category and token.category.startswith("verb_"):
            stmt.verb = token.canonical
            tense = token.category.replace("verb_", "")  # present, past, continuous
            stmt.verb_tense = tense
            i += 1
            continue
        
        # Unknown words (potential names if capitalized or proper noun)
        if token.category == "unknown":
            if token.is_proper_noun and not stmt.name:
                stmt.name = token.word
            i += 1
            continue
        
        # Default: skip
        i += 1
    
    return stmt


def parse_tanglish(text: str) -> Tuple[List[Token], Statement]:
    """
    Full pipeline: tokenize and extract facts from Tanglish text.
    
    Returns:
        (list of tokens, extracted statement)
    
    Example:
        >>> tokens, stmt = parse_tanglish("vannakam en peru sarandeep naa madurai la irundhu varen")
        >>> print(stmt.greeting)  # "vannakam"
        >>> print(stmt.name)  # "sarandeep"
        >>> print(stmt.location)  # "madurai"
    """
    tokens = tokenize_tanglish(text)
    stmt = extract_statements_from_tokens(tokens)
    return tokens, stmt


# ── Integration with chat flow ─────────────────────────────────────────────

def detect_intent_with_tokenization(message: str) -> Dict[str, Any]:
    """
    Enhanced intent detection combining tokenization + traditional patterns.
    
    Returns a dict like:
        {
            "original_message": message,
            "tokens": [token dicts],
            "extracted_facts": {...},
            "intents": ["greeting", "user_name", "user_location", ...],
            "confidence": 0.85,
        }
    """
    tokens, stmt = parse_tanglish(message)
    
    intents = []
    confidence = 0.0
    
    # Map extracted facts to chatbot intents
    if stmt.greeting:
        intents.append("greeting")
        confidence += 0.3
    if stmt.name:
        intents.append("user_name")
        confidence += 0.3
    if stmt.location or stmt.origin:
        intents.append("user_location")
        confidence += 0.2
    if stmt.education:
        intents.append("user_school")
        confidence += 0.2
    
    # Normalize confidence
    confidence = min(1.0, confidence)
    
    return {
        "original_message": message,
        "tokens": [t.to_dict() for t in tokens],
        "extracted_facts": stmt.to_dict(),
        "intents": intents,
        "confidence": confidence,
    }
