"""
tests/test_response_quality.py
================================
Regression tests for chatbot response-quality improvements.

Coverage
--------
1.  Language consistency: statements in Tamil/Tanglish/English get ack in
    the SAME language (deterministic short-circuit, no Ollama needed).
2.  Irrelevant-response-after-save prevention: statements are acknowledged
    by acknowledge_statement() before reaching Ollama.
3.  Correct fact retrieval for questions (deterministic path verified).
4.  Missing-fact polite replies in all three dialects.
5.  acknowledge_statement() returns None when fact not in DB (not yet saved).
6.  Single merged system message: _build_system_message() produces ONE string
    that contains both the base prompt and the memory block.
7.  Ollama is NEVER called when a statement or question can be handled locally.

All Ollama HTTP calls are patched out so tests run without a running instance.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── Project root on sys.path ──────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── DB isolation ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path, monkeypatch):
    """Redirect all DB paths to fresh temp files for each test."""
    mem_db  = tmp_path / "memory.db"
    chat_db = tmp_path / "chatbot.db"

    import memory_db
    import training_review
    import chatbot
    import chat_memory

    monkeypatch.setattr(memory_db,       "DB_PATH", mem_db)
    monkeypatch.setattr(training_review, "DB_PATH", chat_db)
    monkeypatch.setattr(chatbot,         "CHAT_DB_PATH", chat_db)

    # Redirect fact_extractor's Ollama URL to something unreachable so it
    # never accidentally fires a real network call.
    import fact_extractor as fe
    monkeypatch.setattr(fe, "OLLAMA_URL", "http://localhost:99999/NOOP")

    # Patch chat_memory.get_memory to always use the redirected DB_PATH
    monkeypatch.setattr(
        chat_memory, "get_memory",
        lambda key, language="english": memory_db.get_memory(key, language),
    )

    memory_db.initialize_database()
    training_review.initialize_training_db()
    chatbot.initialize_chatbot()

    yield


# ===========================================================================
# 1. Language consistency — acknowledge_statement()
# ===========================================================================

class TestAcknowledgeStatementLanguageConsistency:
    """
    After a fact is saved by extract_facts(), acknowledge_statement() must
    return a reply in the SAME language the user used — no Ollama required.
    """

    def test_english_name_ack_is_english(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="regex")
        reply = acknowledge_statement("My name is Sarandeep")
        assert reply is not None, "Must return an acknowledgment"
        # Must contain the value
        assert "Sarandeep" in reply
        # Must be English — no Tamil script
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply), (
            f"English input got Tamil output: {reply!r}"
        )

    def test_tanglish_learning_ack_is_tanglish(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="regex")
        reply = acknowledge_statement("Naan Python kathukittu irukken")
        assert reply is not None
        assert "Python" in reply
        # Tanglish ack must NOT be Tamil script
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply), (
            f"Tanglish input got Tamil-script output: {reply!r}"
        )
        # Must contain a Tanglish word
        assert any(w in reply.lower() for w in ("seri", "save", "panniten",
                                                  "kathukureengga", "neenga")), (
            f"Expected Tanglish ack, got: {reply!r}"
        )

    def test_tamil_name_ack_is_tamil(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="regex")
        reply = acknowledge_statement("என் பெயர் சரண்தீப்")
        assert reply is not None
        # Tamil ack must contain Tamil script
        assert any("\u0B80" <= ch <= "\u0BFF" for ch in reply), (
            f"Tamil input got non-Tamil output: {reply!r}"
        )

    def test_tamil_learning_ack_is_tamil(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="regex")
        reply = acknowledge_statement(
            "நான் Python கற்றுக்கொண்டு இருக்கிறேன்"
        )
        assert reply is not None
        assert "Python" in reply
        assert any("\u0B80" <= ch <= "\u0BFF" for ch in reply), (
            f"Tamil input got non-Tamil output: {reply!r}"
        )

    def test_tanglish_goal_ack_is_tanglish(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_goal", "AI Engineer",
                              category="goal", source="regex")
        reply = acknowledge_statement("En goal AI Engineer aaganum")
        assert reply is not None
        assert "AI Engineer" in reply
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_english_workplace_ack_is_english(self):
        import memory_db
        from chat_memory import acknowledge_statement
        memory_db.save_memory("user_workplace", "Tarcin Robotics",
                              category="work", source="regex")
        reply = acknowledge_statement("I work at Tarcin Robotics")
        assert reply is not None
        assert "Tarcin Robotics" in reply
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply)


# ===========================================================================
# 2. No Ollama call when statement can be handled locally
# ===========================================================================

class TestNoOllamaForStatements:
    """
    Statements whose facts are in the DB must be handled by
    acknowledge_statement() — Ollama must NOT be called.
    """

    def test_english_name_statement_no_ollama(self):
        import memory_db, chatbot
        from fact_extractor import extract_facts
        with patch("fact_extractor.requests.post",
                   side_effect=__import__("requests").exceptions.ConnectionError):
            # regex handles this without Ollama in fact_extractor
            extract_facts("My name is Sarandeep")

        # Now ask_ollama — must not call Ollama
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("My name is Sarandeep")

        mock_post.assert_not_called()
        assert result is not None
        assert "Sarandeep" in result

    def test_tanglish_learning_statement_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="regex")

        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("Naan Python kathukittu irukken")

        mock_post.assert_not_called()
        assert "Python" in result

    def test_tamil_goal_statement_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_goal", "AI Engineer",
                              category="goal", source="regex")

        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama(
                "என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்"
            )

        mock_post.assert_not_called()
        assert "AI Engineer" in result


# ===========================================================================
# 3. Statement ack returns None when fact NOT yet in DB
# ===========================================================================

class TestAcknowledgeStatementRequiresDbFact:
    """
    acknowledge_statement() must return None when the fact isn't in the DB yet.
    This ensures new statements reach the normal extraction → ack pipeline
    and don't silently return a wrong reply.
    """

    def test_returns_none_when_fact_absent(self):
        from chat_memory import acknowledge_statement
        # DB is empty — fact not saved yet
        result = acknowledge_statement("My name is Sarandeep")
        assert result is None, (
            "acknowledge_statement must return None when fact not in DB"
        )

    def test_returns_none_for_tanglish_before_save(self):
        from chat_memory import acknowledge_statement
        result = acknowledge_statement("Naan Python kathukittu irukken")
        assert result is None

    def test_returns_none_for_random_message(self):
        from chat_memory import acknowledge_statement
        result = acknowledge_statement("Tell me a joke.")
        assert result is None


# ===========================================================================
# 4. Deterministic question retrieval (no Ollama)
# ===========================================================================

class TestDeterministicQuestionRetrieval:
    """
    Questions matching _INTENT_PATTERNS must be handled by answer_question()
    without ever calling Ollama, even when facts are present.
    """

    def test_english_name_question_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my name?")
        mock_post.assert_not_called()
        assert "Sarandeep" in result

    def test_tanglish_goal_question_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_goal", "AI Engineer",
                              category="goal", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En goal enna?")
        mock_post.assert_not_called()
        assert "AI Engineer" in result

    def test_tamil_learning_question_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama(
                "நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?"
            )
        mock_post.assert_not_called()
        assert "Python" in result

    def test_tamil_name_question_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("என் பெயர் என்ன?")
        mock_post.assert_not_called()
        assert "Sarandeep" in result

    def test_tanglish_learning_question_no_ollama(self):
        import memory_db, chatbot
        memory_db.save_memory("user_learning", "JavaScript",
                              category="learning", source="manual")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("naan enna kathukkiren?")
        mock_post.assert_not_called()
        assert "JavaScript" in result


# ===========================================================================
# 5. Missing fact → polite "not saved" in correct dialect (no Ollama)
# ===========================================================================

class TestMissingFactReply:
    """DB is empty — questions must return a polite denial without Ollama."""

    def test_english_not_saved(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my name?")
        mock_post.assert_not_called()
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()

    def test_tanglish_not_saved(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("En goal enna?")
        mock_post.assert_not_called()
        assert result is not None
        # Tanglish "not saved" message
        assert "save" in result.lower() or "aagalai" in result.lower()

    def test_tamil_not_saved_contains_tamil(self):
        import chatbot
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama(
                "நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?"
            )
        mock_post.assert_not_called()
        assert result is not None
        # Tamil "not saved" message must contain Tamil script
        assert "சேமிக்கப்படவில்லை" in result


# ===========================================================================
# 6. Single merged system message
# ===========================================================================

class TestMergedSystemMessage:
    """_build_system_message() must return a single string, not a list."""

    def test_no_memory_returns_base_prompt(self):
        from chatbot import _build_system_message
        result = _build_system_message(None)
        assert isinstance(result, str)
        # Must contain the language rule
        assert "LANGUAGE RULE" in result or "Reply in" in result or "language" in result.lower()

    def test_with_memory_returns_single_string(self):
        from chatbot import _build_system_message
        ctx = "user name: Sarandeep\nuser learning: Python"
        result = _build_system_message(ctx)
        assert isinstance(result, str)
        # Memory is embedded, not a separate object
        assert "Sarandeep" in result
        assert "Python" in result
        # The base prompt language rule must still be present
        assert "LANGUAGE RULE" in result or "language" in result.lower()

    def test_ollama_receives_single_system_message(self):
        """Verify the messages list sent to Ollama has exactly ONE system entry."""
        import memory_db, chatbot
        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="manual")

        captured_messages = []

        def fake_post(url, json=None, timeout=None):
            captured_messages.extend(json.get("messages", []))
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"message": {"content": "Hello!"}}
            mock_resp.raise_for_status.return_value = None
            return mock_resp

        # Use a message that reaches Ollama (not a recognised intent)
        with patch("chatbot.requests.post", side_effect=fake_post):
            chatbot.ask_ollama("Tell me something interesting.")

        system_messages = [m for m in captured_messages if m["role"] == "system"]
        assert len(system_messages) == 1, (
            f"Expected exactly 1 system message, got {len(system_messages)}. "
            "Dual system messages cause inconsistent Ollama behaviour."
        )
        # Memory must be embedded inside that single system message
        assert "Sarandeep" in system_messages[0]["content"]


# ===========================================================================
# 7. Full pipeline: extract → acknowledge (no Ollama)
# ===========================================================================

class TestFullStatementPipeline:
    """
    Simulate the main() loop sequence:
    extract_facts() saves the fact, then ask_ollama() is called on the SAME
    message — the whole pipeline must produce an acknowledged response without
    hitting Ollama.
    """

    def _save_via_regex(self, message: str):
        """Use the real extract_facts() regex path (Ollama unreachable)."""
        import requests as req_lib
        from fact_extractor import extract_facts
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            return extract_facts(message)

    def test_english_name_full_pipeline(self):
        import chatbot
        self._save_via_regex("My name is Sarandeep")
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("My name is Sarandeep")
        mock_post.assert_not_called()
        assert "Sarandeep" in reply
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_tanglish_learning_full_pipeline(self):
        import chatbot
        self._save_via_regex("Naan Python kathukittu irukken")
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("Naan Python kathukittu irukken")
        mock_post.assert_not_called()
        assert "Python" in reply
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_tamil_name_full_pipeline(self):
        import chatbot
        self._save_via_regex("என் பெயர் சரண்தீப்")
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("என் பெயர் சரண்தீப்")
        mock_post.assert_not_called()
        assert reply is not None
        # Tamil ack must contain Tamil script
        assert any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_tanglish_goal_full_pipeline(self):
        import chatbot
        self._save_via_regex("En goal AI Engineer aaganum")
        with patch("chatbot.requests.post") as mock_post:
            reply = chatbot.ask_ollama("En goal AI Engineer aaganum")
        mock_post.assert_not_called()
        assert "AI Engineer" in reply
