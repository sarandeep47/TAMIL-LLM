"""
tests/test_hallucination_guard.py
==================================
Regression tests for personal-fact hallucination prevention.

Reproduced bugs fixed
---------------------
1. "naa KLNCE il padikuren" → detect_intent returned None → fell through to
   Ollama which hallucinated a reply using raw user text.
2. "naa enna college padikuren" → same: None intent, Ollama path.
3. "which college am i have done my college degree" → None intent,
   Ollama invented "Madura Kamarajar College" from stale chat history.
4. "I'm studying at KLNCE" → regex classified as user_learning, not user_school.
5. "what degree do i have" → not caught by personal-history guard.

Root causes
-----------
A. `padikuren` (present-tense "studying at") had no patterns in
   _INTENT_PATTERNS, _STATEMENT_PATTERNS, or _ASCII_REGEXES.
B. Degree/graduation questions had no intent patterns and weren't caught
   by the personal-history guard.
C. "_ASCII_REGEXES ordering: "i'm studying" matched user_learning before
   "i'm studying at" matched user_school_current.

Coverage
--------
1.  detect_intent() for padikuren questions (present-tense enrollment)
2.  detect_intent() for padichen questions (past-tense)
3.  detect_intent() for degree/graduation questions
4.  regex extracts KLNCE with education_status='current' for padikuren
5.  regex extracts KLNCE with education_status='past' for padichen
6.  "I'm studying at X" → user_school_current, not user_learning
7.  KLNCE saved and retrieved correctly
8.  No college → "not saved" response, no Ollama call
9.  Asking about degree when only enrollment is stored → stored fact, no hallucination
10. Assistant-generated hallucinations not saved as facts
11. is_personal_history_question() guards unmatched personal questions
12. Tense distinction preserved in ack and retrieval
13. Tamil, Tanglish, English question variants
14. Existing name/goal/learning intents unaffected
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── DB isolation ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path, monkeypatch):
    mem_db  = tmp_path / "memory.db"
    chat_db = tmp_path / "chatbot.db"

    import memory_db, training_review, chatbot, chat_memory

    monkeypatch.setattr(memory_db,       "DB_PATH", mem_db)
    monkeypatch.setattr(training_review, "DB_PATH", chat_db)
    monkeypatch.setattr(chatbot,         "CHAT_DB_PATH", chat_db)

    import fact_extractor as fe
    monkeypatch.setattr(fe, "OLLAMA_URL", "http://localhost:99999/NOOP")

    monkeypatch.setattr(
        chat_memory, "get_memory",
        lambda key, language="english": memory_db.get_memory(key, language),
    )
    # Also patch get_education_status so it reads from the redirected DB
    monkeypatch.setattr(
        chat_memory, "get_education_status",
        lambda key="user_school": memory_db.get_education_status(key),
    )

    memory_db.initialize_database()
    training_review.initialize_training_db()
    chatbot.initialize_chatbot()
    yield


# ── helpers ───────────────────────────────────────────────────────────────────

def _save_via_regex(message: str):
    import requests as req_lib
    from fact_extractor import extract_facts
    with patch("fact_extractor.requests.post",
               side_effect=req_lib.exceptions.ConnectionError):
        return extract_facts(message)


# ===========================================================================
# 1. detect_intent covers padikuren (present-tense college questions)
# ===========================================================================

class TestPadikurenIntentDetection:
    @pytest.mark.parametrize("question", [
        "naa KLNCE il padikuren",
        "naa enna college padikuren",
        "naan enna college la padikuren",
        "naa enna college la padikuren",
        "naan endha college la padikuren",
        "naa endha college la padikuren",
        "naan enga college padikuren",
        "where am i studying",
        "which college am i",
        "what college am i",
    ])
    def test_padikuren_question_maps_to_user_school(self, question):
        from chat_memory import detect_intent
        result = detect_intent(question)
        assert result == "user_school", (
            f"detect_intent({question!r}) = {result!r}, expected 'user_school'"
        )

    def test_il_padikuren_short_form_detected(self):
        """'naa KLNCE il padikuren' — the exact reproduced bug message."""
        from chat_memory import detect_intent
        assert detect_intent("naa KLNCE il padikuren") == "user_school"


# ===========================================================================
# 2. detect_intent covers degree / graduation questions
# ===========================================================================

class TestDegreeQuestionIntentDetection:
    @pytest.mark.parametrize("question", [
        "which college am i have done my college degree",
        "which college degree",
        "my degree",
        "did i graduate",
        "where did i graduate",
        "my graduation",
        "my qualification",
    ])
    def test_degree_question_maps_to_user_school(self, question):
        from chat_memory import detect_intent
        result = detect_intent(question)
        assert result == "user_school", (
            f"detect_intent({question!r}) = {result!r}, expected 'user_school'"
        )


# ===========================================================================
# 3. Regex extracts KLNCE with correct tense
# ===========================================================================

class TestKLNCERegexExtraction:
    @pytest.mark.parametrize("statement,expected_edu", [
        ("naa KLNCE il padikuren",   "current"),
        ("naa KLNCE la padikuren",   "current"),
        ("naan KLNCE la padikuren",  "current"),
        ("naa KLNCE il padichen",    "past"),
        ("naa KLNCE la padichen",    "past"),
        ("naan KLNCE la padichen",   "past"),
        ("I'm studying at KLNCE",    "current"),
        ("I study at KLNCE",         "current"),
        ("I studied at KLNCE",       "past"),
    ])
    def test_klnce_extracted_with_correct_tense(self, statement, expected_edu):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex(statement)
        assert facts, f"No facts extracted from {statement!r}"
        school_facts = [f for f in facts if f.key == "user_school"]
        assert school_facts, f"No user_school fact in {facts!r}"
        f = school_facts[0]
        assert "KLNCE" in f.value, f"KLNCE not in extracted value {f.value!r}"
        assert f.education_status == expected_edu, (
            f"education_status={f.education_status!r}, expected {expected_edu!r}"
        )

    def test_studying_at_is_school_not_learning(self):
        """'I'm studying at KLNCE' must produce user_school, not user_learning."""
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("I'm studying at KLNCE")
        keys = [f.key for f in facts]
        assert "user_school" in keys, f"Expected user_school, got {keys!r}"
        assert "user_learning" not in keys, (
            "'I'm studying at KLNCE' must not produce user_learning"
        )


# ===========================================================================
# 4. KLNCE saved and retrieved correctly
# ===========================================================================

class TestKLNCESaveAndRetrieve:
    def test_klnce_saved_from_padikuren_statement(self):
        import memory_db
        _save_via_regex("naa KLNCE il padikuren")
        value = memory_db.get_memory("user_school")
        assert value == "KLNCE", f"Expected 'KLNCE', got {value!r}"

    def test_klnce_education_status_current_saved(self):
        import memory_db
        _save_via_regex("naa KLNCE il padikuren")
        status = memory_db.get_education_status("user_school")
        assert status == "current", f"Expected 'current', got {status!r}"

    def test_klnce_saved_from_padichen_statement(self):
        import memory_db
        _save_via_regex("naa KLNCE la padichen")
        value = memory_db.get_memory("user_school")
        assert value == "KLNCE"
        status = memory_db.get_education_status("user_school")
        assert status == "past", f"Expected 'past', got {status!r}"

    def test_klnce_retrieved_for_padikuren_question(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual",
                              education_status="current")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("naa enna college padikuren")
        mock_post.assert_not_called()
        assert "KLNCE" in result

    def test_klnce_retrieved_for_il_padikuren(self):
        """The exact reproduced bug — must not reach Ollama."""
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("naa KLNCE il padikuren")
        mock_post.assert_not_called()
        assert "KLNCE" in result

    def test_klnce_retrieved_for_degree_question(self):
        """Degree question when school is stored must return stored fact."""
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama(
                "which college am i have done my college degree"
            )
        mock_post.assert_not_called()
        assert "KLNCE" in result

    def test_full_pipeline_padikuren_save_then_question(self):
        """Full pipeline: extract_facts saves KLNCE, then question retrieves it."""
        import chatbot
        _save_via_regex("naa KLNCE il padikuren")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En college enna?")
        mock_post.assert_not_called()
        assert "KLNCE" in result


# ===========================================================================
# 5. No college saved → not-saved response, Ollama never called
# ===========================================================================

class TestNoCollegeSaved:
    @pytest.mark.parametrize("question", [
        "En college enna?",
        "naa enna college padikuren",
        "naa KLNCE il padikuren",
        "which college am i have done my college degree",
        "What is my college?",
        "where am i studying",
    ])
    def test_no_college_never_calls_ollama(self, question):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama(question)
        mock_post.assert_not_called()
        assert result is not None

    def test_no_college_returns_not_saved_english(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my college?")
        mock_post.assert_not_called()
        assert "not" in result.lower() or "saved" in result.lower()

    def test_no_college_returns_not_saved_tanglish(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En college enna?")
        mock_post.assert_not_called()
        assert "save" in result.lower() or "aagalai" in result.lower()

    def test_degree_question_no_school_no_ollama(self):
        """Degree question with no school fact must not call Ollama."""
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama(
                "which college am i have done my college degree"
            )
        mock_post.assert_not_called()
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()


# ===========================================================================
# 6. Degree completion question when only enrollment is stored
# ===========================================================================

class TestDegreeQuestionsWithEnrollmentOnly:
    """When user_school has education_status='current', asking about degree
    completion must return the stored college, not hallucinate graduation."""

    def test_degree_question_returns_college_not_hallucination(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual",
                              education_status="current")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("did i graduate")
        mock_post.assert_not_called()
        # Must return KLNCE (what we know), not any other college
        assert "KLNCE" in result
        # Must NOT contain hallucinated college names
        hallucinated = ["Madura Kamarajar", "Kamarajar College", "Madurai College"]
        for h in hallucinated:
            assert h not in result, (
                f"Response contains hallucinated college name {h!r}: {result!r}"
            )

    def test_past_tense_response_for_past_enrollment(self):
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual",
                              education_status="past")
        result = answer_question("Where did I study?")
        assert "KLNCE" in result

    def test_present_tense_response_for_current_enrollment(self):
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual",
                              education_status="current")
        result = answer_question("where am i studying")
        assert result is not None
        assert "KLNCE" in result
        # Should use present-tense phrasing
        assert any(w in result.lower() for w in ("current", "ippo", "studying", "படிக்கிறீர்கள்")), (
            f"Expected present-tense phrasing, got: {result!r}"
        )


# ===========================================================================
# 7. Assistant hallucinations must not be saved as facts
# ===========================================================================

class TestAssistantHallucinationsNotSaved:
    """
    The main loop only runs extract_facts() on user_message, not on the
    assistant's response. So assistant-generated text must never become a
    fact in the DB.
    """

    def test_hallucinated_college_not_in_db(self):
        import memory_db
        from fact_extractor import _looks_like_personal_statement
        # Simulate assistant response that was hallucinated
        hallucinated = "Naa college degree amma done Madura Kamarajar College!"
        # The assistant response should NOT be passed to extract_facts
        # This test ensures the heuristic would block it even if it were
        # (it's a statement-form sentence, so heuristic might fire — but it
        # should NOT match school patterns since extract_facts is never called
        # on assistant responses in the main loop)
        # Direct check: even if extract_facts ran on it, no user_school fact
        # should be saved because KLNCE (or any real value) is not in it
        from fact_extractor import extract_facts
        import requests as req_lib
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            facts = extract_facts(hallucinated)
        school_facts = [f for f in facts if f.key == "user_school"]
        # If any school fact was extracted from the hallucination, it must not
        # contain "Madura Kamarajar" as a trusted value
        for f in school_facts:
            assert "Madura Kamarajar" not in f.value, (
                f"Hallucinated college name was extracted as a fact: {f!r}"
            )

    def test_user_fact_not_overwritten_by_assistant_text(self):
        """After KLNCE is saved, passing Ollama's hallucinated text through
        extract_facts (simulating a bug) must not overwrite KLNCE."""
        import memory_db
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual",
                              confidence=1.0)
        # Even if extract_facts is accidentally called on assistant text
        from fact_extractor import extract_facts
        import requests as req_lib
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            extract_facts("Naa college degree amma done Madura Kamarajar College!")
        # KLNCE must still be there (manual source = never overwritten)
        assert memory_db.get_memory("user_school") == "KLNCE"


# ===========================================================================
# 8. Personal-history safety guard
# ===========================================================================

class TestPersonalHistorySafetyGuard:
    @pytest.mark.parametrize("question", [
        "what degree do i have",
        "do i have a degree",
        "what is my qualification",
        "what is my major",
        "where did i do my graduation",
    ])
    def test_guard_catches_unmatched_education_questions(self, question):
        from chat_memory import is_personal_history_question
        assert is_personal_history_question(question) is True, (
            f"Guard missed: {question!r}"
        )

    @pytest.mark.parametrize("question", [
        "Tell me about quantum physics",
        "What is the capital of France?",
        "Explain recursion",
    ])
    def test_guard_does_not_block_general_questions(self, question):
        from chat_memory import is_personal_history_question
        assert is_personal_history_question(question) is False, (
            f"Guard incorrectly blocked: {question!r}"
        )

    def test_guarded_question_returns_not_saved_no_ollama(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("what degree do i have")
        mock_post.assert_not_called()
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()

    def test_guarded_question_with_school_returns_school_fact(self):
        """Guard triggers answer_question which returns the stored fact."""
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual")
        # "what degree do i have" matches intent "user_school" directly
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("what degree do i have")
        mock_post.assert_not_called()
        assert "KLNCE" in result


# ===========================================================================
# 9. Tamil questions about school / college
# ===========================================================================

class TestTamilSchoolQuestions:
    def test_tamil_college_question_intent(self):
        from chat_memory import detect_intent
        assert detect_intent("என் கல்லூரி என்ன") == "user_school"

    def test_tamil_college_question_no_ollama_no_fact(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("என் கல்லூரி என்ன")
        mock_post.assert_not_called()
        assert result is not None
        assert "சேமிக்கப்படவில்லை" in result

    def test_tamil_college_question_with_fact(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("என் கல்லூரி என்ன")
        mock_post.assert_not_called()
        assert "KLNCE" in result
        assert any("\u0B80" <= ch <= "\u0BFF" for ch in result), (
            "Tamil question must get Tamil-script response"
        )


# ===========================================================================
# 10. Tense distinction preserved
# ===========================================================================

class TestTenseDistinction:
    def test_padikuren_statement_saves_current_status(self):
        import memory_db
        _save_via_regex("naa KLNCE il padikuren")
        assert memory_db.get_education_status("user_school") == "current"

    def test_padichen_statement_saves_past_status(self):
        import memory_db
        _save_via_regex("naa KLNCE la padichen")
        assert memory_db.get_education_status("user_school") == "past"

    def test_padikuren_ack_is_present_tense(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="regex",
                              education_status="current")
        reply = acknowledge_statement("naa KLNCE il padikuren")
        assert reply is not None
        assert "KLNCE" in reply
        # Must use present-tense phrasing, not past
        present_markers = ["ippo", "padikureengga", "currently", "studying"]
        assert any(m in reply.lower() for m in present_markers), (
            f"Expected present-tense ack, got: {reply!r}"
        )

    def test_padichen_ack_is_past_tense(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="regex",
                              education_status="past")
        reply = acknowledge_statement("naa KLNCE la padichen")
        assert reply is not None
        assert "KLNCE" in reply
        past_markers = ["padicheenga", "studied", "படித்தீர்கள்"]
        assert any(m in reply.lower() for m in past_markers), (
            f"Expected past-tense ack, got: {reply!r}"
        )

    def test_padikuren_does_not_imply_graduation(self):
        """Current enrollment must NOT generate any graduated/degree response."""
        import memory_db, chatbot
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual",
                              education_status="current")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("naa enna college padikuren")
        mock_post.assert_not_called()
        assert "KLNCE" in result
        # Must not claim graduation
        forbidden = ["graduated", "completed", "degree", "finished", "done"]
        for f in forbidden:
            assert f not in result.lower(), (
                f"Response contains {f!r} which implies graduation from "
                f"current-enrollment fact: {result!r}"
            )


# ===========================================================================
# 11. Existing intents unaffected
# ===========================================================================

class TestExistingIntentsUnaffected:
    def test_name_question_still_works(self):
        import memory_db, chatbot
        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my name?")
        mock_post.assert_not_called()
        assert "Sarandeep" in result

    def test_goal_question_still_works(self):
        import memory_db, chatbot
        memory_db.save_memory("user_goal", "AI Engineer",
                              category="goal", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En goal enna?")
        mock_post.assert_not_called()
        assert "AI Engineer" in result

    def test_learning_question_still_works(self):
        import memory_db, chatbot
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What am I learning?")
        mock_post.assert_not_called()
        assert "Python" in result

    def test_learning_not_confused_with_school(self):
        """user_learning and user_school are stored independently."""
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="manual")
        # School question with only learning fact → not saved
        school_result = answer_question("En college enna?")
        assert "Python" not in school_result, (
            "School question must not return the learning fact"
        )

    def test_school_not_confused_with_learning(self):
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_school", "KLNCE",
                              category="education", source="manual")
        # Learning question with only school fact → not saved
        learning_result = answer_question("What am I learning?")
        assert "KLNCE" not in learning_result, (
            "Learning question must not return the school fact"
        )

    def test_general_question_still_reaches_ollama(self):
        import chatbot
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "42 is the answer."}}
        mock_resp.raise_for_status.return_value = None
        with patch("chatbot.requests.post", return_value=mock_resp) as mock_post:
            result = chatbot.ask_ollama("What is the meaning of life?")
        mock_post.assert_called_once()
        assert "42" in result
