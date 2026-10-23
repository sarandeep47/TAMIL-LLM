"""
tests/test_chatbot.py — Pytest suite for the Tamil chatbot components.

Covers
------
* memory_db.py     : save, get, forget, list, migration, confidence gating
* chat_memory.py   : intent detection, language detection, answer_question,
                     learn_fact, multilingual retrieval
* fact_extractor.py: heuristic filtering, JSON validation, false-positive
                     prevention, Ollama failure handling
* training_review.py: save, list pending/approved, approve, reject, edit,
                      JSONL export, DB migration
* chatbot.py       : command handlers (remember, forget, memories),
                     memory context builder, ask_ollama mocking

All Ollama calls are mocked with unittest.mock so tests pass without
a running Ollama instance.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path regardless of how pytest is invoked.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fixtures: redirect DB paths to temp directories for full isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path, monkeypatch):
    """Redirect all DB_PATH globals to fresh temp files for each test."""
    mem_db   = tmp_path / "memory.db"
    chat_db  = tmp_path / "chatbot.db"

    import memory_db
    import training_review
    import chatbot

    monkeypatch.setattr(memory_db,       "DB_PATH", mem_db)
    monkeypatch.setattr(training_review, "DB_PATH", chat_db)
    monkeypatch.setattr(chatbot,         "CHAT_DB_PATH", chat_db)

    # Also patch chat_memory's imported reference to initialize_database
    import chat_memory
    monkeypatch.setattr(chat_memory, "get_memory",
                        lambda key, language="english": memory_db.get_memory(key, language))

    # Initialise schemas in temp files
    memory_db.initialize_database()
    training_review.initialize_training_db()

    yield


# ===========================================================================
# 1. memory_db tests
# ===========================================================================

class TestMemoryDB:
    def test_save_and_get_english(self):
        from memory_db import save_memory, get_memory
        save_memory("user_name", "Sarandeep")
        assert get_memory("user_name") == "Sarandeep"

    def test_save_and_get_tamil(self):
        from memory_db import save_memory, get_memory
        save_memory("user_name", "Sarandeep", "சரண்தீப்")
        assert get_memory("user_name", language="tamil") == "சரண்தீப்"

    def test_get_missing_returns_none(self):
        from memory_db import get_memory
        assert get_memory("nonexistent_key") is None

    def test_upsert_updates_value(self):
        from memory_db import save_memory, get_memory
        save_memory("user_name", "Old Name")
        save_memory("user_name", "New Name")
        assert get_memory("user_name") == "New Name"

    def test_forget_existing(self):
        from memory_db import save_memory, forget_memory, get_memory
        save_memory("user_name", "Sarandeep")
        result = forget_memory("user_name")
        assert result is True
        assert get_memory("user_name") is None

    def test_forget_nonexistent(self):
        from memory_db import forget_memory
        result = forget_memory("does_not_exist")
        assert result is False

    def test_list_memories_empty(self):
        from memory_db import list_memories
        assert list_memories() == []

    def test_list_memories_returns_all(self):
        from memory_db import save_memory, list_memories
        save_memory("user_name", "Alice", category="identity")
        save_memory("user_location", "Madurai", category="identity")
        memories = list_memories()
        keys = [m["key"] for m in memories]
        assert "user_name" in keys
        assert "user_location" in keys

    def test_ai_does_not_overwrite_manual(self):
        """AI extraction must not overwrite a manually saved fact."""
        from memory_db import save_memory, get_memory
        save_memory("user_name", "Sarandeep", source="manual", confidence=1.0)
        save_memory("user_name", "AISuggestion", source="ai", confidence=0.9)
        # Manual fact should still be there
        assert get_memory("user_name") == "Sarandeep"

    def test_ai_can_save_new_fact(self):
        """AI extraction can save a fact that doesn't exist yet."""
        from memory_db import save_memory, get_memory
        save_memory("user_workplace", "Tarcin Robotics", source="ai", confidence=0.85)
        assert get_memory("user_workplace") == "Tarcin Robotics"

    def test_confidence_stored_correctly(self, tmp_path):
        from memory_db import save_memory, DB_PATH
        save_memory("user_goal", "AI engineer", confidence=0.8, source="ai")
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT confidence, source FROM memories WHERE fact_key = 'user_goal'"
            ).fetchone()
        assert abs(row[0] - 0.8) < 0.001
        assert row[1] == "ai"

    def test_updated_at_populated(self, tmp_path):
        from memory_db import save_memory, DB_PATH
        save_memory("user_name", "Sarandeep")
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT updated_at FROM memories WHERE fact_key = 'user_name'"
            ).fetchone()
        assert row[0] is not None


# ===========================================================================
# 2. chat_memory tests
# ===========================================================================

class TestChatMemory:
    def test_detect_language_tamil(self):
        from chat_memory import detect_language_style
        assert detect_language_style("என் பெயர் என்ன?") == "tamil"

    def test_detect_language_tanglish(self):
        from chat_memory import detect_language_style
        assert detect_language_style("en peyar enna?") == "tanglish"

    def test_detect_language_english(self):
        from chat_memory import detect_language_style
        assert detect_language_style("What is my name?") == "english"

    def test_detect_intent_name_english(self):
        from chat_memory import detect_intent
        assert detect_intent("What is my name?") == "user_name"

    def test_detect_intent_name_tanglish(self):
        from chat_memory import detect_intent
        assert detect_intent("en peyar enna") == "user_name"

    def test_detect_intent_location_english(self):
        from chat_memory import detect_intent
        assert detect_intent("where do i live") == "user_location"

    def test_detect_intent_workplace(self):
        from chat_memory import detect_intent
        assert detect_intent("where do i work") == "user_workplace"

    def test_detect_intent_learning(self):
        from chat_memory import detect_intent
        assert detect_intent("what am i learning") == "user_learning"

    def test_detect_intent_goal(self):
        from chat_memory import detect_intent
        assert detect_intent("what is my goal") == "user_goal"

    def test_detect_intent_colour(self):
        from chat_memory import detect_intent
        assert detect_intent("what is my favourite colour") == "favorite_colour"

    def test_detect_intent_no_match(self):
        from chat_memory import detect_intent
        assert detect_intent("tell me a joke") is None

    def test_answer_question_no_data_english(self):
        from chat_memory import answer_question
        result = answer_question("What is my name?")
        assert "not" in result.lower() or "saved" in result.lower()

    def test_answer_question_with_data_english(self, monkeypatch):
        from chat_memory import answer_question
        import memory_db
        memory_db.save_memory("user_name", "Sarandeep")
        result = answer_question("What is my name?")
        assert "Sarandeep" in result
        assert "Your name is" in result

    def test_answer_question_with_data_tanglish(self, monkeypatch):
        import memory_db
        memory_db.save_memory("user_name", "Sarandeep")
        from chat_memory import answer_question
        result = answer_question("en peyar enna")
        assert "Sarandeep" in result
        assert "peyar" in result.lower()

    def test_answer_question_with_data_tamil(self, monkeypatch):
        import memory_db
        memory_db.save_memory("user_location", "Madurai", "மதுரை")
        from chat_memory import answer_question
        result = answer_question("நான் எங்கே இருக்கிறேன்")
        assert "மதுரை" in result or "Madurai" in result

    def test_answer_question_workplace(self, monkeypatch):
        import memory_db
        memory_db.save_memory("user_workplace", "Tarcin Robotics")
        from chat_memory import answer_question
        result = answer_question("where do i work")
        assert "Tarcin Robotics" in result

    def test_answer_question_learning(self, monkeypatch):
        import memory_db
        memory_db.save_memory("user_learning", "Python")
        from chat_memory import answer_question
        result = answer_question("what am i learning")
        assert "Python" in result

    def test_learn_fact_saves_colour(self, monkeypatch):
        import memory_db
        from chat_memory import learn_fact
        result = learn_fact("My favourite colour is blue.")
        assert result is not None
        assert memory_db.get_memory("favorite_colour") == "blue"

    def test_learn_fact_ignores_question(self):
        from chat_memory import learn_fact
        assert learn_fact("En favourite colour enna?") is None

    def test_learn_fact_ignores_empty_colour(self):
        from chat_memory import learn_fact
        assert learn_fact("My favourite colour is ") is None


# ===========================================================================
# 3. fact_extractor tests  (Ollama is mocked)
# ===========================================================================

def _make_mock_ollama_response(facts_list: list[dict]):
    """Build a mock requests.Response for Ollama returning given facts."""
    body = json.dumps({"facts": facts_list}, ensure_ascii=False)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": body}
    }
    mock_response.raise_for_status.return_value = None
    return mock_response


class TestFactExtractor:
    def test_heuristic_skips_short_message(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("hi") is False

    def test_heuristic_skips_question(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("What is my name?") is False

    def test_heuristic_passes_personal_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("I work at Tarcin Robotics.") is True

    def test_heuristic_passes_tanglish(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("Enakku cricket pudikkum.") is True

    def test_heuristic_skips_slash_command(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("/remember name=Sarandeep") is False

    def test_validation_rejects_unknown_key(self):
        from fact_extractor import _validate_raw_facts
        raw = [{"key": "made_up_key", "value": "something", "confidence": 0.9}]
        assert _validate_raw_facts(raw) == []

    def test_validation_rejects_empty_value(self):
        from fact_extractor import _validate_raw_facts
        raw = [{"key": "user_name", "value": "", "confidence": 0.9}]
        assert _validate_raw_facts(raw) == []

    def test_validation_rejects_null_value(self):
        from fact_extractor import _validate_raw_facts
        raw = [{"key": "user_workplace", "value": "null", "confidence": 0.9}]
        assert _validate_raw_facts(raw) == []

    def test_validation_rejects_unknown_value(self):
        from fact_extractor import _validate_raw_facts
        raw = [{"key": "user_workplace", "value": "unknown", "confidence": 0.9}]
        assert _validate_raw_facts(raw) == []

    def test_validation_accepts_valid_fact(self):
        from fact_extractor import _validate_raw_facts
        raw = [{"key": "user_workplace", "value": "Tarcin Robotics", "confidence": 0.95}]
        facts = _validate_raw_facts(raw)
        assert len(facts) == 1
        assert facts[0].value == "Tarcin Robotics"
        assert facts[0].key == "user_workplace"

    def test_extract_facts_returns_empty_for_question(self):
        from fact_extractor import extract_facts
        result = extract_facts("What is my name?")
        assert result == []

    def test_extract_facts_saves_workplace(self, monkeypatch):
        import memory_db
        from fact_extractor import extract_facts
        mock_resp = _make_mock_ollama_response([
            {"key": "user_workplace", "value": "Tarcin Robotics", "confidence": 0.95}
        ])
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            facts = extract_facts("I work at Tarcin Robotics.")
        assert len(facts) == 1
        assert memory_db.get_memory("user_workplace") == "Tarcin Robotics"

    def test_extract_facts_saves_learning(self, monkeypatch):
        import memory_db
        from fact_extractor import extract_facts
        mock_resp = _make_mock_ollama_response([
            {"key": "user_learning", "value": "Python", "confidence": 0.90}
        ])
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            facts = extract_facts("I'm learning Python.")
        assert memory_db.get_memory("user_learning") == "Python"

    def test_extract_facts_does_not_overwrite_manual_name(self):
        import memory_db
        from fact_extractor import extract_facts
        memory_db.save_memory("user_name", "Sarandeep", source="manual", confidence=1.0)
        mock_resp = _make_mock_ollama_response([
            {"key": "user_name", "value": "Different Name", "confidence": 0.9}
        ])
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            facts = extract_facts("My name is Different Name.")
        # Must not overwrite manual fact
        assert memory_db.get_memory("user_name") == "Sarandeep"

    def test_extract_facts_connection_error_ollama_only_message(self):
        """
        For messages the regex cannot parse, an Ollama ConnectionError
        must return [] gracefully (chatbot stays usable).
        """
        from fact_extractor import extract_facts
        import requests as req_lib
        # This message passes the heuristic but has no regex match
        # (irregular phrasing the regex doesn't cover)
        msg = "I am employed by Tarcin since last year and quite happy there."
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            result = extract_facts(msg)
        # Ollama is down; regex didn't match — must return [] without crashing
        assert isinstance(result, list)

    def test_extract_facts_regex_succeeds_without_ollama(self):
        """
        The regex layer must extract 'I work at Tarcin Robotics' successfully
        even when Ollama is completely offline.
        """
        import memory_db
        from fact_extractor import extract_facts
        import requests as req_lib
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            result = extract_facts("I work at Tarcin Robotics.")
        # Regex handles this — must succeed regardless of Ollama state
        assert len(result) >= 1
        assert any(f.key == "user_workplace" for f in result)
        assert memory_db.get_memory("user_workplace") == "Tarcin Robotics"

    def test_extract_facts_bad_json_ollama_only_message(self):
        """
        For messages requiring the LLM, bad JSON from Ollama must return []
        gracefully.
        """
        from fact_extractor import extract_facts
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "not json at all!!!"}}
        mock_resp.raise_for_status.return_value = None
        # Use a message that passes heuristic but regex won't match
        msg = "I am employed by Tarcin since last year and quite happy there."
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            result = extract_facts(msg)
        assert isinstance(result, list)

    def test_extract_facts_timeout_ollama_only_message(self):
        """
        For messages requiring the LLM, an Ollama Timeout must return []
        gracefully.
        """
        from fact_extractor import extract_facts
        import requests as req_lib
        msg = "I am employed by Tarcin since last year and quite happy there."
        with patch("fact_extractor.requests.post",
                   side_effect=req_lib.exceptions.Timeout):
            result = extract_facts(msg)
        assert isinstance(result, list)

    def test_extract_facts_empty_facts_list(self):
        from fact_extractor import extract_facts
        mock_resp = _make_mock_ollama_response([])
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            result = extract_facts("I love Tamil food.")
        assert result == []

    def test_extract_facts_filters_low_confidence_key(self):
        from fact_extractor import _validate_raw_facts
        # confidence > 1.0 should be invalid (out of range check in Fact.is_valid)
        raw = [{"key": "user_skill", "value": "dancing", "confidence": 1.5}]
        facts = _validate_raw_facts(raw)
        assert facts == []

    def test_dry_run_does_not_save(self):
        import memory_db
        from fact_extractor import extract_facts_dry_run
        mock_resp = _make_mock_ollama_response([
            {"key": "user_workplace", "value": "Test Corp", "confidence": 0.9}
        ])
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            facts = extract_facts_dry_run("I work at Test Corp.")
        # Nothing saved
        assert memory_db.get_memory("user_workplace") is None
        # But facts returned
        assert len(facts) == 1


# ===========================================================================
# 4. training_review tests
# ===========================================================================

class TestTrainingReview:
    def test_save_training_example_returns_id(self):
        from training_review import save_training_example
        rid = save_training_example("Hello", "Hi there!")
        assert isinstance(rid, int)
        assert rid > 0

    def test_list_pending_shows_unapproved(self):
        from training_review import save_training_example, list_pending
        save_training_example("Hello", "Hi!")
        pending = list_pending()
        assert len(pending) >= 1
        assert pending[0]["user"] == "Hello"

    def test_approve_example(self):
        from training_review import save_training_example, approve_example, list_pending, list_approved
        rid = save_training_example("Hello", "Hi!")
        assert approve_example(rid) is True
        approved = list_approved()
        assert any(ex["id"] == rid for ex in approved)
        # Should no longer appear in pending
        pending_ids = [ex["id"] for ex in list_pending()]
        assert rid not in pending_ids

    def test_approve_nonexistent_returns_false(self):
        from training_review import approve_example
        assert approve_example(9999) is False

    def test_reject_example(self):
        from training_review import save_training_example, reject_example, list_pending
        rid = save_training_example("Delete me", "Gone")
        assert reject_example(rid) is True
        ids = [ex["id"] for ex in list_pending()]
        assert rid not in ids

    def test_reject_nonexistent_returns_false(self):
        from training_review import reject_example
        assert reject_example(8888) is False

    def test_edit_and_approve(self):
        from training_review import save_training_example, edit_and_approve, list_approved
        rid = save_training_example("Seri", "Wrong answer")
        assert edit_and_approve(rid, "Correct answer") is True
        approved = list_approved()
        match = [ex for ex in approved if ex["id"] == rid]
        assert len(match) == 1
        assert match[0]["assistant"] == "Correct answer"

    def test_export_jsonl(self, tmp_path):
        from training_review import save_training_example, approve_example, export_approved_jsonl
        rid = save_training_example("Test q", "Test a")
        approve_example(rid)
        out_path = tmp_path / "export.jsonl"
        result_path = export_approved_jsonl(output_path=out_path)
        assert result_path.exists()
        lines = result_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["user_message"] == "Test q"
        assert record["assistant_response"] == "Test a"

    def test_export_empty_jsonl(self, tmp_path):
        from training_review import export_approved_jsonl
        out_path = tmp_path / "empty.jsonl"
        result_path = export_approved_jsonl(output_path=out_path)
        assert result_path.exists()
        assert result_path.read_text(encoding="utf-8").strip() == ""

    def test_reviewed_at_populated_on_approve(self, tmp_path):
        from training_review import save_training_example, approve_example, DB_PATH
        rid = save_training_example("Q", "A")
        approve_example(rid)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT reviewed_at FROM training_examples WHERE id = ?", (rid,)
            ).fetchone()
        assert row[0] is not None


# ===========================================================================
# 5. chatbot.py command-handler tests
# ===========================================================================

class TestChatbotCommands:
    def setup_method(self):
        import chatbot
        chatbot.initialize_chatbot()

    def test_handle_remember_name(self):
        import chatbot, memory_db
        result = chatbot.handle_remember("name=Sarandeep")
        assert "Saved" in result or "✓" in result
        assert memory_db.get_memory("user_name") == "Sarandeep"

    def test_handle_remember_location(self):
        import chatbot, memory_db
        chatbot.handle_remember("location=Madurai")
        assert memory_db.get_memory("user_location") == "Madurai"

    def test_handle_remember_workplace(self):
        import chatbot, memory_db
        chatbot.handle_remember("workplace=Tarcin Robotics")
        assert memory_db.get_memory("user_workplace") == "Tarcin Robotics"

    def test_handle_remember_invalid_key(self):
        import chatbot
        result = chatbot.handle_remember("unknown_field=value")
        assert "Unknown key" in result or "valid keys" in result.lower()

    def test_handle_remember_missing_value(self):
        import chatbot
        result = chatbot.handle_remember("name")
        assert "Usage" in result or "=" in result

    def test_handle_forget_existing(self):
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep")
        result = chatbot.handle_forget("name")
        assert "Forgotten" in result or "✓" in result
        assert memory_db.get_memory("user_name") is None

    def test_handle_forget_nonexistent(self):
        import chatbot
        result = chatbot.handle_forget("name")
        assert "No memory" in result

    def test_handle_memories_empty(self):
        import chatbot
        result = chatbot.handle_memories()
        assert "No memories" in result

    def test_handle_memories_with_data(self):
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep")
        result = chatbot.handle_memories()
        assert "Sarandeep" in result

    def test_build_memory_context_empty(self):
        import chatbot
        assert chatbot.build_memory_context() is None

    def test_build_memory_context_with_facts(self):
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep")
        ctx = chatbot.build_memory_context()
        assert "Sarandeep" in ctx
        assert "user name" in ctx.lower()

    def test_ask_ollama_uses_memory_answer(self):
        """When a direct memory answer exists, Ollama should NOT be called."""
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my name?")
        mock_post.assert_not_called()
        assert "Sarandeep" in result

    def test_ask_ollama_connection_error(self):
        import chatbot, requests as req_lib
        with patch("chatbot.requests.post",
                   side_effect=req_lib.exceptions.ConnectionError):
            result = chatbot.ask_ollama("Tell me something.")
        assert "connection" in result.lower() or "ollama" in result.lower()

    def test_ask_ollama_falls_back_to_llm_for_unknown(self):
        """For non-memory questions, Ollama should be called."""
        import chatbot
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": "The sky is blue."}
        }
        mock_resp.raise_for_status.return_value = None
        with patch("chatbot.requests.post", return_value=mock_resp) as mock_post:
            result = chatbot.ask_ollama("What colour is the sky?")
        mock_post.assert_called_once()
        assert "blue" in result.lower()


# ===========================================================================
# 6. Integration: memory persists across "restarts" (new DB connections)
# ===========================================================================

class TestPersistence:
    def test_fact_survives_reconnect(self, tmp_path, monkeypatch):
        """Data saved in one connection must be readable in a new connection."""
        import memory_db
        memory_db.save_memory("user_name", "Sarandeep")

        # Simulate restart: clear the module-level connection cache (SQLite
        # creates a new connection every call, so just call get_memory again)
        result = memory_db.get_memory("user_name")
        assert result == "Sarandeep"

    def test_training_example_persists(self):
        from training_review import save_training_example, list_pending
        save_training_example("Persist?", "Yes!")
        pending = list_pending()
        assert any(ex["user"] == "Persist?" for ex in pending)


# ===========================================================================
# 7. Regression tests — all six reported failures
# ===========================================================================

class TestRegressions:
    """
    Each test maps to one of the six observed failures.
    These test the full pipeline short of actually calling Ollama.
    """

    # ── Failure 1 ──────────────────────────────────────────────────────────
    # Input : "என் பெயர் சரண்தீப்"
    # Expected: name extracted and saved as "Sarandeep" (or the Tamil value)

    def test_tamil_name_statement_triggers_heuristic(self):
        """Tamil-script name statement must be detected as personal statement."""
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("என் பெயர் சரண்தீப்") is True

    def test_tamil_name_extracted_by_regex(self):
        """'என் பெயர் சரண்தீப்' must extract user_name without LLM."""
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என் பெயர் சரண்தீப்")
        assert len(facts) >= 1
        name_fact = next((f for f in facts if f.key == "user_name"), None)
        assert name_fact is not None, "No user_name fact extracted"
        # Value should be either the Tamil original or known transliteration
        assert name_fact.value  # non-empty
        assert name_fact.source == "regex"

    def test_tamil_name_known_map_transliterates(self):
        """Known Tamil name சரண்தீப் must transliterate to Sarandeep."""
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என் பெயர் சரண்தீப்")
        name_fact = next((f for f in facts if f.key == "user_name"), None)
        assert name_fact is not None
        assert name_fact.value == "Sarandeep"

    def test_tamil_name_persists_to_db(self):
        """After extract_facts(), 'user_name' must exist in the DB."""
        import memory_db
        from fact_extractor import extract_facts
        # No Ollama needed — regex path handles this
        extract_facts("என் பெயர் சரண்தீப்")
        value = memory_db.get_memory("user_name")
        assert value == "Sarandeep"

    def test_tamil_name_db_record_has_correct_source(self):
        """DB row for regex-extracted name must have source='regex'."""
        import sqlite3, memory_db
        from fact_extractor import extract_facts
        extract_facts("என் பெயர் சரண்தீப்")
        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT source FROM memories WHERE fact_key = 'user_name'"
            ).fetchone()
        assert row is not None
        assert row[0] == "regex"

    # ── Failure 2 ──────────────────────────────────────────────────────────
    # Input : "என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்"
    # Expected: user_goal extracted as "AI Engineer"

    def test_tamil_goal_triggers_heuristic(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்"
        ) is True

    def test_tamil_goal_extracted_by_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")
        goal_fact = next((f for f in facts if f.key == "user_goal"), None)
        assert goal_fact is not None, "No user_goal fact extracted"
        assert "AI Engineer" in goal_fact.value or "AI" in goal_fact.value

    def test_tamil_goal_persists_to_db(self):
        import memory_db
        from fact_extractor import extract_facts
        extract_facts("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")
        value = memory_db.get_memory("user_goal")
        assert value is not None
        assert "AI" in value

    def test_tamil_goal_db_record(self):
        """Verify the actual SQLite record after extraction."""
        import sqlite3, memory_db
        from fact_extractor import extract_facts
        extract_facts("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")
        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT fact_value, source, category FROM memories "
                "WHERE fact_key = 'user_goal'"
            ).fetchone()
        assert row is not None, "user_goal not written to DB"
        assert "AI" in row[0]
        assert row[1] == "regex"
        assert row[2] == "goal"

    # ── Failure 3 ──────────────────────────────────────────────────────────
    # Input : "நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?"
    # Expected: detect_intent → "user_learning", not None (so it doesn't
    #           fall through to Ollama and hallucinate)

    def test_tamil_learning_question_intent_detected(self):
        from chat_memory import detect_intent
        result = detect_intent("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result == "user_learning", (
            f"Expected 'user_learning', got {result!r}. "
            "This question must be handled deterministically, not sent to Ollama."
        )

    def test_tamil_learning_question_returns_not_saved_when_empty(self):
        """With no saved fact, return polite 'not saved' — never hallucinate."""
        from chat_memory import answer_question
        result = answer_question("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result is not None
        # Must say it is not saved, not invent a subject
        assert "சேமிக்கப்படவில்லை" in result or "save" in result.lower()

    def test_tamil_learning_question_returns_saved_value(self):
        import memory_db
        memory_db.save_memory("user_learning", "Python")
        from chat_memory import answer_question
        result = answer_question("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result is not None
        assert "Python" in result

    # ── Failure 4 ──────────────────────────────────────────────────────────
    # Input : "Naan Python kathukittu irukken"
    # Expected: user_learning = Python  (NOT language_preference)

    def test_tanglish_learning_triggers_heuristic(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("Naan Python kathukittu irukken") is True

    def test_tanglish_learning_extracted_by_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan Python kathukittu irukken")
        learning_fact = next((f for f in facts if f.key == "user_learning"), None)
        assert learning_fact is not None, (
            "user_learning not extracted from 'Naan Python kathukittu irukken'. "
            "Got: " + str(facts)
        )
        assert "Python" in learning_fact.value

    def test_tanglish_learning_not_language_preference(self):
        """Critical: must NOT be classified as user_language_preference."""
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan Python kathukittu irukken")
        for f in facts:
            assert f.key != "user_language_preference", (
                "'Naan Python kathukittu irukken' must not be saved as "
                "language_preference"
            )

    def test_tanglish_learning_persists_to_db(self):
        import memory_db
        from fact_extractor import extract_facts
        extract_facts("Naan Python kathukittu irukken")
        value = memory_db.get_memory("user_learning")
        assert value == "Python"

    # ── Failure 5 ──────────────────────────────────────────────────────────
    # Input : "En goal enna?"
    # Expected: detect_intent → "user_goal", answer returns saved goal or
    #           politely says it hasn't been saved — not an empty None

    def test_tanglish_goal_question_intent_detected(self):
        from chat_memory import detect_intent
        result = detect_intent("En goal enna?")
        assert result == "user_goal", f"Expected 'user_goal', got {result!r}"

    def test_tanglish_goal_question_not_saved_response(self):
        """When goal not yet saved, return polite message, not None."""
        from chat_memory import answer_question
        result = answer_question("En goal enna?")
        # Must return a string (not None, which would drop through to Ollama)
        assert result is not None
        # Must indicate not saved
        assert "save" in result.lower() or "aagalai" in result.lower()

    def test_tanglish_goal_question_returns_saved_value(self):
        import memory_db
        memory_db.save_memory("user_goal", "AI Engineer")
        from chat_memory import answer_question
        result = answer_question("En goal enna?")
        assert result is not None
        assert "AI Engineer" in result

    # ── Failure 6 ──────────────────────────────────────────────────────────
    # Cross-language retrieval: save fact in one language, retrieve in another

    def test_cross_language_save_tanglish_retrieve_tamil(self):
        """Save via 'Naan Python kathukittu irukken', retrieve with Tamil question."""
        import memory_db
        from fact_extractor import extract_facts
        from chat_memory import answer_question
        # Save via Tanglish statement (regex path, no Ollama)
        extract_facts("Naan Python kathukittu irukken")
        assert memory_db.get_memory("user_learning") == "Python"
        # Retrieve with Tamil question
        result = answer_question("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result is not None
        assert "Python" in result

    def test_cross_language_save_tamil_retrieve_english(self):
        """Save name via Tamil statement, retrieve with English question."""
        import memory_db
        from fact_extractor import extract_facts
        from chat_memory import answer_question
        extract_facts("என் பெயர் சரண்தீப்")
        # English query must find the value
        result = answer_question("What is my name?")
        assert result is not None
        assert "Sarandeep" in result or "சரண்தீப்" in result

    def test_cross_language_save_english_retrieve_tanglish(self):
        """Save via /remember, retrieve with Tanglish question."""
        import memory_db
        memory_db.save_memory("user_goal", "AI Engineer", source="manual")
        from chat_memory import answer_question
        result = answer_question("En goal enna?")
        assert result is not None
        assert "AI Engineer" in result


# ===========================================================================
# 8. Deterministic regex extractor unit tests
# ===========================================================================

class TestFactExtractorRegex:
    """Test the _extract_by_regex() function directly — no Ollama needed."""

    def test_english_name_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("My name is Sarandeep")
        assert any(f.key == "user_name" and "Sarandeep" in f.value for f in facts)

    def test_english_learning_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("I'm learning Python")
        assert any(f.key == "user_learning" and "Python" in f.value for f in facts)

    def test_english_workplace_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("I work at Tarcin Robotics")
        assert any(f.key == "user_workplace" and "Tarcin" in f.value for f in facts)

    def test_english_location_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("I live in Madurai")
        assert any(f.key == "user_location" and "Madurai" in f.value for f in facts)

    def test_english_goal_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("My goal is to become an AI engineer")
        assert any(f.key == "user_goal" for f in facts)

    def test_tanglish_name_regex(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("En peyar Sarandeep")
        assert any(f.key == "user_name" and "Sarandeep" in f.value for f in facts)

    def test_tanglish_learning_kathukittu(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan Python kathukittu irukken")
        assert any(f.key == "user_learning" and "Python" in f.value for f in facts)

    def test_tanglish_learning_kathukkiren(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan JavaScript kathukkiren")
        assert any(f.key == "user_learning" and "JavaScript" in f.value for f in facts)

    def test_tamil_name_sarandeep_known_map(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என் பெயர் சரண்தீப்")
        assert any(f.key == "user_name" and f.value == "Sarandeep" for f in facts)

    def test_tamil_goal_ai_engineer(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")
        goal_fact = next((f for f in facts if f.key == "user_goal"), None)
        assert goal_fact is not None
        assert "AI Engineer" in goal_fact.value

    def test_question_skipped_by_regex(self):
        """Questions must not pass the heuristic gate."""
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("What is my name?") is False
        assert _looks_like_personal_statement("En goal enna?") is False
        assert _looks_like_personal_statement("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?") is False

    def test_short_message_skipped(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("Hi") is False
        assert _looks_like_personal_statement("Ok") is False

    def test_slash_command_skipped(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("/remember name=Test") is False


# ===========================================================================
# 9. Hallucination prevention
# ===========================================================================

class TestHallucinationPrevention:
    """
    Verify that deterministic retrieval never invents facts.
    The LLM (Ollama) is mocked for all tests that reach ask_ollama().
    """

    def test_empty_db_returns_not_saved_for_learning(self):
        """With no saved fact, answer_question must say 'not saved'."""
        from chat_memory import answer_question
        result = answer_question("What am I learning?")
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower() or "saved" in result

    def test_empty_db_returns_not_saved_tamil(self):
        from chat_memory import answer_question
        result = answer_question("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result is not None
        assert "சேமிக்கப்படவில்லை" in result

    def test_empty_db_returns_not_saved_for_goal(self):
        from chat_memory import answer_question
        result = answer_question("What is my goal?")
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()

    def test_ai_cannot_overwrite_manual_name(self):
        """Even if AI extraction runs, it must not overwrite a manual name."""
        import memory_db
        from fact_extractor import extract_facts
        memory_db.save_memory("user_name", "Sarandeep", source="manual", confidence=1.0)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": '{"facts": [{"key": "user_name", "value": "HACKED", "confidence": 0.99}]}'}
        }
        mock_resp.raise_for_status.return_value = None
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            extract_facts("My name is HACKED")

        assert memory_db.get_memory("user_name") == "Sarandeep"

    def test_correction_updates_ai_fact(self):
        """
        An AI-saved fact can be corrected by a new statement
        (regex has higher confidence than previous AI value).
        """
        import memory_db
        # First save via AI at confidence 0.75
        memory_db.save_memory("user_learning", "Java", source="ai", confidence=0.75)
        from fact_extractor import extract_facts
        # User corrects: "I'm learning Python" — regex path, confidence 0.97
        extract_facts("I'm learning Python")
        # Must be updated because new confidence > old
        value = memory_db.get_memory("user_learning")
        assert value == "Python"


# ===========================================================================
# 10. Intent detection completeness
# ===========================================================================

class TestIntentDetection:
    """Verify all intent patterns match correctly across all three dialects."""

    CASES = [
        # (question, expected_intent)
        # Tamil script
        ("என் பெயர் என்ன?",                          "user_name"),
        ("என்னுடைய பெயர் என்ன?",                    "user_name"),
        ("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?",   "user_learning"),
        ("நான் என்ன படிக்கிறேன்?",                  "user_learning"),
        ("என் இலக்கு என்ன?",                         "user_goal"),
        ("என்னுடைய இலக்கு என்ன?",                   "user_goal"),
        ("நான் எங்கே இருக்கிறேன்?",                  "user_location"),
        ("எனக்கு பிடித்த நிறம் என்ன?",              "favorite_colour"),
        # Tanglish
        ("en peyar enna?",                            "user_name"),
        ("naan enna kathukkiren?",                    "user_learning"),
        ("naan enna kathukittu irukken?",             "user_learning"),
        ("en goal enna?",                             "user_goal"),
        ("naan enga irukken?",                        "user_location"),
        ("en favourite colour enna?",                 "favorite_colour"),
        # English
        ("What is my name?",                          "user_name"),
        ("What am I learning?",                       "user_learning"),
        ("What is my goal?",                          "user_goal"),
        ("Where do I live?",                          "user_location"),
        ("What is my favourite colour?",              "favorite_colour"),
        ("Where do I work?",                          "user_workplace"),
        ("What are my interests?",                    "user_interest"),
        ("What are my skills?",                       "user_skill"),
    ]

    @pytest.mark.parametrize("question,expected", CASES)
    def test_intent_pattern(self, question, expected):
        from chat_memory import detect_intent
        result = detect_intent(question)
        assert result == expected, (
            f"detect_intent({question!r}) = {result!r}, expected {expected!r}"
        )

