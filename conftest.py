"""
conftest.py — project-wide pytest configuration.

Registers custom marks so they don't produce PytestUnknownMarkWarning.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "manual: marks tests as requiring a live Ollama instance or manual setup "
        "(deselect with: -m 'not manual')",
    )
