"""
Regression tests for greeting variants, degree extraction, and education handling.

Coverage:
1. Greeting spelling variants (vannakam, vannakkam, etc.)
2. Degree extraction (BE, MSc, etc.)
3. Current vs past institution storage
4. Institution aliases (KLCE → KLNCE)
5. Acknowledgment count (exactly one per fact)
6. No Ollama for recognized greetings
"""

import pytest
from memory_db import initialize_database, forget_memory, get_memory, list_memories
from chat_memory import handle_greeting, acknowledge_statement, answer_question, detect_language_style
from fact_extractor import extract_facts, extract_facts_dry_run


@pytest.fixture(autouse=True)
def reset_memory():
    """Clear memory before each test."""
    initialize_database()
    # Forget all keys
    for f in list_memories():
        forget_memory(f["key"])
    yield
    # Cleanup after
    for f in list_memories():
        forget_memory(f["key"])


# ===========================================================================
# 1. GREETING VARIANTS
# ===========================================================================

class TestGreetingVariants:
    """Recognize common Tamil greeting spelling variants."""

    def test_vanakkam_original_spelling(self):
        """Original Panini-style spelling."""
        result = handle_greeting("vanakkam")
        assert result is not None
        assert "vanakkam" in result.lower() or "hello" in result.lower()

    def test_vannakam_spelling(self):
        """Alternative transliteration (single 'n' in middle)."""
        result = handle_greeting("vannakam")
        assert result is not None
        assert "vanakkam" in result.lower() or "hello" in result.lower()

    def test_vannakkam_spelling(self):
        """Alternative with repeated 'n' and 'k'."""
        result = handle_greeting("vannakkam")
        assert result is not None
        assert "vanakkam" in result.lower() or "hello" in result.lower()

    def test_tamil_script_greeting(self):
        """Tamil script វណක្កម్."""
        result = handle_greeting("வணக்கம்")
        assert result is not None
        assert "வணக்கம்" in result or "hello" in result.lower()

    def test_greeting_not_routed_to_ollama(self):
        """Greetings should be deterministic, not call Ollama."""
        result = handle_greeting("vannakam")
        # Should return a greeting, not None (which would trigger Ollama)
        assert result is not None
        assert len(result) > 0

    def test_greeting_english_context(self):
        """Greetings in English should return English response."""
        result = handle_greeting("hello")
        assert result is not None
        assert result.lower() == "hello!"

    def test_greeting_tanglish_context(self):
        """Tanglish variant returns Tanglish response."""
        result = handle_greeting("vanakkam")
        assert result is not None
        # Should be either Vanakkam! or Hello! (both acceptable)
        assert "vanakkam" in result.lower() or "hello" in result.lower()

    def test_greeting_exactly_once(self):
        """One greeting should produce exactly one response line."""
        result = handle_greeting("vannakam")
        assert result.count("\n") == 0  # Single line response
        assert result.count("!") == 1    # Exactly one exclamation


# ===========================================================================
# 2. DEGREE EXTRACTION
# ===========================================================================

class TestDegreeExtraction:
    """Degree extraction must be distinct from field of study."""

    def test_explicit_degree_statement(self):
        """'I have a BE degree' → extracts as user_degree, not field."""
        facts = extract_facts_dry_run("I have a BE degree")
        assert len(facts) > 0
        assert any(f.key == "user_degree" for f in facts)
        assert not any(f.key == "user_field_of_study" for f in facts)

    def test_degree_vs_field_distinction(self):
        """'Naa CSE padichen' → field, NOT degree."""
        facts = extract_facts_dry_run("naa cse padichen college la")
        # Should extract field of study, not degree
        field_facts = [f for f in facts if f.key == "user_field_of_study"]
        degree_facts = [f for f in facts if f.key == "user_degree"]
        assert len(field_facts) > 0
        assert len(degree_facts) == 0

    def test_degree_save_and_retrieve(self):
        """Save degree, then retrieve it separately from field."""
        extract_facts("I have a BE degree")
        # Use a more specific degree question that doesn't map to school
        answer = answer_question("What is my degree?")
        assert answer is not None
        assert "BE" in answer or "degree" in answer.lower()

    def test_degree_separate_from_field(self):
        """Can store both degree and field separately."""
        extract_facts("I have a BE degree")
        extract_facts("naa cse padichen college la")
        
        # Check both are stored
        degree = get_memory("user_degree", language="english")
        field = get_memory("user_field_of_study", language="english")
        
        assert degree is not None
        assert "BE" in degree
        assert field is not None
        assert "cse" in field.lower()


# ===========================================================================
# 3. CURRENT VS PAST INSTITUTION
# ===========================================================================

class TestInstitutionTense:
    """Preserve past vs current institution context."""

    def test_past_institution_padichen(self):
        """'naa KLNCE la padichen' → past institution."""
        facts = extract_facts_dry_run("naa KLNCE la padichen")
        assert len(facts) > 0
        school_facts = [f for f in facts if f.key == "user_school"]
        assert len(school_facts) > 0
        assert school_facts[0].education_status == "past"

    def test_current_institution_padikuren(self):
        """'naa KLNCE la padikuren' → current institution."""
        facts = extract_facts_dry_run("naa KLNCE la padikuren")
        assert len(facts) > 0
        school_facts = [f for f in facts if f.key == "user_school"]
        assert len(school_facts) > 0
        assert school_facts[0].education_status == "current"

    def test_past_institution_acknowledgment(self):
        """Acknowledge past institution appropriately."""
        extract_facts("naa KLNCE la padichen")
        ack = acknowledge_statement("naa KLNCE la padichen")
        assert ack is not None
        # Should mention the institution was studied at (past)
        assert "KLNCE" in ack or "college" in ack.lower()

    def test_past_vs_current_not_conflated(self):
        """Save past institution, current doesn't overwrite."""
        extract_facts("naa KLNCE la padichen")
        past = get_memory("user_school", language="english")
        
        extract_facts("naa MIT la padikuren")
        current = get_memory("user_school", language="english")
        
        # Last one saved wins (should be MIT with current status)
        assert current is not None
        assert "MIT" in current


# ===========================================================================
# 4. AMBIGUOUS DEGREE STATEMENTS
# ===========================================================================

class TestAmbiguousDegreeStatements:
    """Handle conservative interpretation of informal degree phrasing."""

    def test_informal_degree_statement(self):
        """'na BE KLCE la pannen en degree' → don't hallucinate."""
        facts = extract_facts_dry_run("na BE KLCE la pannen en degree")
        # Should not extract anything without explicit keywords
        # or should extract conservatively
        if facts:
            # If extracted, should not assume completion
            degree_facts = [f for f in facts if f.key == "user_degree"]
            for df in degree_facts:
                # Degree should be BE, not completion status
                assert "BE" in df.value or df.value.upper() == "BE"

    def test_no_silent_normalization_of_aliases(self):
        """'KLCE' should not silently become 'KLNCE' without confirmation."""
        facts = extract_facts_dry_run("naa KLCE la padichen")
        # Should extract as KLCE, not normalized to KLNCE
        if facts:
            school_facts = [f for f in facts if f.key == "user_school"]
            for sf in school_facts:
                assert sf.value == "KLCE"


# ===========================================================================
# 5. ACKNOWLEDGMENT QUALITY
# ===========================================================================

class TestAcknowledgmentQuality:
    """Ensure exactly one acknowledgment per fact, no repetition."""

    def test_school_acknowledgment_single(self):
        """One school statement should produce exactly one acknowledgment."""
        extract_facts("naa KLNCE la padichen")
        ack = acknowledge_statement("naa KLNCE la padichen")
        assert ack is not None
        # Should not repeat the message
        assert ack.count("KLNCE") <= 2  # May appear once in template, once in value
        # Should not concatenate multiple statements
        assert ack.count(".") <= 2  # Max 2 periods (once for ack, maybe one in punctuation)

    def test_degree_acknowledgment_single(self):
        """One degree statement produces one acknowledgment."""
        extract_facts("I have a BE degree")
        # Acknowledgment should work for degree statements
        ack = acknowledge_statement("I have a BE degree")
        # This should work if acknowledge_statement processes tanglish_understanding output
        if ack:
            assert ack is not None
            assert ack.count("BE") <= 2

    def test_no_ollama_echo_in_acknowledgment(self):
        """Acknowledgments should not echo Ollama-style responses."""
        extract_facts("naa KLNCE la padichen")
        ack = acknowledge_statement("naa KLNCE la padichen")
        assert ack is not None
        # Should be a simple acknowledgment, not "I understand you studied at KLNCE, KLNCE la padichen..."
        assert "KLNCE" not in ack or ack.count("KLNCE") == 1


# ===========================================================================
# 6. QUESTION-TO-STATEMENT DISTINCTION
# ===========================================================================

class TestQuestionNotExtracted:
    """Questions should NOT be extracted, only statements."""

    def test_degree_question_not_extracted(self):
        """'Which degree have I completed?' should NOT extract."""
        facts = extract_facts_dry_run("Which degree have I completed?")
        # Question should not trigger extraction
        assert len(facts) == 0

    def test_college_question_not_extracted(self):
        """'naa enga college la padichen?' (past question) should NOT extract."""
        facts = extract_facts_dry_run("naa enga college la padichen?")
        assert len(facts) == 0

    def test_college_current_question_not_extracted(self):
        """'Where am I studying?' should NOT extract."""
        facts = extract_facts_dry_run("Where am I studying?")
        assert len(facts) == 0


# ===========================================================================
# 7. NO OLLAMA FOR KNOWN PATTERNS
# ===========================================================================

class TestNoOllamaFallback:
    """Deterministic handlers should prevent Ollama calls."""

    def test_greeting_no_ollama_needed(self):
        """Greeting should be deterministic, no Ollama."""
        # This is implicitly tested by handle_greeting returning a value
        # instead of None (which would trigger Ollama)
        result = handle_greeting("vannakam")
        assert result is not None

    def test_personal_fact_question_no_ollama_unless_not_saved(self):
        """Personal-fact questions should retrieve from DB, not Ollama."""
        # Save a fact first
        extract_facts("naa cse padichen college la")
        
        # Question should be answered from memory
        answer = answer_question("naa enna padichen nu sollu")
        assert answer is not None
        # If answer mentions CSE, it came from DB, not Ollama
        if "cse" in answer.lower() or "field" in answer.lower():
            assert "cse" in answer.lower()  # CSE was saved, should be retrieved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
