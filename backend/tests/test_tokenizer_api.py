"""
test_tokenizer_api.py — API-level tests for word-by-word Tanglish tokenization.

Tests multi-fact extraction through the /api/chat endpoint.
"""

import os
import sys
import pytest

# Set test environment
os.environ["OLLAMA_URL"] = "http://localhost:11434/api/chat"
os.environ["MODEL"] = "llama3.2:3b"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"

# Add parent directory to path for imports
sys.path.insert(0, str(os.path.dirname(__file__).replace("\\", "/").rsplit("/", 2)[0]))

from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """Clear and initialize test database."""
    # Remove test DB if it exists
    db_path = "data/processed/memory.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
    
    # Re-initialize
    from memory_db import initialize_database
    initialize_database()
    
    yield
    
    # Cleanup after test
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


class TestTokenizerAPI:
    """Test tokenizer integration through the API."""
    
    def test_health_endpoint(self, client):
        """Test that the health endpoint works."""
        response = client.get("/health")
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_chat_empty_message(self, client):
        """Test that empty messages are rejected."""
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 400
    
    def test_chat_with_tokenizer_multi_fact(self, client):
        """
        Test multi-fact extraction through chat endpoint.
        
        Input: "vannakam en peru sarandeep naa madurai la irundhu varen"
        Expected: Extract name and location, save to DB, return acknowledgment
        """
        # This test would need Ollama running. For now, we skip the actual
        # Ollama call and just test fact extraction.
        # In production, run with: OLLAMA_URL=http://localhost:11434/api/chat
        
        message = "vannakam en peru sarandeep naa madurai la irundhu varen"
        
        # We'll use the direct functions instead of HTTP to avoid Ollama dependency
        from chat_memory import extract_and_save_multi_facts_tanglish, acknowledge_statement
        from memory_db import get_memory
        
        # Extract and save facts
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Verify facts were extracted
        assert facts is not None
        assert "user_name" in facts
        assert facts["user_name"] == "sarandeep"
        assert "user_location" in facts
        assert facts["user_location"] == "madurai"
        
        # Verify they're in the database
        assert get_memory("user_name") == "sarandeep"
        assert get_memory("user_location") == "madurai"
        
        # Verify acknowledgment works
        ack = acknowledge_statement(message)
        assert ack is not None
        assert "sarandeep" in ack.lower() or "peyar" in ack.lower()
    
    def test_tokenizer_fact_persistence(self, client):
        """Test that extracted facts persist in the database."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory, list_memories
        
        message = "en peru kavya madurai la irundhu varen"
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Verify facts in DB
        memories = list_memories()
        assert len(memories) >= 1
        
        # Check specific values
        assert get_memory("user_name") == "kavya"
        assert get_memory("user_location") == "madurai"
    
    def test_tokenizer_partial_facts(self, client):
        """Test extraction with only some facts present."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        from memory_db import get_memory
        
        # Only name, no location
        message = "en peru ravi"
        facts = extract_and_save_multi_facts_tanglish(message)
        
        assert facts is not None
        assert facts.get("user_name") == "ravi"
        assert get_memory("user_name") == "ravi"
    
    def test_tokenizer_greeting_only(self, client):
        """Test that greetings alone don't cause errors."""
        from chat_memory import extract_and_save_multi_facts_tanglish, acknowledge_statement
        
        message = "vannakam"
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Greetings don't save facts
        assert facts is None or len(facts) == 0
        
        # But acknowledge_statement shouldn't crash
        ack = acknowledge_statement(message)
        # Should be None since no facts to acknowledge
        assert ack is None


class TestTokenizerLanguageVariations:
    """Test tokenizer with different Tanglish spellings."""
    
    def test_fuzzy_match_location(self):
        """Test fuzzy matching for location variations."""
        from model.tanglish_tokenizer import parse_tanglish
        
        # "irundu" instead of "irundhu" (common variation)
        tokens, stmt = parse_tanglish("naa madurai la irundu varen")
        
        assert stmt.location == "madurai"
    
    def test_fuzzy_match_greeting(self):
        """Test fuzzy matching for greeting variations."""
        from model.tanglish_tokenizer import parse_tanglish
        
        # Various greeting spellings
        for greeting in ["vannakam", "vanakkam", "vanakam"]:
            tokens, stmt = parse_tanglish(greeting)
            assert stmt.greeting is not None
    
    def test_fuzzy_match_pronoun(self):
        """Test fuzzy matching for pronoun variations."""
        from model.tanglish_tokenizer import parse_tanglish
        
        # "naa" vs "naan"
        tokens1, stmt1 = parse_tanglish("naa peru ravi")
        tokens2, stmt2 = parse_tanglish("naan peru ravi")
        
        # Both should extract the name
        assert stmt1.name == "ravi"
        assert stmt2.name == "ravi"


class TestTokenizerEdgeCases:
    """Test edge cases and error handling."""
    
    def test_tokenizer_with_punctuation(self):
        """Test that punctuation doesn't break tokenization."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        message = "en peru sarandeep, naa madurai la irundhu varen!"
        facts = extract_and_save_multi_facts_tanglish(message)
        
        assert facts is not None
        assert facts.get("user_name") == "sarandeep"
    
    def test_tokenizer_mixed_script(self):
        """Test tokenizer with mixed English/Tamil."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        # Mix of Tanglish and English
        message = "en peru sarandeep from madurai"
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Should still extract what it can
        assert facts is not None
    
    def test_tokenizer_no_facts(self):
        """Test that non-personal messages return None."""
        from chat_memory import extract_and_save_multi_facts_tanglish
        
        message = "ithu enna?"  # What is this? (no personal facts)
        facts = extract_and_save_multi_facts_tanglish(message)
        
        # Should return None or empty dict (no personal facts)
        assert not facts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
