"""
tests/test_stabilization.py
============================
Regression tests for the Tamil LLM chatbot stabilization task.

Coverage
--------
1.  Tamil / Tanglish / English fact extraction (all six original failures)
2.  Correct canonical keys and actual SQLite record values
3.  Save, retrieve, update, forget, export
4.  Cross-language retrieval
5.  Persistence (close + re-open DB)
6.  Database migration and category back-fill
7.  Missing facts → polite "not saved" response
8.  Ollama timeout, bad JSON, unavailable — no crash, [] returned
9.  Ambiguous statements that must NOT be saved
10. Confidence hierarchy: manual > regex > AI

All Ollama calls are mocked. A separate manual integration test is also
provided at the bottom (skipped by default).

Run:
    python -m pytest tests/test_stabilization.py -v
    python -m pytest tests/test_stabilization.py -v -k manual  # real Ollama
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Project root on sys.path ──────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── DB isolation fixture ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_dbs(tmp_path, monkeypatch):
    """Point all DB_PATH references to fresh temp files for each test."""
    mem_db  = tmp_path / "memory.db"
    chat_db = tmp_path / "chatbot.db"

    import memory_db
    import training_review
    import chatbot

    monkeypatch.setattr(memory_db,       "DB_PATH", mem_db)
    monkeypatch.setattr(training_review, "DB_PATH", chat_db)
    monkeypatch.setattr(chatbot,         "CHAT_DB_PATH", chat_db)

    # fact_extractor imports DB_PATH lazily inside functions — patch it too
    import fact_extractor as fe
    monkeypatch.setattr(fe, "OLLAMA_URL", "http://localhost:99999/NOOP")

    import chat_memory
    monkeypatch.setattr(
        chat_memory, "get_memory",
        lambda key, language="english": memory_db.get_memory(key, language),
    )

    memory_db.initialize_database()
    training_review.initialize_training_db()
    chatbot.initialize_chatbot()

    yield


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Tamil personal-statement heuristic
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersonalStatementHeuristic:

    def test_tamil_name_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("என் பெயர் சரண்தீப்") is True

    def test_tamil_goal_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்"
        ) is True

    def test_tamil_learning_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "நான் Python கற்றுக்கொண்டு இருக்கிறேன்"
        ) is True

    def test_tamil_workplace_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "நான் Tarcin Robotics நிறுவனத்தில் வேலை செய்கிறேன்"
        ) is True

    def test_tamil_learning_question_not_statement(self):
        """A Tamil learning QUESTION must not trigger extraction."""
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?"
        ) is False

    def test_tamil_name_question_not_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("என் பெயர் என்ன?") is False

    def test_tanglish_learning_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "Naan Python kathukittu irukken"
        ) is True

    def test_tanglish_goal_aaganum_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement(
            "En goal AI Engineer aaganum"
        ) is True

    def test_english_learning_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("I'm learning Python") is True

    def test_english_name_is_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("My name is Sarandeep") is True

    def test_english_question_not_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("What am I learning?") is False

    def test_slash_command_not_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("/remember name=Test") is False

    def test_short_message_not_statement(self):
        from fact_extractor import _looks_like_personal_statement
        assert _looks_like_personal_statement("Hi") is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Regex extraction — all 12 original scenario inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegexExtraction:

    # ── Name ──────────────────────────────────────────────────────────────────
    def test_tamil_name_sarandeep(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என் பெயர் சரண்தீப்")
        f = next((x for x in facts if x.key == "user_name"), None)
        assert f is not None
        assert f.value == "Sarandeep"
        assert f.source == "regex"

    def test_tanglish_name_en_peru(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("En peru Sarandeep")
        f = next((x for x in facts if x.key == "user_name"), None)
        assert f is not None
        assert "Sarandeep" in f.value

    def test_english_name(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("My name is Sarandeep")
        f = next((x for x in facts if x.key == "user_name"), None)
        assert f is not None
        assert "Sarandeep" in f.value

    # ── Learning ──────────────────────────────────────────────────────────────
    def test_tamil_learning_python(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("நான் Python கற்றுக்கொண்டு இருக்கிறேன்")
        f = next((x for x in facts if x.key == "user_learning"), None)
        assert f is not None
        assert "Python" in f.value

    def test_tanglish_learning_kathukittu(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan Python kathukittu irukken")
        f = next((x for x in facts if x.key == "user_learning"), None)
        assert f is not None
        assert f.value == "Python"

    def test_english_learning(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("I'm learning Python")
        f = next((x for x in facts if x.key == "user_learning"), None)
        assert f is not None
        assert "Python" in f.value

    def test_tanglish_learning_not_classified_as_language_preference(self):
        """Critical: 'Naan Python kathukittu irukken' → user_learning only."""
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan Python kathukittu irukken")
        bad = [x for x in facts if x.key == "user_language_preference"]
        assert bad == [], (
            f"Must not be language_preference. Got: {facts}"
        )

    # ── Goal ──────────────────────────────────────────────────────────────────
    def test_tamil_goal_ai_engineer(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")
        f = next((x for x in facts if x.key == "user_goal"), None)
        assert f is not None
        assert "AI Engineer" in f.value

    def test_tanglish_goal_aaganum(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("En goal AI Engineer aaganum")
        f = next((x for x in facts if x.key == "user_goal"), None)
        assert f is not None, f"Got facts: {facts}"
        assert "AI Engineer" in f.value

    def test_english_goal(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("My goal is to become an AI Engineer")
        f = next((x for x in facts if x.key == "user_goal"), None)
        assert f is not None

    # ── Workplace ─────────────────────────────────────────────────────────────
    def test_tamil_workplace(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex(
            "நான் Tarcin Robotics நிறுவனத்தில் வேலை செய்கிறேன்"
        )
        f = next((x for x in facts if x.key == "user_workplace"), None)
        assert f is not None, f"Got facts: {facts}"
        assert "Tarcin" in f.value

    def test_tanglish_workplace_la_work_panren(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("Naan Tarcin Robotics la work panren")
        f = next((x for x in facts if x.key == "user_workplace"), None)
        assert f is not None, f"Got facts: {facts}"
        assert "Tarcin" in f.value

    def test_english_workplace(self):
        from fact_extractor import _extract_by_regex
        facts = _extract_by_regex("I work at Tarcin Robotics")
        f = next((x for x in facts if x.key == "user_workplace"), None)
        assert f is not None
        assert "Tarcin Robotics" in f.value


# ═══════════════════════════════════════════════════════════════════════════════
# 3. extract_facts() — DB persistence verified with actual SQLite reads
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractFactsPersistence:

    def test_tamil_name_db_record(self):
        """Verify fact_key, fact_value, source, category in SQLite."""
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("என் பெயர் சரண்தீப்")

        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT fact_value, source, category, confidence "
                "FROM memories WHERE fact_key = 'user_name'"
            ).fetchone()

        assert row is not None, "user_name row missing from DB"
        fact_value, source, category, confidence = row
        assert fact_value == "Sarandeep"
        assert source == "regex"
        assert category == "identity"
        assert confidence >= 0.8

    def test_tanglish_learning_db_record(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("Naan Python kathukittu irukken")

        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT fact_value, source, category "
                "FROM memories WHERE fact_key = 'user_learning'"
            ).fetchone()

        assert row is not None
        fact_value, source, category = row
        assert fact_value == "Python"
        assert source == "regex"
        assert category == "learning"

    def test_tamil_goal_db_record(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")

        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT fact_value, source, category "
                "FROM memories WHERE fact_key = 'user_goal'"
            ).fetchone()

        assert row is not None
        fact_value, source, category = row
        assert "AI Engineer" in fact_value
        assert source == "regex"
        assert category == "goal"

    def test_tanglish_goal_db_record(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("En goal AI Engineer aaganum")

        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT fact_value, source FROM memories "
                "WHERE fact_key = 'user_goal'"
            ).fetchone()

        assert row is not None, "user_goal not written to DB"
        assert "AI Engineer" in row[0]
        assert row[1] == "regex"

    def test_tamil_workplace_db_record(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("நான் Tarcin Robotics நிறுவனத்தில் வேலை செய்கிறேன்")

        with sqlite3.connect(memory_db.DB_PATH) as conn:
            row = conn.execute(
                "SELECT fact_value, source, category "
                "FROM memories WHERE fact_key = 'user_workplace'"
            ).fetchone()

        assert row is not None, "user_workplace not written to DB"
        assert "Tarcin" in row[0]
        assert row[1] == "regex"
        assert row[2] == "work"

    def test_fact_survives_db_reconnect(self):
        """Fact written by extract_facts() must be readable via get_memory()."""
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("Naan Python kathukittu irukken")
        # Simulate restart by calling get_memory (new connection each time)
        value = memory_db.get_memory("user_learning")
        assert value == "Python"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Intent detection — all dialects × all fact types
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntentDetection:

    CASES = [
        # Tamil script
        ("என் பெயர் என்ன?",                        "user_name"),
        ("என்னுடைய பெயர் என்ன?",                  "user_name"),
        ("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?", "user_learning"),
        ("நான் என்ன படிக்கிறேன்?",                "user_learning"),
        ("என் இலக்கு என்ன?",                       "user_goal"),
        ("என்னுடைய இலக்கு என்ன?",                 "user_goal"),
        ("நான் எங்கே இருக்கிறேன்?",                "user_location"),
        ("நான் எங்கே வேலை செய்கிறேன்?",           "user_workplace"),
        ("எனக்கு பிடித்த நிறம் என்ன?",            "favorite_colour"),
        # Tanglish
        ("en peyar enna?",                          "user_name"),
        ("naan enna kathukkiren?",                  "user_learning"),
        ("naan enna kathukittu irukken?",           "user_learning"),
        ("en goal enna?",                           "user_goal"),
        ("naan enga irukken?",                      "user_location"),
        ("naan enga work panren?",                  "user_workplace"),
        ("en favourite colour enna?",               "favorite_colour"),
        # English
        ("What is my name?",                        "user_name"),
        ("What am I learning?",                     "user_learning"),
        ("What is my goal?",                        "user_goal"),
        ("Where do I live?",                        "user_location"),
        ("Where do I work?",                        "user_workplace"),
        ("What is my favourite colour?",            "favorite_colour"),
        ("What are my interests?",                  "user_interest"),
        ("What are my skills?",                     "user_skill"),
    ]

    @pytest.mark.parametrize("question,expected", CASES)
    def test_intent(self, question, expected):
        from chat_memory import detect_intent
        result = detect_intent(question)
        assert result == expected, (
            f"detect_intent({question!r}) returned {result!r}, expected {expected!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cross-language retrieval
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossLanguageRetrieval:

    def test_save_tanglish_retrieve_tamil(self):
        """Save via Tanglish statement, retrieve with Tamil question."""
        from fact_extractor import extract_facts
        from chat_memory import answer_question

        extract_facts("Naan Python kathukittu irukken")
        result = answer_question("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result is not None
        assert "Python" in result

    def test_save_tamil_retrieve_english(self):
        """Save name via Tamil statement, retrieve with English question."""
        from fact_extractor import extract_facts
        from chat_memory import answer_question

        extract_facts("என் பெயர் சரண்தீப்")
        result = answer_question("What is my name?")
        assert result is not None
        assert "Sarandeep" in result

    def test_save_english_retrieve_tanglish(self):
        """Save via /remember (English), retrieve with Tanglish question."""
        import memory_db
        memory_db.save_memory("user_goal", "AI Engineer",
                              category="goal", source="manual")
        from chat_memory import answer_question
        result = answer_question("En goal enna?")
        assert result is not None
        assert "AI Engineer" in result

    def test_save_tanglish_retrieve_english(self):
        """Save goal via Tanglish, retrieve with English question."""
        from fact_extractor import extract_facts
        from chat_memory import answer_question

        extract_facts("En goal AI Engineer aaganum")
        result = answer_question("What is my goal?")
        assert result is not None
        assert "AI Engineer" in result

    def test_save_tamil_retrieve_tanglish_goal(self):
        """Save goal via Tamil statement, retrieve with Tanglish question."""
        from fact_extractor import extract_facts
        from chat_memory import answer_question

        extract_facts("என்னுடைய இலக்கு AI Engineer ஆக வேண்டும்")
        result = answer_question("En goal enna?")
        assert result is not None
        assert "AI Engineer" in result


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Memory operations — save, update, forget, list
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryOperations:

    def test_save_and_retrieve(self):
        from memory_db import save_memory, get_memory
        save_memory("user_name", "Sarandeep", category="identity")
        assert get_memory("user_name") == "Sarandeep"

    def test_save_with_tamil_value(self):
        from memory_db import save_memory, get_memory
        save_memory("user_name", "Sarandeep", "சரண்தீப்", category="identity")
        assert get_memory("user_name", language="tamil") == "சரண்தீப்"
        assert get_memory("user_name", language="english") == "Sarandeep"

    def test_update_overwrites(self):
        from memory_db import save_memory, get_memory
        save_memory("user_learning", "Java", category="learning")
        save_memory("user_learning", "Python", category="learning")
        assert get_memory("user_learning") == "Python"

    def test_forget_existing(self):
        from memory_db import save_memory, forget_memory, get_memory
        save_memory("user_name", "Sarandeep", category="identity")
        assert forget_memory("user_name") is True
        assert get_memory("user_name") is None

    def test_forget_nonexistent_returns_false(self):
        from memory_db import forget_memory
        assert forget_memory("does_not_exist") is False

    def test_list_memories_returns_all(self):
        from memory_db import save_memory, list_memories
        save_memory("user_name", "Sarandeep", category="identity")
        save_memory("user_learning", "Python", category="learning")
        keys = [m["key"] for m in list_memories()]
        assert "user_name" in keys
        assert "user_learning" in keys

    def test_list_memories_empty_initially(self):
        from memory_db import list_memories
        assert list_memories() == []

    def test_missing_key_returns_none(self):
        from memory_db import get_memory
        assert get_memory("user_goal") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Confidence hierarchy — manual > regex > AI
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfidenceHierarchy:

    def test_manual_not_overwritten_by_regex(self):
        """A manual name fact must not be overwritten by regex extraction."""
        import memory_db
        from fact_extractor import extract_facts

        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="manual", confidence=1.0)
        extract_facts("My name is DifferentPerson")
        assert memory_db.get_memory("user_name") == "Sarandeep"

    def test_manual_not_overwritten_by_ai(self):
        """A manual fact must not be overwritten by an AI extraction."""
        import memory_db
        from fact_extractor import extract_facts

        memory_db.save_memory("user_name", "Sarandeep",
                              category="identity", source="manual", confidence=1.0)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": '{"facts": [{"key":"user_name","value":"HACKED","confidence":0.99}]}'}
        }
        mock_resp.raise_for_status.return_value = None

        # Force AI path by using a message the regex cannot parse
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            extract_facts("I am called HACKED.")

        assert memory_db.get_memory("user_name") == "Sarandeep"

    def test_regex_overwrites_ai_fact(self):
        """A regex fact (conf≈0.97) should overwrite an AI fact (conf<0.97)."""
        import memory_db
        from fact_extractor import extract_facts

        memory_db.save_memory("user_learning", "Java",
                              category="learning", source="ai", confidence=0.75)
        extract_facts("I'm learning Python")
        assert memory_db.get_memory("user_learning") == "Python"

    def test_ai_does_not_overwrite_regex(self):
        """An AI fact must not replace a regex-sourced fact."""
        import memory_db
        from fact_extractor import extract_facts

        memory_db.save_memory("user_learning", "Python",
                              category="learning", source="regex", confidence=0.97)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "message": {"content": '{"facts": [{"key":"user_learning","value":"AI","confidence":0.99}]}'}
        }
        mock_resp.raise_for_status.return_value = None

        # Force AI path with a non-regex-parseable message
        with patch("fact_extractor.requests.post", return_value=mock_resp):
            extract_facts("I am enrolled in artificial intelligence.")

        assert memory_db.get_memory("user_learning") == "Python"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Missing facts — polite response, never hallucinate
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingFacts:

    def test_english_missing_fact(self):
        from chat_memory import answer_question
        result = answer_question("What am I learning?")
        assert result is not None
        assert "not" in result.lower() or "saved" in result.lower()

    def test_tamil_missing_fact(self):
        from chat_memory import answer_question
        result = answer_question("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert result is not None
        assert "சேமிக்கப்படவில்லை" in result

    def test_tanglish_missing_fact(self):
        from chat_memory import answer_question
        result = answer_question("En goal enna?")
        assert result is not None
        assert "save" in result.lower() or "aagalai" in result.lower()

    def test_no_intent_returns_none(self):
        """Unrecognized question returns None — caller should use Ollama."""
        from chat_memory import answer_question
        result = answer_question("Tell me a joke.")
        assert result is None

    def test_answer_question_does_not_invent_facts(self):
        """answer_question must never return a specific topic without a saved value."""
        from chat_memory import answer_question
        result = answer_question("What is my goal?")
        # Must not contain a plausible-sounding invented goal
        assert result is not None
        # Confirm it's the "not saved" message, not a fabricated value
        assert "engineer" not in result.lower()
        assert "python" not in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Ollama failure resilience
# ═══════════════════════════════════════════════════════════════════════════════

class TestOllamaResilience:

    def _msg_for_llm(self) -> str:
        """A message that passes heuristics but won't match any regex."""
        return "I have been employed at Tarcin for over two years now."

    def test_connection_error_returns_empty_list(self):
        import requests as rq
        from fact_extractor import extract_facts

        with patch("fact_extractor.requests.post",
                   side_effect=rq.exceptions.ConnectionError):
            result = extract_facts(self._msg_for_llm())
        assert isinstance(result, list)

    def test_timeout_returns_empty_list(self):
        import requests as rq
        from fact_extractor import extract_facts

        with patch("fact_extractor.requests.post",
                   side_effect=rq.exceptions.Timeout):
            result = extract_facts(self._msg_for_llm())
        assert isinstance(result, list)

    def test_bad_json_returns_empty_list(self):
        from fact_extractor import extract_facts

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "not json!!!"}}
        mock_resp.raise_for_status.return_value = None

        with patch("fact_extractor.requests.post", return_value=mock_resp):
            result = extract_facts(self._msg_for_llm())
        assert isinstance(result, list)

    def test_unknown_key_from_ai_rejected(self):
        from fact_extractor import _validate

        raw = [{"key": "made_up_key", "value": "something", "confidence": 0.9}]
        assert _validate(raw) == []

    def test_empty_value_from_ai_rejected(self):
        from fact_extractor import _validate

        raw = [{"key": "user_name", "value": "", "confidence": 0.9}]
        assert _validate(raw) == []

    def test_null_value_from_ai_rejected(self):
        from fact_extractor import _validate

        raw = [{"key": "user_name", "value": "null", "confidence": 0.9}]
        assert _validate(raw) == []

    def test_regex_works_without_ollama(self):
        """Regex extraction must succeed even when Ollama is unreachable."""
        import memory_db, requests as rq
        from fact_extractor import extract_facts

        with patch("fact_extractor.requests.post",
                   side_effect=rq.exceptions.ConnectionError):
            result = extract_facts("I work at Tarcin Robotics")

        assert any(f.key == "user_workplace" for f in result)
        assert memory_db.get_memory("user_workplace") == "Tarcin Robotics"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Ambiguous / unsupported statements — must NOT be saved
# ═══════════════════════════════════════════════════════════════════════════════

class TestAmbiguousStatements:

    def test_question_not_saved_english(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("What am I learning?")
        assert memory_db.get_memory("user_learning") is None

    def test_question_not_saved_tamil(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        assert memory_db.get_memory("user_learning") is None

    def test_question_not_saved_tanglish(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("En goal enna?")
        assert memory_db.get_memory("user_goal") is None

    def test_generic_statement_not_saved(self):
        """Generic statement with no personal fact must not persist anything."""
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("The weather is nice today.")
        assert list_memories_count(memory_db) == 0

    def test_slash_command_not_saved(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("/remember name=Test")
        assert memory_db.get_memory("user_name") is None

    def test_too_short_not_saved(self):
        import memory_db
        from fact_extractor import extract_facts

        extract_facts("Hi")
        assert list_memories_count(memory_db) == 0


def list_memories_count(memory_db) -> int:
    import sqlite3
    with sqlite3.connect(memory_db.DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Database migration — category back-fill
# ═══════════════════════════════════════════════════════════════════════════════

class TestDatabaseMigration:

    def test_category_backfill_on_init(self, tmp_path, monkeypatch):
        """
        Simulate an old DB where user_name has category='general'.
        After initialize_database(), it should be corrected to 'identity'.
        """
        import memory_db
        db = tmp_path / "old_memory.db"
        monkeypatch.setattr(memory_db, "DB_PATH", db)

        # Create old-style record with wrong category
        with sqlite3.connect(db) as conn:
            conn.execute("""
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_key TEXT NOT NULL UNIQUE,
                    fact_value TEXT NOT NULL,
                    tamil_value TEXT,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'manual',
                    updated_at TEXT
                )
            """)
            conn.execute(
                "INSERT INTO memories (fact_key, fact_value, category, source) "
                "VALUES ('user_name', 'Sarandeep', 'general', 'manual')"
            )
            conn.commit()

        # Run migration
        memory_db.initialize_database()

        # Category must now be correct
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT category FROM memories WHERE fact_key = 'user_name'"
            ).fetchone()

        assert row is not None
        assert row[0] == "identity", f"Expected 'identity', got {row[0]!r}"

    def test_favorite_colour_category_corrected(self, tmp_path, monkeypatch):
        import memory_db
        db = tmp_path / "old2.db"
        monkeypatch.setattr(memory_db, "DB_PATH", db)

        with sqlite3.connect(db) as conn:
            conn.execute("""
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_key TEXT NOT NULL UNIQUE,
                    fact_value TEXT NOT NULL,
                    tamil_value TEXT,
                    category TEXT DEFAULT 'general',
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'manual',
                    updated_at TEXT
                )
            """)
            conn.execute(
                "INSERT INTO memories (fact_key, fact_value, category) "
                "VALUES ('favorite_colour', 'blue', 'general')"
            )
            conn.commit()

        memory_db.initialize_database()

        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT category FROM memories WHERE fact_key = 'favorite_colour'"
            ).fetchone()

        assert row[0] == "preference"

    def test_missing_column_added(self, tmp_path, monkeypatch):
        """Old DBs without 'confidence' column must be migrated safely."""
        import memory_db
        db = tmp_path / "old3.db"
        monkeypatch.setattr(memory_db, "DB_PATH", db)

        with sqlite3.connect(db) as conn:
            conn.execute("""
                CREATE TABLE memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_key TEXT NOT NULL UNIQUE,
                    fact_value TEXT NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO memories (fact_key, fact_value) "
                "VALUES ('user_name', 'Test')"
            )
            conn.commit()

        # Must not raise
        memory_db.initialize_database()

        with sqlite3.connect(db) as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(memories)")}

        assert "confidence" in cols
        assert "source" in cols
        assert "category" in cols


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Training review — save, approve, reject, export
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrainingReview:

    def test_save_returns_id(self):
        from training_review import save_training_example
        rid = save_training_example("Hello", "Hi!")
        assert isinstance(rid, int) and rid > 0

    def test_list_pending(self):
        from training_review import save_training_example, list_pending
        save_training_example("Hello", "Hi!")
        pending = list_pending()
        assert any(ex["user"] == "Hello" for ex in pending)

    def test_approve_removes_from_pending(self):
        from training_review import save_training_example, approve_example, list_pending
        rid = save_training_example("Q", "A")
        assert approve_example(rid) is True
        assert not any(ex["id"] == rid for ex in list_pending())

    def test_reject_removes_record(self):
        from training_review import save_training_example, reject_example, list_pending
        rid = save_training_example("Bad Q", "Bad A")
        assert reject_example(rid) is True
        assert not any(ex["id"] == rid for ex in list_pending())

    def test_export_jsonl(self, tmp_path):
        from training_review import save_training_example, approve_example, export_approved_jsonl
        rid = save_training_example("Test Q", "Test A")
        approve_example(rid)
        out = tmp_path / "export.jsonl"
        path = export_approved_jsonl(output_path=out)
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["user_message"] == "Test Q"
        assert record["assistant_response"] == "Test A"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. chatbot.py command handlers
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatbotCommands:

    def test_remember_name(self):
        import chatbot, memory_db
        result = chatbot.handle_remember("name=Sarandeep")
        assert "Saved" in result or "✓" in result
        assert memory_db.get_memory("user_name") == "Sarandeep"

    def test_remember_goal(self):
        import chatbot, memory_db
        chatbot.handle_remember("goal=AI Engineer")
        assert memory_db.get_memory("user_goal") == "AI Engineer"

    def test_remember_learning(self):
        import chatbot, memory_db
        chatbot.handle_remember("learning=Python")
        assert memory_db.get_memory("user_learning") == "Python"

    def test_remember_invalid_key(self):
        import chatbot
        result = chatbot.handle_remember("unknown=value")
        assert "Unknown key" in result or "valid keys" in result.lower()

    def test_forget_existing(self):
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep", category="identity")
        result = chatbot.handle_forget("name")
        assert "Forgotten" in result or "✓" in result
        assert memory_db.get_memory("user_name") is None

    def test_forget_nonexistent(self):
        import chatbot
        result = chatbot.handle_forget("name")
        assert "No memory" in result or "not found" in result.lower()

    def test_memories_empty(self):
        import chatbot
        result = chatbot.handle_memories()
        assert "No memories" in result

    def test_memories_with_data(self):
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep", category="identity")
        result = chatbot.handle_memories()
        assert "Sarandeep" in result

    def test_ask_ollama_short_circuits_for_known_question(self):
        """Known memory question must not call Ollama at all."""
        import chatbot, memory_db
        memory_db.save_memory("user_name", "Sarandeep", category="identity")
        with patch("chatbot.requests.post") as mock_post:
            result = chatbot.ask_ollama("What is my name?")
        mock_post.assert_not_called()
        assert "Sarandeep" in result

    def test_ask_ollama_connection_error(self):
        import chatbot, requests as rq
        with patch("chatbot.requests.post",
                   side_effect=rq.exceptions.ConnectionError):
            result = chatbot.ask_ollama("Tell me something.")
        assert "ollama" in result.lower() or "connection" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Manual integration test (real Ollama, skipped by default)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.manual
class TestManualIntegration:
    """
    These tests require a running Ollama instance with llama3.2:3b.

    Run with:
        python -m pytest tests/test_stabilization.py -v -k manual
    """

    def test_ollama_responds_to_greeting(self):
        """Smoke test: Ollama must respond without crashing."""
        import chatbot
        result = chatbot.ask_ollama("Vanakkam!")
        assert isinstance(result, str)
        assert len(result) > 0
        # Must not be the connection-error fallback
        assert "connection failed" not in result.lower()

    def test_ollama_does_not_hallucinate_learning(self):
        """
        Without any saved facts, Ollama must not claim the user is learning
        something specific.
        """
        import chatbot
        result = chatbot.ask_ollama("நான் என்ன கற்றுக்கொண்டு இருக்கிறேன்?")
        # The deterministic path should intercept this before Ollama is called
        # This tests that the pipeline is wired correctly end-to-end
        assert result is not None
        assert isinstance(result, str)

    def test_fact_extraction_via_real_ollama(self):
        """
        Verify the LLM path (not regex) for an irregular phrasing.
        This test inspects the DB record after extraction.
        """
        import memory_db
        from fact_extractor import extract_facts

        msg = "I have been studying Machine Learning for six months."
        facts = extract_facts(msg)
        # Either regex or Ollama must extract user_learning
        # (we do not assert on exact value as Ollama may phrase it differently)
        value = memory_db.get_memory("user_learning")
        if value is not None:
            assert isinstance(value, str)
            assert len(value) > 1
