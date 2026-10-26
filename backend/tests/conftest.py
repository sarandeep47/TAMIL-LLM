"""
Pytest configuration for backend tests.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

@pytest.fixture
def client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    from backend.main import app
    
    return TestClient(app)
