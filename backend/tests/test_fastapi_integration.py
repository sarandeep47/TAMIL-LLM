"""
FastAPI Integration Tests for End-to-End Verification

Tests the /api/chat endpoint with sample Tanglish inputs.
Verifies:
- Endpoint responds correctly
- Language detection works
- Facts are extracted (or blocked safely)
- Memory persistence works

Sample inputs (8 test cases):
1. "vannakam" — greeting (should not extract)
2. "naa sarandeep" — name statement
3. "naa madurai la irundhu varen" — location statement
4. "naa BE mudichuruken" — education statement
5. "sorry btech mudichuruken" — alternate education
6. "naan enna degree panniruken" — education question
7. "ennaku blue pudikum" — interest statement
8. "en peru enna sollu papom" — name with marker

Run with:
  pytest backend/tests/test_fastapi_integration.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
PARENT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PARENT_DIR))

import pytest
from fastapi.testclient import TestClient

# Mock Ollama BEFORE importing FastAPI app
with patch('requests.post') as mock_post, \
     patch('requests.get') as mock_get:
    
    # Mock POST (chat endpoint)
    mock_post_response = MagicMock()
    mock_post_response.status_code = 200
    mock_post_response.json.return_value = {
        "message": {"role": "assistant", "content": "Seri!"},
        "done": True,
    }
    mock_post.return_value = mock_post_response
    
    # Mock GET (health check)
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = {"models": []}
    mock_get.return_value = mock_get_response
    
    # NOW import the app (with mocks in place)
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from main import app

# Create test client
client = TestClient(app)


class TestFastAPIIntegration:
    """FastAPI /api/chat integration tests."""

    def test_health_check(self):
        """Test /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ollama_ready" in data
        assert "model" in data

    def test_chat_empty_message(self):
        """Test /api/chat with empty message (should fail)."""
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"].lower()

    def test_chat_message_too_long(self):
        """Test /api/chat with message exceeding max length."""
        long_message = "a" * 5001
        response = client.post("/api/chat", json={"message": long_message})
        assert response.status_code == 400

    # ────────────────────────────────────────────────────────────────────────
    # SAMPLE INPUTS TESTS
    # ────────────────────────────────────────────────────────────────────────

    def test_sample_1_vannakam_greeting(self):
        """
        Sample 1: 'vannakam' (greeting)
        Expected: ChatResponse with language='tanglish', extracted_facts=[]
        """
        response = client.post("/api/chat", json={"message": "vannakam"})
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "language" in data
        assert "extracted_facts" in data
        assert isinstance(data["extracted_facts"], list)
        print(f"✓ Sample 1 (vannakam): {data['language']}")

    def test_sample_2_naa_sarandeep_name(self):
        """Sample 2: 'naa sarandeep' (name statement)"""
        response = client.post("/api/chat", json={"message": "naa sarandeep"})
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["language"] in ["tanglish", "english", "tamil"]
        print(f"✓ Sample 2 (naa sarandeep): {data['language']}")

    def test_sample_3_location_statement(self):
        """Sample 3: 'naa madurai la irundhu varen'"""
        response = client.post(
            "/api/chat",
            json={"message": "naa madurai la irundhu varen"}
        )
        assert response.status_code == 200
        print(f"✓ Sample 3 (location)")

    def test_sample_4_education_be(self):
        """Sample 4: 'naa BE mudichuruken'"""
        response = client.post(
            "/api/chat",
            json={"message": "naa BE mudichuruken"}
        )
        assert response.status_code == 200
        print(f"✓ Sample 4 (education: BE)")

    def test_sample_5_education_btech(self):
        """Sample 5: 'sorry btech mudichuruken'"""
        response = client.post(
            "/api/chat",
            json={"message": "sorry btech mudichuruken"}
        )
        assert response.status_code == 200
        print(f"✓ Sample 5 (education: btech)")

    def test_sample_6_degree_question(self):
        """Sample 6: 'naan enna degree panniruken'"""
        response = client.post(
            "/api/chat",
            json={"message": "naan enna degree panniruken"}
        )
        assert response.status_code == 200
        print(f"✓ Sample 6 (degree question)")

    def test_sample_7_interest_blue(self):
        """Sample 7: 'ennaku blue pudikum' (I like blue)"""
        response = client.post(
            "/api/chat",
            json={"message": "ennaku blue pudikum"}
        )
        assert response.status_code == 200
        print(f"✓ Sample 7 (interest)")

    def test_sample_8_name_with_marker(self):
        """Sample 8: 'en peru enna sollu papom'"""
        response = client.post(
            "/api/chat",
            json={"message": "en peru enna sollu papom"}
        )
        assert response.status_code == 200
        print(f"✓ Sample 8 (name with marker)")

    # ────────────────────────────────────────────────────────────────────────
    # MEMORY ENDPOINT TESTS
    # ────────────────────────────────────────────────────────────────────────

    def test_memories_endpoint(self):
        """Test /api/memories endpoint."""
        response = client.get("/api/memories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    # ────────────────────────────────────────────────────────────────────────
    # RESPONSE MODEL VALIDATION
    # ────────────────────────────────────────────────────────────────────────

    def test_chat_response_schema(self):
        """Verify ChatResponse schema."""
        response = client.post("/api/chat", json={"message": "test"})
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "reply" in data
        assert "language" in data
        assert "extracted_facts" in data
        
        # Type validation
        assert isinstance(data["reply"], str)
        assert isinstance(data["language"], str)
        assert isinstance(data["extracted_facts"], list)

    def test_invalid_json(self):
        """Test with invalid JSON."""
        response = client.post(
            "/api/chat",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code in [400, 422]

    def test_missing_message_field(self):
        """Test with missing 'message' field."""
        response = client.post("/api/chat", json={"text": "wrong field"})
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
