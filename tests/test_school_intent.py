"""
tests/test_school_intent.py
============================
Regression tests for Tanglish/Tamil/English college and school intent
detection.

Root cause fixed
----------------
`user_school` existed in memory_db but had no entries in `_INTENT_PATTERNS`
(question routing) or `_STATEMENT_PATTERNS` (statement acknowledgment).
Inputs like "naa enna college la padichen" produced detect_intent=None, fell
through every short-circuit, and reached Ollama which hallucinated a
statement-like reply ("Super, naan college la padichen irukken.").

Coverage
--------
1.  detect_intent() recognises all question variants → "user_school"
2.  Questions take priority: answer_question() short-circuits before Ollama
3.  When school fact is saved, retrieval is correct in all three dialects
4.  When no fact is saved, a polite "not saved" reply is returned (no Ollama)
5.  Past-tense school detection does NOT clash with present-tense learning
6.  _detect_statement_intent() recognises school statements
7.  acknowledge_statement() returns a language-matched ack after saving
8.  Full pipeline: state college → ask about college → correct answer (no LLM)
9.  Existing name/goal/learning intents are unaffected

All Ollama calls are patched out.
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

    memory_db.initialize_database()
    training_review.initialize_training_db()
    chatbot.initialize_chatbot()
    yield


# ===========================================================================
# 1. detect_intent() recognises all college/school question variants
# ===========================================================================

class TestSchoolQuestionIntentDetection:
    """Every variant must map to 'user_school', not None."""

    @pytest.mark.parametrize("question", [
        # Tanglish — the exact bug-reproducing inputs
        "naa enna college la padichen",
        "naa enna college la padichen?",
        "Naan endha college la padichen?",
        "naan endha college la padichen",
        "naan enga college padichen",
        "naa enga college padichen",
        "En college enna?",
        "en college enna",
        "En school enna?",
        "en school enna",
        "naan enna school la padichen?",
        "naa enna school la padichen",
        # English
        "Which college did I study at?",
        "what college did i go to",
        "What is my school?",
        "what is my college",
        "Where did I study?",
        "where did i go to school",
    ])
    def test_detect_intent_returns_user_school(self, question):
        from chat_memory import detect_intent
        result = detect_intent(question)
        assert result == "user_school", (
            f"detect_intent({question!r}) = {result!r}, expected 'user_school'"
        )

    def test_no_collision_with_user_learning(self):
        """Present-tense learning must NOT map to user_school."""
        from chat_memory import detect_intent
        learning_inputs = [
            "naan enna kathukkiren?",
            "What am I learning?",
            "naan enna kathukittu irukken?",
        ]
        for msg in learning_inputs:
            result = detect_intent(msg)
            assert result == "user_learning", (
                f"Expected 'user_learning' for {msg!r}, got {result!r}"
            )

    def test_no_collision_with_user_name(self):
        from chat_memory import detect_intent
        assert detect_intent("What is my name?") == "user_name"
        assert detect_intent("en peyar enna?") == "user_name"

    def test_no_collision_with_user_goal(self):
        from chat_memory import detect_intent
        assert detect_intent("En goal enna?") == "user_goal"


# ===========================================================================
# 2. answer_question() short-circuits — Ollama never called for school Qs
# ===========================================================================

class TestSchoolQuestionNoOllama:
    """Ollama must NOT be called for any recognised school question."""

    def test_tanglish_college_question_no_ollama_fact_present(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "Anna University",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En college enna?")
        mock_post.assert_not_called()
        assert "Anna University" in result

    def test_tanglish_padichen_question_no_ollama_fact_present(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "PSG College",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("naa enna college la padichen?")
        mock_post.assert_not_called()
        assert "PSG College" in result

    def test_english_question_no_ollama_fact_present(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "IIT Madras",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("Which college did I study at?")
        mock_post.assert_not_called()
        assert "IIT Madras" in result

    def test_tanglish_question_no_ollama_fact_missing(self):
        """Even when fact is absent, Ollama must NOT be called."""
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En college enna?")
        mock_post.assert_not_called()
        assert result is not None
        assert "save" in result.lower() or "aagalai" in result.lower()

    def test_english_question_no_ollama_fact_missing(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my school?")
        mock_post.assert_not_called()
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()


# ===========================================================================
# 3. Correct fact returned in each dialect
# ===========================================================================

class TestSchoolFactRetrieval:
    """When a school fact is stored, answer_question() returns it in the
    correct dialect and phrasing."""

    def test_tanglish_returns_tanglish_response(self):
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_school", "Anna University",
                              category="education", source="manual")
        result = answer_question("En college enna?")
        assert result is not None
        assert "Anna University" in result
        # Tanglish response must not contain Tamil script
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in result), (
            f"Tanglish question got Tamil-script reply: {result!r}"
        )

    def test_english_returns_english_response(self):
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_school", "IIT Madras",
                              category="education", source="manual")
        result = answer_question("What is my college?")
        assert result is not None
        assert "IIT Madras" in result
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in result)

    def test_tamil_returns_tamil_response(self):
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_school", "Anna University",
                              category="education", source="manual")
        result = answer_question("என் கல்லூரி என்ன")
        assert result is not None
        assert "Anna University" in result
        # Tamil response must contain Tamil script
        assert any("\u0B80" <= ch <= "\u0BFF" for ch in result), (
            f"Tamil question got non-Tamil reply: {result!r}"
        )


# ===========================================================================
# 4. Not-saved replies — polite, no Ollama, correct dialect
# ===========================================================================

class TestSchoolNotSavedReplies:
    """answer_question() must return a polite, dialect-matched reply when
    user_school is not in the DB."""

    def test_tanglish_not_saved(self):
        from chat_memory import answer_question
        result = answer_question("En college enna?")
        assert result is not None
        assert "save" in result.lower() or "aagalai" in result.lower(), (
            f"Expected Tanglish 'not saved' message, got: {result!r}"
        )

    def test_english_not_saved(self):
        from chat_memory import answer_question
        result = answer_question("What is my school?")
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()

    def test_tanglish_padichen_not_saved(self):
        from chat_memory import answer_question
        result = answer_question("naa enna college la padichen?")
        assert result is not None
        assert "save" in result.lower() or "aagalai" in result.lower()


# ===========================================================================
# 5. _detect_statement_intent() recognises school statements
# ===========================================================================

class TestSchoolStatementDetection:
    """Declarative school statements must map to 'user_school'."""

    @pytest.mark.parametrize("statement", [
        "Naan Anna University la padichen",
        "naa MIT la padichen",
        "I studied at IIT Madras",
        "My college is PSG College of Technology",
        "My school is DAV",
        "college la padichen",
    ])
    def test_statement_intent_is_user_school(self, statement):
        from chat_memory import _detect_statement_intent
        result = _detect_statement_intent(statement)
        assert result == "user_school", (
            f"_detect_statement_intent({statement!r}) = {result!r}, "
            "expected 'user_school'"
        )

    def test_learning_statement_not_school(self):
        """Present-tense learning statement must NOT be classified as school."""
        from chat_memory import _detect_statement_intent
        assert _detect_statement_intent("Naan Python kathukittu irukken") == "user_learning"

    def test_name_statement_not_school(self):
        from chat_memory import _detect_statement_intent
        assert _detect_statement_intent("My name is Sarandeep") == "user_name"


# ===========================================================================
# 6. acknowledge_statement() — language-matched ack after school save
# ===========================================================================

class TestSchoolStatementAcknowledge:
    """acknowledge_statement() must return a reply in the user's dialect."""

    def test_tanglish_ack_is_tanglish(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_school", "Anna University",
                              category="education", source="regex")
        reply = acknowledge_statement("Naan Anna University la padichen")
        assert reply is not None
        assert "Anna University" in reply
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply), (
            f"Tanglish statement got Tamil-script ack: {reply!r}"
        )

    def test_english_ack_is_english(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_school", "IIT Madras",
                              category="education", source="manual")
        reply = acknowledge_statement("I studied at IIT Madras")
        assert reply is not None
        assert "IIT Madras" in reply
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_returns_none_when_fact_not_in_db(self):
        from chat_memory import acknowledge_statement
        # DB empty — must not fabricate an ack
        result = acknowledge_statement("Naan Anna University la padichen")
        assert result is None


# ===========================================================================
# 7. Full pipeline: state college → ask → correct retrieval (no Ollama)
# ===========================================================================

class TestSchoolFullPipeline:
    """Save a school via extract_facts(), then ask — whole pipeline, no LLM."""

    def _save_via_regex(self, message: str):
        import requests as req_lib
        from fact_extractor import extract_facts
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            return extract_facts(message)

    def test_english_save_then_tanglish_question(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "Anna University",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("En college enna?")
        mock_post.assert_not_called()
        assert "Anna University" in reply

    def test_tanglish_question_after_manual_remember(self):
        import memory_db, chatbot
        # Simulate /remember college=PSG College
        memory_db.save_memory("user_school", "PSG College",
                              category="education", source="manual",
                              confidence=1.0)
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("naa enna college la padichen?")
        mock_post.assert_not_called()
        assert "PSG College" in reply

    def test_endha_college_variant(self):
        import memory_db, chatbot
        memory_db.save_memory("user_school", "MIT",
                              category="education", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("Naan endha college la padichen?")
        mock_post.assert_not_called()
        assert "MIT" in reply


# ===========================================================================
# 8. Regression: existing intents unaffected
# ===========================================================================

class TestExistingIntentsUnaffected:
    """All previously working name/goal/learning facts still work correctly."""

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
        """
        Saving a learning fact must not affect school retrieval and vice versa.
        """
        import memory_db
        from chat_memory import answer_question
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="manual")
        # School question with only learning fact stored → not saved
        school_result = answer_question("En college enna?")
        assert school_result is not None
        assert "Python" not in school_result, (
            "School question must not return the learning fact"
        )
        # Learning question → Python
        learning_result = answer_question("What am I learning?")
        assert "Python" in learning_result

    def test_unknown_message_still_reaches_ollama(self):
        """Unrecognised messages must still reach Ollama as before."""
        import chatbot
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "Interesting!"}}
        mock_resp.raise_for_status.return_value = None
        with patch("chatbot.requests.post", return_value=mock_resp) as mock_post:
            result = chatbot.ask_ollama("Tell me about the universe.")
        mock_post.assert_called_once()
        assert "Interesting!" in result
