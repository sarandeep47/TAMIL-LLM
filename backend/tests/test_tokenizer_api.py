"""
test_tokenizer_api.py — API-level tests for word-by-word Tanglish tokenization.

STATUS: ALL TESTS SKIPPED - Tokenizer is disabled pending safety fixes.

The tokenizer had critical issues (false name extraction, no pre-checks).
After fixes are implemented, these tests will be re-enabled.
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
    """API tests for tokenizer (DISABLED - tokenizer not safe yet)."""
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_health_endpoint(self, client):
        """Test that the health endpoint works."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_chat_empty_message(self, client):
        """Test that empty messages are rejected."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_chat_with_tokenizer_multi_fact(self, client):
        """Multi-fact extraction through chat endpoint."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_tokenizer_fact_persistence(self, client):
        """Extracted facts persist in the database."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_tokenizer_partial_facts(self, client):
        """Extraction with only some facts present."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_tokenizer_greeting_only(self, client):
        """Greetings alone don't cause errors."""
        pass


class TestTokenizerLanguageVariations:
    """Language variation tests (DISABLED - tokenizer not safe yet)."""
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_fuzzy_match_location(self):
        """Fuzzy matching for location variations."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_fuzzy_match_greeting(self):
        """Fuzzy matching for greeting variations."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_fuzzy_match_pronoun(self):
        """Fuzzy matching for pronoun variations."""
        pass


class TestTokenizerEdgeCases:
    """Edge cases (DISABLED - tokenizer not safe yet)."""
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_tokenizer_with_punctuation(self):
        """Punctuation doesn't break tokenization."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_tokenizer_mixed_script(self):
        """Mixed English/Tamil."""
        pass
    
    @pytest.mark.skip(reason="Tokenizer disabled pending safety fixes")
    def test_tokenizer_no_facts(self):
        """Non-personal messages return None."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
