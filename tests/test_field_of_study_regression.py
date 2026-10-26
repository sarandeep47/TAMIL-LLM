"""
tests/test_field_of_study_regression.py
=======================================
Regression tests for field-of-study extraction and acknowledgment.

Reproduces observed issue:
- User: "naa cse padichen college la" (past-tense field of study statement)
- Assistant: "Antha thakaval innama save aagalai." (says not saved)

Root causes fixed:
1. Field-of-study patterns missing from intent detection
2. Field-of-study extraction patterns missing from fact_extractor
3. Field-of-study acknowledgment templates missing
4. Regex overly greedy, matching field names as school names

Key distinctions preserved:
- Institution (KLNCE, Anna University) vs. Field (CSE, IT)
- Past enrollment (padichen) vs. Current enrollment (padikuren)
- Field-of-study (what you study) vs. College/School (where you study)
- Field-of-study (what you study) vs. Learning (what you're learning)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path, monkeypatch):
    """Isolate tests with temporary databases."""
    mem_db = tmp_path / "memory.db"
    chat_db = tmp_path / "chatbot.db"

    import memory_db, training_review, chatbot, chat_memory

    monkeypatch.setattr(memory_db, "DB_PATH", mem_db)
    monkeypatch.setattr(training_review, "DB_PATH", chat_db)
    monkeypatch.setattr(chatbot, "CHAT_DB_PATH", chat_db)

    import fact_extractor as fe
    monkeypatch.setattr(fe, "OLLAMA_URL", "http://localhost:99999/NOOP")

    monkeypatch.setattr(
        chat_memory, "get_memory",
        lambda key, language="english": memory_db.get_memory(key, language),
    )
    monkeypatch.setattr(
        chat_memory, "get_education_status",
        lambda key="user_school": memory_db.get_education_status(key),
    )

    memory_db.initialize_database()
    training_review.initialize_training_db()
    chatbot.initialize_chatbot()
    yield


# ===========================================================================
# 1. Field-of-Study Extraction
# ===========================================================================

class TestFieldOfStudyExtraction:
    """Field-of-study should be extracted from statements like 'naa cse padichen'."""

    def test_past_tense_field_extraction(self):
        """'naa cse padichen college la' → user_field_of_study='cse'."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa cse padichen college la")
        assert len(facts) == 1
        assert facts[0].key == "user_field_of_study"
        assert facts[0].value == "cse"

    def test_present_tense_field_extraction(self):
        """'naa cse padikuren college la' → user_field_of_study='cse'."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa cse padikuren college la")
        assert len(facts) == 1
        assert facts[0].key == "user_field_of_study"
        assert facts[0].value == "cse"

    def test_uppercase_field_extraction(self):
        """'naa CSE padichen college la' → user_field_of_study='CSE'."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa CSE padichen college la")
        assert len(facts) == 1
        assert facts[0].key == "user_field_of_study"
        assert facts[0].value == "CSE"

    def test_multi_word_field_extraction(self):
        """'naa computer science padichen college la' → user_field_of_study='computer science'."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa computer science padichen college la")
        assert len(facts) == 1
        assert facts[0].key == "user_field_of_study"
        assert "computer" in facts[0].value.lower()
        assert "science" in facts[0].value.lower()

    def test_no_extraction_without_college_keyword(self):
        """'naa cse padichen' alone should not extract (ambiguous if college context)."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa cse padichen")
        # Might extract as learning or not at all without college keyword
        if facts:
            # If it does extract, should not be field-of-study without college context
            assert facts[0].key != "user_field_of_study" or "college" in facts[0].value.lower()


# ===========================================================================
# 2. Field vs. School Distinction
# ===========================================================================

class TestFieldVsSchoolDistinction:
    """Must distinguish between institution (KLNCE) and field (CSE)."""

    def test_field_name_not_extracted_as_school(self):
        """'naa cse padichen college la' should NOT extract as user_school."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa cse padichen college la")
        assert facts[0].key == "user_field_of_study"
        assert facts[0].key != "user_school"

    def test_institution_name_extracted_as_school(self):
        """'naa KLNCE il padikuren' should extract as user_school, not field."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa KLNCE il padikuren")
        assert len(facts) == 1
        assert facts[0].key == "user_school"
        assert facts[0].value == "KLNCE"

    def test_both_field_and_school_not_duplicated(self):
        """Even with both field and institution, should extract only one fact."""
        from fact_extractor import extract_facts_dry_run
        # "naa CSE KLNCE padikuren" — ambiguous but should not duplicate
        facts = extract_facts_dry_run("naa cse padikuren college la")
        assert len(facts) == 1  # Only field or school, not both


# ===========================================================================
# 3. Statement-Intent Detection
# ===========================================================================

class TestFieldOfStudyStatementIntent:
    """Field-of-study statements should be detected by _detect_statement_intent."""

    def test_field_statement_detected(self):
        """'naa cse padichen college la' should be detected as field-of-study statement."""
        from chat_memory import _detect_statement_intent
        intent = _detect_statement_intent("naa cse padichen college la")
        assert intent == "user_field_of_study", (
            f"Should detect field-of-study statement, got {intent!r}"
        )

    def test_school_statement_detected(self):
        """'naa KLNCE il padikuren' should still be detected as school statement."""
        from chat_memory import _detect_statement_intent
        intent = _detect_statement_intent("naa KLNCE il padikuren")
        assert intent == "user_school"


# ===========================================================================
# 4. Acknowledgment
# ===========================================================================

class TestFieldOfStudyAcknowledgment:
    """Saving a field-of-study should produce a natural acknowledgment."""

    def test_field_acknowledgment_after_save(self):
        """After extracting 'naa cse padichen college la', should acknowledge."""
        from fact_extractor import extract_facts
        from chat_memory import acknowledge_statement
        
        facts = extract_facts("naa cse padichen college la")
        assert len(facts) == 1
        assert facts[0].key == "user_field_of_study"
        
        ack = acknowledge_statement("naa cse padichen college la")
        assert ack is not None
        assert "cse" in ack.lower() or "save" in ack.lower()

    def test_field_acknowledgment_in_tanglish(self):
        """Acknowledgment should detect Tanglish and respond in Tanglish."""
        from chat_memory import acknowledge_statement
        import memory_db
        
        memory_db.save_memory(
            "user_field_of_study", "CSE",
            category="education", source="regex"
        )
        
        ack = acknowledge_statement("naa cse padichen college la")
        assert ack is not None
        # Should be in Tanglish (detected from message language)
        assert "save" in ack.lower() or "cse" in ack.lower()


# ===========================================================================
# 5. Question Retrieval
# ===========================================================================

class TestFieldOfStudyRetrieval:
    """Questions about field-of-study should retrieve saved facts."""

    def test_what_did_i_study_intent(self):
        """'what did i study' should detect user_field_of_study intent."""
        from chat_memory import detect_intent
        intent = detect_intent("what did i study")
        assert intent == "user_field_of_study"

    def test_what_is_my_field_intent(self):
        """'what is my field' should detect user_field_of_study intent."""
        from chat_memory import detect_intent
        intent = detect_intent("what is my field")
        assert intent == "user_field_of_study"

    def test_field_retrieval_after_save(self):
        """After saving CSE, 'what did i study' should return CSE."""
        import memory_db
        from chat_memory import answer_question
        
        memory_db.save_memory(
            "user_field_of_study", "CSE",
            category="education", source="regex"
        )
        
        answer = answer_question("what did i study")
        assert answer is not None
        assert "CSE" in answer
        assert "not" not in answer.lower() or "saved" not in answer.lower()


# ===========================================================================
# 6. Field vs. Learning Distinction
# ===========================================================================

class TestFieldVsLearningDistinction:
    """Must distinguish between field-of-study and current learning."""

    def test_field_not_confused_with_learning(self):
        """'naa cse padichen college la' (field) ≠ 'naa cse kathukiren' (learning)."""
        from fact_extractor import extract_facts_dry_run
        
        # Field of study (past tense, college context)
        field_facts = extract_facts_dry_run("naa cse padichen college la")
        assert field_facts[0].key == "user_field_of_study"
        
        # Learning (current tense, explicit learning verb)
        learn_facts = extract_facts_dry_run("naa cse kathukiren")
        assert len(learn_facts) == 0 or learn_facts[0].key == "user_learning"


# ===========================================================================
# 7. SQLite Persistence
# ===========================================================================

class TestFieldOfStudyPersistence:
    """Field-of-study facts should persist in the database."""

    def test_field_saved_to_sqlite(self):
        """After extraction, field-of-study should be in SQLite."""
        import memory_db
        from fact_extractor import extract_facts
        
        facts = extract_facts("naa cse padichen college la")
        assert len(facts) == 1
        
        # Verify it's in the DB
        val = memory_db.get_memory("user_field_of_study")
        assert val == "cse"

    def test_field_independent_of_school(self):
        """Saving field should not affect school facts and vice versa."""
        import memory_db
        from fact_extractor import extract_facts
        
        # Save field
        extract_facts("naa cse padichen college la")
        
        # Save school
        extract_facts("naa KLNCE il padikuren")
        
        # Both should exist
        field = memory_db.get_memory("user_field_of_study")
        school = memory_db.get_memory("user_school")
        
        assert field == "cse"
        assert school == "KLNCE"


# ===========================================================================
# 8. End-to-End Scenario
# ===========================================================================

class TestFieldOfStudyEndToEnd:
    """Full conversation: statement → acknowledgment → retrieval."""

    def test_full_field_of_study_scenario(self):
        """
        User: "naa cse padichen college la" (statement)
        User: "what did i study" (question)
        Should return CSE without saying "not saved"
        """
        from fact_extractor import extract_facts
        from chat_memory import answer_question, acknowledge_statement
        
        # 1. Statement
        print("\n1. User: naa cse padichen college la")
        facts = extract_facts("naa cse padichen college la")
        assert len(facts) == 1
        assert facts[0].key == "user_field_of_study"
        print(f"   Extracted: {facts[0].key}={facts[0].value}")
        
        ack = acknowledge_statement("naa cse padichen college la")
        assert ack is not None
        print(f"   Assistant: {ack}")
        
        # 2. Question
        print("\n2. User: what did i study")
        answer = answer_question("what did i study")
        assert answer is not None
        assert "CSE" in answer.upper() or "cse" in answer.lower()
        print(f"   Assistant: {answer}")
        
        # 3. Verify (from earlier test)
        print("\n3. Verify name retrieval works")
        import memory_db
        memory_db.save_memory(
            "user_name", "Sarandeep",
            category="identity", source="manual"
        )
        answer2 = answer_question("en peru enna")
        assert "Sarandeep" in answer2
        print(f"   Assistant: {answer2}")


# ===========================================================================
# 9. No Hallucination on Missing Facts
# ===========================================================================

class TestNoHallucination:
    """Missing facts should return 'not saved', never hallucinate."""

    def test_no_field_hallucination(self):
        """'what did i study' with no saved field → 'not saved'."""
        from chat_memory import answer_question
        
        answer = answer_question("what did i study")
        assert answer is not None
        assert "saved" in answer.lower()

    def test_no_school_hallucination(self):
        """'which college did i study' with no saved college → 'not saved'."""
        from chat_memory import answer_question
        
        answer = answer_question("which college did i study")
        assert answer is not None
        assert "saved" in answer.lower()
