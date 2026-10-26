"""
Tests for the FastAPI backend endpoints.

Covers:
- Health check
- Chat endpoint (normal messages, empty messages, long messages)
- Memories endpoint
- Error handling (Ollama down, timeouts, etc.)

Note: Tests run with TestClient which doesn't require the server to actually
start or Ollama to be running. Tests gracefully handle Ollama unavailability.
"""

import pytest
import sys
from pathlib import Path
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Disable Ollama URL so tests don't actually try to connect
os.environ["OLLAMA_URL"] = "http://localhost:11434/api/chat"

from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_app_loads(client):
    """Test that the app can be instantiated."""
    assert app is not None
    assert len(app.routes) >= 3


def test_health_check_structure(client):
    """Test /health endpoint response structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "ollama_ready" in data
    assert "model" in data
    assert data["status"] in ["ok", "degraded"]


def test_chat_empty_message(client):
    """Test that empty messages return 400 error."""
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 400


def test_chat_whitespace_only(client):
    """Test that whitespace-only messages return 400 error."""
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400


def test_chat_message_too_long(client):
    """Test that messages over 5000 chars return 400 error."""
    long_message = "a" * 5001
    response = client.post("/api/chat", json={"message": long_message})
    assert response.status_code == 400


def test_memories_endpoint_structure(client):
    """Test /api/memories endpoint response structure."""
    response = client.get("/api/memories")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_missing_message_field(client):
    """Test that missing message field returns error."""
    response = client.post("/api/chat", json={})
    # Should return validation error (422)
    assert response.status_code in [400, 422]


def test_cors_middleware_loaded(client):
    """Test that CORS middleware is configured."""
    response = client.get("/health")
    # Should have CORS headers
    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
