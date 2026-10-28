"""
tests/test_response_quality.py
================================
Regression tests for chatbot response-quality improvements.

Coverage
--------
1.  Language consistency for questions: direct personal-memory questions get 
    answers in the SAME language (deterministic lookup, no Ollama).
2.  Correct fact retrieval for direct questions (deterministic path verified).
3.  Missing-fact polite replies in all three dialects.
4.  Single merged system message: _build_system_message() produces ONE string
    that contains both the base prompt and the memory block.
5.  Statements now call Ollama for natural conversational responses, with
    memory context injected into the system prompt for context awareness.
6.  Direct questions use answer_question() for deterministic DB recall.

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
# Direct question retrieval (deterministic, no Ollama)
# ===========================================================================


class TestNoOllamaForStatements:
    """
    Direct personal-memory questions must be handled deterministically without
    Ollama (using answer_question()). But statements now go to Ollama for natural
    conversational responses, with memory context injected into the prompt.
    
    The key difference:
    - "What is my name?" → deterministic DB lookup, no Ollama
    - "My name is Sarandeep" → Ollama generates natural response (which may be 
      a friendly greeting or acknowledgment in the proper language)
    """

    def test_english_name_statement_calls_ollama(self):
        """Statements now go to Ollama for natural conversation."""
        import memory_db, chatbot
        from fact_extractor import extract_facts
        with patch("fact_extractor.requests.post",
                   side_effect=__import__("requests").exceptions.ConnectionError):
            # regex handles this without Ollama in fact_extractor
            extract_facts("My name is Sarandeep")

        # Now ask_ollama — should call Ollama for natural response
        with patch("chatbot.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "Great! I'm Sarandeep now in my records."}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            result = chatbot.ask_ollama("My name is Sarandeep")

        # Should call Ollama for natural response
        mock_post.assert_called_once()
        assert result is not None
        assert "Sarandeep" in result or "Great" in result

    def test_tanglish_learning_statement_calls_ollama(self):
        """Tanglish statements also go to Ollama for natural responses."""
        import memory_db, chatbot
        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="regex")

        with patch("chatbot.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "Semma! Python nalla language."}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            result = chatbot.ask_ollama("Naan Python kathukittu irukken")

        mock_post.assert_called_once()
        assert "Python" in result or "Semma" in result

    def test_tamil_goal_statement_calls_ollama(self):
        """Tamil statements also go to Ollama for natural responses."""
        import memory_db, chatbot
        memory_db.save_memory("user_goal", "AI Engineer",
                              category="goal", source="regex")

        with patch("chatbot.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "மிக அருமை! AI Engineer ஆக வேண்டும்."}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp

            result = chatbot.ask_ollama(
                "என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்"
            )

        mock_post.assert_called_once()
        assert result is not None


# ===========================================================================
# 3. Deterministic question retrieval (direct memory questions)
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
    Simulate the main() loop sequence with the new natural conversation flow:
    extract_facts() saves the fact, then ask_ollama() is called on the SAME
    message — Ollama now generates a natural response with memory context.
    
    The memory context is injected into the system prompt so Ollama is aware
    of the user's profile, enabling natural follow-up conversation.
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
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "Nice to meet you Sarandeep!"}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp
            
            reply = chatbot.ask_ollama("My name is Sarandeep")
        
        # Should call Ollama for natural response
        mock_post.assert_called_once()
        assert "Sarandeep" in reply or "Nice" in reply
        # Response should be in English (matching input language)
        assert not any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_tanglish_learning_full_pipeline(self):
        import chatbot
        self._save_via_regex("Naan Python kathukittu irukken")
        
        with patch("chatbot.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "Semma! Python nalla language, enna domain?"}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp
            
            reply = chatbot.ask_ollama("Naan Python kathukittu irukken")
        
        # Should call Ollama for natural response
        mock_post.assert_called_once()
        assert "Python" in reply or "Semma" in reply

    def test_tamil_name_full_pipeline(self):
        import chatbot
        self._save_via_regex("என் பெயர் சரண்தீப்")
        
        with patch("chatbot.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "சரண்தீப்! அழகான பெயர்."}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp
            
            reply = chatbot.ask_ollama("என் பெயர் சரண்தீப்")
        
        # Should call Ollama for natural response
        mock_post.assert_called_once()
        # Tamil response should contain Tamil script
        assert any("\u0B80" <= ch <= "\u0BFF" for ch in reply)

    def test_tanglish_goal_full_pipeline(self):
        import chatbot
        self._save_via_regex("En goal AI Engineer aaganum")
        
        with patch("chatbot.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "Semma! AI Engineer aaganum appadina enna domain?"}
            }
            mock_resp.raise_for_status.return_value = None
            mock_post.return_value = mock_resp
            
            reply = chatbot.ask_ollama("En goal AI Engineer aaganum")
        
        # Should call Ollama for natural response
        mock_post.assert_called_once()
        assert "AI Engineer" in reply
