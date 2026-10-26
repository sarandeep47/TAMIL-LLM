"""
tests/test_college_retrieval_regression.py
===========================================
Regression tests for college-memory retrieval failures.

Reproduces observed issues:
- "naa KLNCE il padikuren" → memory saved: school, school (DUPLICATE)
- "naa enga padikuren" → "Antha thakaval innama save aagalai." (NOT RETRIEVED)
- "naa entha college la padikuren" → "Antha thakaval innama save aagalai." (NOT RETRIEVED)
- "Which degree have I completed?" → correctly says not saved ✓
- "naa enna kalloori il padikuren" → repeats question (NOT RETRIEVED)

The root causes fixed:
1. Missing intent patterns for "enga", "entha college", "enna kalloori" variants
2. Learning regex overmatching "I am studying at X"
3. School regex capturing postposition "KLNCE il" instead of just "KLNCE"
4. Duplicate fact extraction due to multiple regex patterns matching school
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
# 1. Regression: Missing intent patterns for college questions
# ===========================================================================

class TestMissingIntentPatterns:
    """These variants were not detected, falling through to "not saved"."""

    def test_naa_enga_padikuren_intent_detected(self):
        """'naa enga padikuren' (where am I studying?) must detect user_school intent."""
        from chat_memory import detect_intent
        intent = detect_intent("naa enga padikuren")
        assert intent == "user_school", (
            f"'naa enga padikuren' must return user_school intent, got {intent!r}"
        )

    def test_naa_entha_college_la_padikuren_intent_detected(self):
        """'naa entha college la padikuren' must detect user_school intent."""
        from chat_memory import detect_intent
        intent = detect_intent("naa entha college la padikuren")
        assert intent == "user_school", (
            f"'naa entha college la padikuren' must return user_school, got {intent!r}"
        )

    def test_naa_enna_kalloori_il_padikuren_intent_detected(self):
        """'naa enna kalloori il padikuren' must detect user_school intent."""
        from chat_memory import detect_intent
        intent = detect_intent("naa enna kalloori il padikuren")
        assert intent == "user_school", (
            f"'naa enna kalloori il padikuren' must return user_school, got {intent!r}"
        )


# ===========================================================================
# 2. Regression: Duplicate fact extraction
# ===========================================================================

class TestNoDuplicateExtraction:
    """Multiple regex patterns should not produce duplicate facts."""

    def test_naa_college_il_padikuren_single_extraction(self):
        """'naa KLNCE il padikuren' should extract exactly ONE user_school fact."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa KLNCE il padikuren")
        assert len(facts) == 1, (
            f"Should extract 1 fact, got {len(facts)}: {facts}"
        )
        assert facts[0].key == "user_school"
        assert facts[0].value == "KLNCE"
        assert facts[0].education_status == "current"

    def test_i_am_studying_at_single_extraction(self):
        """'I am studying at KLNCE' should extract one school fact, not school + learning."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("I am studying at KLNCE")
        assert len(facts) == 1, (
            f"Should extract 1 fact, got {len(facts)}: {[f.key for f in facts]}"
        )
        assert facts[0].key == "user_school"
        assert facts[0].value == "KLNCE"
        assert facts[0].education_status == "current"

    def test_learning_vs_school_distinction(self):
        """Learning 'I'm studying Python' must not match school 'studying at X'."""
        from fact_extractor import extract_facts_dry_run
        
        # "I'm studying Python" → learning
        learning_facts = extract_facts_dry_run("I'm studying Python")
        assert len(learning_facts) == 1
        assert learning_facts[0].key == "user_learning"
        assert learning_facts[0].value == "Python"
        
        # "I'm studying at KLNCE" → school
        school_facts = extract_facts_dry_run("I'm studying at KLNCE")
        assert len(school_facts) == 1
        assert school_facts[0].key == "user_school"
        assert school_facts[0].value == "KLNCE"


# ===========================================================================
# 3. Regression: Regex value clipping
# ===========================================================================

class TestRegexValueClipping:
    """Extracted values should not include postpositions or extra words."""

    def test_school_value_excludes_postposition(self):
        """'naa KLNCE il padikuren' should extract 'KLNCE', not 'KLNCE il'."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("naa KLNCE il padikuren")
        assert facts[0].value == "KLNCE", (
            f"Value should be 'KLNCE', got {facts[0].value!r}"
        )

    def test_school_value_excludes_at(self):
        """'I am studying at KLNCE' should extract 'KLNCE', not 'at KLNCE'."""
        from fact_extractor import extract_facts_dry_run
        facts = extract_facts_dry_run("I am studying at KLNCE")
        assert facts[0].value == "KLNCE", (
            f"Value should be 'KLNCE', got {facts[0].value!r}"
        )


# ===========================================================================
# 4. Regression: Question retrieval (the main issue)
# ===========================================================================

class TestCollegeQuestionRetrieval:
    """Questions about college must retrieve the saved college, not "not saved"."""

    def test_naa_enga_padikuren_retrieves_college(self):
        """After saving KLNCE, 'naa enga padikuren' must return it."""
        import memory_db
        from chat_memory import answer_question
        
        memory_db.save_memory(
            "user_school", "KLNCE",
            category="education", source="regex", education_status="current"
        )
        
        answer = answer_question("naa enga padikuren")
        assert answer is not None
        assert "KLNCE" in answer, (
            f"Answer should contain 'KLNCE', got {answer!r}"
        )
        assert "not" not in answer.lower() or "Antha" not in answer, (
            f"Should not say 'not saved', got {answer!r}"
        )

    def test_naa_entha_college_la_padikuren_retrieves_college(self):
        """After saving KLNCE, 'naa entha college la padikuren' must return it."""
        import memory_db
        from chat_memory import answer_question
        
        memory_db.save_memory(
            "user_school", "KLNCE",
            category="education", source="regex", education_status="current"
        )
        
        answer = answer_question("naa entha college la padikuren")
        assert answer is not None
        assert "KLNCE" in answer
        assert "Antha thakaval" not in answer, (
            f"Should not say 'not saved' (Antha), got {answer!r}"
        )

    def test_naa_enna_kalloori_il_padikuren_retrieves_college(self):
        """After saving KLNCE, 'naa enna kalloori il padikuren' must return it."""
        import memory_db
        from chat_memory import answer_question
        
        memory_db.save_memory(
            "user_school", "KLNCE",
            category="education", source="regex", education_status="current"
        )
        
        answer = answer_question("naa enna kalloori il padikuren")
        assert answer is not None
        assert "KLNCE" in answer
        assert "Antha thakaval" not in answer


# ===========================================================================
# 5. Regression: Degree questions are NOT assumed to imply graduation
# ===========================================================================

class TestDegreeQuestionHonesty:
    """Degree questions must not hallucinate — if no graduation fact is saved,
    the answer must acknowledge that only the college is known."""

    def test_degree_question_with_college_says_not_saved(self):
        """'Which degree have I completed?' with only college saved must say
        the degree info isn't saved, not infer a degree from the college."""
        import memory_db
        from chat_memory import answer_question
        
        memory_db.save_memory(
            "user_school", "KLNCE",
            category="education", source="regex", education_status="current"
        )
        
        answer = answer_question("Which degree have I completed?")
        # Degree is not saved, so should say "hasn't been saved" or similar
        assert answer is not None
        assert "saved" in answer.lower(), (
            f"Degree not saved, should mention 'saved'. Got {answer!r}"
        )

    def test_degree_question_no_college_says_not_saved(self):
        """'What degree do I have?' with no college should say not saved."""
        from chat_memory import answer_question
        
        answer = answer_question("What degree do I have?")
        assert answer is not None
        assert "saved" in answer.lower()


# ===========================================================================
# 6. Regression: Statement acknowledgement is not duplicated
# ===========================================================================

class TestNoAcknowledgmentDuplication:
    """Saving a college fact should produce a single acknowledgement,
    not "Memory saved: school, school" due to duplicate extraction."""

    def test_single_acknowledgement_for_college_statement(self):
        """After extracting 'naa KLNCE il padikuren', acknowledge once."""
        from fact_extractor import extract_facts
        from chat_memory import acknowledge_statement
        
        facts = extract_facts("naa KLNCE il padikuren")
        assert len(facts) == 1, (
            f"Should extract 1 fact, got {len(facts)}"
        )
        
        ack = acknowledge_statement("naa KLNCE il padikuren")
        assert ack is not None
        assert ack.count("save") == 1 or "save" not in ack.lower(), (
            f"Acknowledgement mentions 'save' too many times: {ack!r}"
        )


# ===========================================================================
# 7. Regression: Tense is preserved through the pipeline
# ===========================================================================

class TestTensePreservation:
    """Present-tense college enrollment (padikuren) should be stored with
    education_status='current', and retrieval should reflect that."""

    def test_present_tense_stored_as_current(self):
        """'naa KLNCE il padikuren' → education_status='current'."""
        import memory_db
        from fact_extractor import extract_facts
        
        facts = extract_facts("naa KLNCE il padikuren")
        assert facts[0].education_status == "current"
        
        status = memory_db.get_education_status("user_school")
        assert status == "current"

    def test_past_tense_stored_as_past(self):
        """'I studied at Anna University' → education_status='past'."""
        import memory_db
        from fact_extractor import extract_facts
        
        facts = extract_facts("I studied at Anna University")
        assert facts[0].education_status == "past"
        
        status = memory_db.get_education_status("user_school")
        assert status == "past"

    def test_response_reflects_tense(self):
        """Current enrollment should say 'currently studying', past should not."""
        import memory_db
        from chat_memory import answer_question
        
        # Current
        memory_db.save_memory(
            "user_school", "KLNCE",
            category="education", source="regex", education_status="current"
        )
        current_answer = answer_question("What is my college?")
        assert "ippo" in current_answer or "currently" in current_answer, (
            f"Current enrollment response should say 'currently'. Got: {current_answer!r}"
        )
        
        # Past
        memory_db.forget_memory("user_school")
        memory_db.save_memory(
            "user_school", "Anna University",
            category="education", source="regex", education_status="past"
        )
        past_answer = answer_question("What is my college?")
        assert "college/school is" in past_answer, (
            f"Past enrollment should not say 'currently'. Got: {past_answer!r}"
        )


# ===========================================================================
# 8. End-to-end scenario reproduction
# ===========================================================================

class TestEndToEndScenario:
    """Reproduce the exact observed conversation."""

    def test_full_conversation_scenario(self):
        """
        User: "naa KLNCE il padikuren" → statement, save KLNCE with status=current
        User: "naa enga padikuren" → question, retrieve KLNCE
        User: "naa entha college la padikuren" → question, retrieve KLNCE
        User: "Which degree have I completed?" → question, say not saved
        User: "naa enna kalloori il padikuren" → question, retrieve KLNCE
        """
        from fact_extractor import extract_facts
        from chat_memory import answer_question, acknowledge_statement
        
        # 1. Save KLNCE
        facts = extract_facts("naa KLNCE il padikuren")
        assert len(facts) == 1
        assert facts[0].value == "KLNCE"
        
        ack = acknowledge_statement("naa KLNCE il padikuren")
        assert ack is not None
        assert "KLNCE" in ack or "save" in ack.lower()
        
        # 2. Question variations should all retrieve KLNCE
        questions = [
            "naa enga padikuren",
            "naa entha college la padikuren",
            "naa enna kalloori il padikuren",
        ]
        
        for q in questions:
            answer = answer_question(q)
            assert answer is not None
            assert "KLNCE" in answer, (
                f"Question {q!r} should retrieve KLNCE, got {answer!r}"
            )
            assert "Antha thakaval" not in answer, (
                f"Question {q!r} should not say 'not saved', got {answer!r}"
            )
        
        # 3. Degree question (no degree saved) should say not saved
        degree_answer = answer_question("Which degree have I completed?")
        assert degree_answer is not None
        assert "saved" in degree_answer.lower(), (
            f"Degree not saved, should mention 'saved'. Got {degree_answer!r}"
        )
