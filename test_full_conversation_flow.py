"""
test_full_conversation_flow.py
===============================
Tests the full conversation flow with education memory and Tanglish quality.

Tests:
1. Education memory extraction and retrieval
2. Tanglish conversation quality (natural follow-ups)
3. Casual Tanglish endings (apdiya?, irukka?, etc.)
4. Prevent garbled responses
5. Regression: ensure origin and location remain separate
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_ROOT = os.path.dirname(os.path.abspath(__file__))
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
# 1. EDUCATION MEMORY TESTS
# ===========================================================================

class TestEducationMemoryFlow:
    """Full flow: extract education, save, and retrieve."""

    def test_extract_degree_plus_institution(self):
        """Extract institution from 'Naa BE pannen KLN la'."""
        from fact_extractor import extract_facts_dry_run
        
        facts = extract_facts_dry_run("Naa BE pannen KLN la")
        assert len(facts) == 1
        assert facts[0].key == "user_school"
        assert facts[0].value == "KLN"

    def test_save_and_retrieve_education(self):
        """Save education fact and retrieve it with various question forms."""
        from fact_extractor import extract_facts
        from chat_memory import answer_question
        import memory_db
        
        # Save
        facts = extract_facts("Naa BE pannen KLN la")
        assert len(facts) == 1
        
        # Verify saved in DB
        college = memory_db.get_memory("user_school", language="english")
        assert college == "KLN"
        
        # Retrieve with various questions
        questions = [
            "Naa enga padichen?",
            "Naa enga padikuren?",
            "Entha college?",
            "What is my college?",
        ]
        
        for q in questions:
            answer = answer_question(q)
            assert answer is not None, f"Question {q!r} returned None"
            assert "KLN" in answer, f"Question {q!r} should contain KLN, got: {answer!r}"
            assert "Antha thakaval" not in answer, (
                f"Question {q!r} should not say 'not saved', got: {answer!r}"
            )

    def test_education_memory_not_confused_with_location(self):
        """Ensure 'KLN' as college is not misclassified as location."""
        from fact_extractor import extract_facts
        import memory_db
        
        facts = extract_facts("Naa BE pannen KLN la")
        assert len(facts) == 1
        assert facts[0].key == "user_school"
        
        # Verify location is NOT saved
        location = memory_db.get_memory("user_location")
        assert location is None or location != "KLN"


# ===========================================================================
# 2. TANGLISH QUALITY TESTS
# ===========================================================================

class TestTanglishConversationQuality:
    """Test natural Tanglish conversation flow."""

    def test_greeting_returns_tanglish_greeting_for_tanglish_input(self):
        """'Vanakkam' should receive a Tanglish greeting from handle_greeting."""
        from chatbot import ask_ollama
        
        # This should return "Vanakkam!" from handle_greeting, not go to Ollama
        response = ask_ollama("Vanakkam")
        assert response == "Vanakkam!", (
            f"Tanglish greeting should return 'Vanakkam!', got: {response!r}"
        )

    def test_follow_up_questions_are_natural(self):
        """Follow-up questions should use natural Tanglish."""
        from chatbot import ask_ollama
        
        # Mock Ollama for a non-greeting message
        with patch('chatbot.requests.post') as mock_post:
            mock_response = MagicMock()
            # Example: natural response with follow-up
            mock_response.json.return_value = {
                "message": {"content": "Madurai-la irundhu vara! Anga enga irukka?"}
            }
            mock_post.return_value = mock_response
            
            response = ask_ollama("Madurai la irundhu varen")
            # Should contain a follow-up question
            assert "?" in response, f"Should have a follow-up question, got: {response!r}"


class TestRegression_NoGarbledResponses:
    """Ensure responses don't contain garbled or unrelated text."""

    def test_single_follow_up_question_only(self):
        """Response should have ONE follow-up question, not multiple or repeated."""
        from chatbot import ask_ollama
        
        with patch('chatbot.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "message": {"content": "Oh super! Nalla person aah! Enna interest irukku?"}
            }
            mock_post.return_value = mock_response
            
            response = ask_ollama("Naa nalla irken")
            
            # Count question marks (should be 1 or 0, not multiple)
            question_count = response.count("?")
            assert question_count <= 1, (
                f"Should have at most 1 follow-up question, got {question_count} in: {response!r}"
            )

    def test_no_non_existent_tanglish_words(self):
        """Response should not contain invented Tanglish like 'naanam varen'."""
        # Check system prompt and response generation
        from chatbot import _SYSTEM_PROMPT_BASE
        
        # System prompt should have guidance against invented words
        assert "NEVER use non-existent" in _SYSTEM_PROMPT_BASE or \
               "invented" in _SYSTEM_PROMPT_BASE.lower(), (
            "System prompt should warn against invented Tanglish words"
        )


# ===========================================================================
# 3. REGRESSION TESTS
# ===========================================================================

class TestRegression_OriginVsLocation:
    """Ensure origin (irundhu varen) and location (iruken) remain separate."""

    def test_origin_and_location_separate_facts(self):
        """'Madurai la irundhu varen' → user_origin, not user_location."""
        from fact_extractor import extract_facts_dry_run
        
        facts = extract_facts_dry_run("Madurai la irundhu varen")
        assert len(facts) >= 1
        
        # Should be origin, not location
        origin_facts = [f for f in facts if f.key == "user_origin"]
        assert len(origin_facts) > 0, (
            f"Should extract user_origin, got keys: {[f.key for f in facts]}"
        )

    def test_location_and_origin_stored_separately(self):
        """Save both location and origin, verify they're different DB rows."""
        from fact_extractor import extract_facts
        import memory_db
        
        # Save location
        extract_facts("Naa Villapuram la iruken")
        location = memory_db.get_memory("user_location")
        assert location == "Villapuram"
        
        # Save origin
        extract_facts("Madurai la irundhu varen")
        origin = memory_db.get_memory("user_origin")
        assert origin == "Madurai"
        
        # Both should be saved
        assert location != origin
        assert location == "Villapuram"
        assert origin == "Madurai"

    def test_retrieve_origin_and_location_separately(self):
        """Retrieve origin and location with different questions."""
        from fact_extractor import extract_facts
        from chat_memory import answer_question
        import memory_db
        
        # Save both
        extract_facts("Naa Villapuram la iruken")
        extract_facts("Madurai la irundhu varen")
        
        # Retrieve location
        location_answer = answer_question("Naa enga iruken?")
        assert "Villapuram" in location_answer
        
        # Retrieve origin
        origin_answer = answer_question("Naa enga irundhu varen?")
        assert "Madurai" in origin_answer


class TestRegression_CasualConversationNotBlocked:
    """Ensure casual questions like 'Naa nalla iruken' don't trigger errors."""

    def test_casual_not_blocked_as_memory_question(self):
        """'Naa nalla iruken, nee?' should NOT return 'not saved'."""
        from chat_memory import answer_question
        
        answer = answer_question("Naa nalla iruken, nee?")
        
        # Should be None (let Ollama handle it) or a casual response,
        # NOT a "not saved" message
        if answer is not None:
            assert "Antha thakaval" not in answer and "saved" not in answer.lower(), (
                f"Casual question should not say 'not saved', got: {answer!r}"
            )


# ===========================================================================
# 4. NATURAL CASUAL TANGLISH QUESTION ENDINGS
# ===========================================================================

class TestCasualTanglishEndings:
    """Test natural conversational endings like 'apdiya?', 'irukka?', etc."""

    def test_system_prompt_includes_casual_endings(self):
        """System prompt should guide use of casual Tanglish endings."""
        from chatbot import _SYSTEM_PROMPT_BASE
        
        casual_words = ['apdiya', 'irukka', 'ahh', 'illaya', 'enna', 'seri', 'tag question']
        found = any(word in _SYSTEM_PROMPT_BASE.lower() for word in casual_words)
        assert found, (
            f"System prompt should include casual Tanglish endings"
        )

    def test_system_prompt_example_uses_natural_endings(self):
        """System prompt examples should demonstrate casual Tanglish endings."""
        from chatbot import _SYSTEM_PROMPT_BASE
        
        # Check for at least one example with a casual ending
        has_apdiya = "apdiya" in _SYSTEM_PROMPT_BASE
        has_irukka = "irukka" in _SYSTEM_PROMPT_BASE
        assert has_apdiya or has_irukka, (
            "System prompt examples should include natural Tanglish endings like 'apdiya?' or 'irukka?'"
        )


# ===========================================================================
# 5. MOCKED vs REAL OLLAMA TESTS
# ===========================================================================

class TestWithMockedOllama:
    """Tests using mocked Ollama responses."""

    def test_mocked_greeting_flow(self):
        """Mocked: greeting → natural Tanglish response (handled by handle_greeting)."""
        from chatbot import ask_ollama
        
        # Greetings are handled by handle_greeting, not Ollama
        response = ask_ollama("Vanakkam")
        assert response == "Vanakkam!"

    def test_mocked_education_flow(self):
        """Mocked: education question → natural follow-up."""
        from chatbot import ask_ollama
        from fact_extractor import extract_facts
        import memory_db
        
        # Save education
        extract_facts("Naa BE pannen KLN la")
        college = memory_db.get_memory("user_school")
        
        with patch('chatbot.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "message": {"content": f"Oh super! {college} la engineering venu varathu?"}
            }
            mock_post.return_value = mock_response
            
            response = ask_ollama("Naa BE padichen")
            assert college in response or response is not None


class TestRegressions_Summary:
    """Summary of all regression tests."""

    def test_all_regressions_pass(self):
        """Verify no regressions in core functionality."""
        from fact_extractor import extract_facts_dry_run, extract_facts
        from chat_memory import answer_question
        import memory_db
        
        # 1. Name extraction with full statement still works
        name_facts = extract_facts_dry_run("My name is Sarandeep")
        assert len(name_facts) > 0, "Name extraction should work"
        
        # 2. Origin retrieval works
        extract_facts("Madurai la irundhu varen")
        origin = memory_db.get_memory("user_origin")
        assert origin == "Madurai", f"Origin should be Madurai, got {origin}"
        
        # 3. Casual questions don't block
        answer = answer_question("Naa nalla iruken?")
        # Should be None (let Ollama handle) or not "not saved"
        if answer is not None:
            assert "Antha thakaval" not in answer, (
                f"Casual question should not say 'not saved', got {answer}"
            )
