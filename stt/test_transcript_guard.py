#!/usr/bin/env python3
"""Test transcript guard echo and loop detection."""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stt.transcript_guard import check_transcript


def test_echo():
    """Echo: 3+ words from hint list."""
    text = "வணக்கம், நன்றி, கேப், கார், இருக்கிறது"
    result = check_transcript(text)
    assert result == "echo", f"Expected 'echo', got '{result}'"
    print("✓ echo test passed")


def test_loop():
    """Loop: word appears 4+ times or bigram 3+ times."""
    text = "நன்றி பொருத்தம் நன்றி பொருத்தம் நன்றி பொருத்தம்"  # நன்றி appears 3 times, "நன்றி பொருத்தம்" appears 3 times
    result = check_transcript(text)
    assert result == "loop", f"Expected 'loop', got '{result}'"
    print("✓ loop test passed")


def test_ok_single():
    """Single hint word is ok."""
    text = "வணக்கம்"
    result = check_transcript(text)
    assert result == "ok", f"Expected 'ok', got '{result}'"
    print("✓ ok (single word) test passed")


def test_ok_two_hints():
    """Two hint words are ok."""
    text = "வணக்கம் நன்றி"
    result = check_transcript(text)
    assert result == "ok", f"Expected 'ok', got '{result}'"
    print("✓ ok (two hints) test passed")


def test_ok_normal():
    """Normal Tamil sentence is ok."""
    text = "நான் அண்ணா நகர்ல இருக்கேன்"
    result = check_transcript(text)
    assert result == "ok", f"Expected 'ok', got '{result}'"
    print("✓ ok (normal sentence 1) test passed")


def test_ok_normal_2():
    """Normal Tamil sentence is ok."""
    text = "எனக்கு ஒரு கேப் வேணும்"
    result = check_transcript(text)
    assert result == "ok", f"Expected 'ok', got '{result}'"
    print("✓ ok (normal sentence 2) test passed")


if __name__ == "__main__":
    test_echo()
    test_loop()
    test_ok_single()
    test_ok_two_hints()
    test_ok_normal()
    test_ok_normal_2()
    print("\n6/6 tests passed!")
