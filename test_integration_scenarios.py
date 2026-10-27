#!/usr/bin/env python3
"""
Integration tests for tanglish_understanding layer with live chatbot flow.

Tests the real scenarios through ask_ollama → memory_db → response path.
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from chatbot import ask_ollama
from memory_db import initialize_database, save_memory, forget_memory, get_memory, list_memories
from chat_memory import (
    detect_intent, acknowledge_statement, answer_question,
    is_personal_history_question, detect_language_style
)
from tanglish_understanding import understand_tanglish

# Initialize
initialize_database()

# Clear all existing memories
for mem in list_memories():
    forget_memory(mem['key'])

print("=" * 70)
print("INTEGRATION TEST: Tanglish Understanding Layer with Live Chatbot")
print("=" * 70)

# Test counter
tests_passed = 0
tests_failed = 0

def test_scenario(name: str, message: str, expected_intent: str | None = None, 
                  should_save: bool = False, should_retrieve: bool = False,
                  pre_save_key: str | None = None, pre_save_value: str | None = None):
    """Test a single scenario through the live chatbot."""
    global tests_passed, tests_failed
    
    print(f"\n{name}")
    print(f"  Input: \"{message}\"")
    
    # Pre-save if needed
    if pre_save_key and pre_save_value:
        save_memory(pre_save_key, pre_save_value, category="test", source="manual")
        print(f"  [Setup: Saved {pre_save_key}={pre_save_value}]")
    
    # Test tanglish understanding
    intent = understand_tanglish(message)
    print(f"  Intent: type={intent.sentence_type}, topic={intent.topic}, "
          f"op={intent.operation}, conf={intent.confidence:.2f}")
    
    # Test memory operations
    det_intent = detect_intent(message)
    ack_stmt = acknowledge_statement(message)
    ans_quest = answer_question(message)
    
    print(f"  Memory ops: intent={det_intent}, ack_stmt={ack_stmt is not None}, "
          f"ans_quest={ans_quest is not None}")
    
    # Test full response
    response = ask_ollama(message)
    print(f"  Response: {response[:80]}..." if len(response) > 80 else f"  Response: {response}")
    
    # Verify expectations
    success = True
    if expected_intent and det_intent != expected_intent:
        print(f"  ❌ Expected intent {expected_intent}, got {det_intent}")
        success = False
    
    if should_save and ack_stmt is None:
        print(f"  ❌ Expected acknowledgment, got None")
        success = False
    
    if should_retrieve and ans_quest is None:
        print(f"  ❌ Expected answer, got None")
        success = False
    
    if success:
        tests_passed += 1
        print(f"  ✅ PASS")
    else:
        tests_failed += 1
        print(f"  ❌ FAIL")
    
    return response


def clear_all_memories():
    """Clear all saved memories."""
    for mem in list_memories():
        forget_memory(mem['key'])


# ─────────────────────────────────────────────────────────────────────────────
# Test Scenarios from Requirements
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "─" * 70)
print("TEST SET 1: NAME STATEMENTS AND QUESTIONS")
print("─" * 70)

test_scenario(
    "1a. Save name statement",
    "en peru Sarandeep",
    expected_intent="user_name",
    should_save=True
)

test_scenario(
    "1b. Retrieve name question",
    "en peru enna?",
    expected_intent="user_name",
    should_retrieve=True,
    pre_save_key="user_name",
    pre_save_value="Sarandeep"
)

print("\n" + "─" * 70)
print("TEST SET 2: LOCATION STATEMENTS AND QUESTIONS")
print("─" * 70)

clear_all_memories()

test_scenario(
    "2a. Save location statement",
    "naa Madurai la iruken",
    expected_intent="user_location",
    should_save=True
)

test_scenario(
    "2b. Retrieve location question",
    "naa enga iruken?",
    expected_intent="user_location",
    should_retrieve=True,
    pre_save_key="user_location",
    pre_save_value="Madurai"
)

test_scenario(
    "2c. Recall pattern (explicit memory request)",
    "naa enga iruken nu sonnen",
    should_retrieve=True,
    pre_save_key="user_location",
    pre_save_value="Madurai"
)

print("\n" + "─" * 70)
print("TEST SET 3: EDUCATION (FIELD OF STUDY VS SCHOOL)")
print("─" * 70)

clear_all_memories()

test_scenario(
    "3a. Save field of study (no college keyword)",
    "naa cse padichen college la",
    expected_intent="user_field_of_study",
    should_save=True
)

test_scenario(
    "3b. Retrieve field of study question",
    "naa enna padichen nu sollu",
    should_retrieve=True,
    pre_save_key="user_field_of_study",
    pre_save_value="CSE"
)

clear_all_memories()

test_scenario(
    "3c. Save school (with college keyword and institution name)",
    "naa KLNCE college la padichen",
    expected_intent="user_school",
    should_save=True
)

test_scenario(
    "3d. Retrieve school question",
    "naa enga college la padichen?",
    expected_intent="user_school",
    should_retrieve=True,
    pre_save_key="user_school",
    pre_save_value="KLNCE"
)

print("\n" + "─" * 70)
print("TEST SET 4: GENERAL GREETINGS AND KNOWLEDGE QUESTIONS")
print("─" * 70)

test_scenario(
    "4a. Greeting (should go to Ollama, not memory)",
    "Vanakkam",
    should_retrieve=False
)

test_scenario(
    "4b. General knowledge (should go to Ollama, not memory)",
    "Tell me about Python",
    should_retrieve=False
)

test_scenario(
    "4c. General question about programming",
    "What is machine learning?",
    should_retrieve=False
)

print("\n" + "─" * 70)
print("TEST SET 5: EDGE CASES AND TYPO TOLERANCE")
print("─" * 70)

clear_all_memories()

# Variant spelling tests
test_scenario(
    "5a. Tanglish variant: 'na' instead of 'naa'",
    "na Madurai la iruken",
    should_save=True
)

clear_all_memories()

test_scenario(
    "5b. Tanglish variant: 'ile' instead of 'la'",
    "naa Madurai ile iruken",
    should_save=True
)

test_scenario(
    "5c. Question about unknown fact (should return 'not saved')",
    "naa enga iruken?",
    should_retrieve=True,
    pre_save_key=None,  # Don't pre-save anything
    pre_save_value=None
)

print("\n" + "─" * 70)
print("TEST SUMMARY")
print("─" * 70)
print(f"\n✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")
print(f"📊 Total:  {tests_passed + tests_failed}")
print(f"📈 Success Rate: {100 * tests_passed / (tests_passed + tests_failed):.1f}%\n")

# Exit code
sys.exit(0 if tests_failed == 0 else 1)
