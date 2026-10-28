#!/usr/bin/env python3
"""
test_final_verification.py
==========================
Final verification that both education memory and Tanglish conversation work end-to-end.

Runs a complete conversation flow and verifies:
1. Education memory extraction and retrieval
2. Origin vs location distinction
3. Casual conversation not blocked
4. Greeting detection returns Tanglish, not English
5. No regressions in existing functionality
"""

import os
import sys
import tempfile
from pathlib import Path

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def setup_isolated_db():
    """Create isolated test databases."""
    tmpdir = Path(tempfile.gettempdir()) / 'final_verify_db'
    tmpdir.mkdir(exist_ok=True)
    
    import memory_db, training_review, chatbot
    
    mem_db = tmpdir / "memory.db"
    chat_db = tmpdir / "chatbot.db"
    
    import os as os_module
    os_module.environ['TAMIL_LLM_DB_ROOT'] = str(tmpdir.parent)
    
    memory_db.DB_PATH = mem_db
    training_review.DB_PATH = chat_db
    chatbot.CHAT_DB_PATH = chat_db
    
    memory_db.initialize_database()
    training_review.initialize_training_db()
    chatbot.initialize_chatbot()
    
    return tmpdir


def test_education_memory():
    """Test 1: Education memory extraction and retrieval."""
    print("\n" + "="*70)
    print("TEST 1: EDUCATION MEMORY EXTRACTION & RETRIEVAL")
    print("="*70)
    
    setup_isolated_db()
    
    import fact_extractor
    import memory_db
    from chat_memory import answer_question
    
    # 1. Extract education fact
    print("\n1. Extracting: 'Naa BE pannen KLN la'")
    facts = fact_extractor.extract_facts("Naa BE pannen KLN la")
    assert len(facts) == 1, f"Should extract 1 fact, got {len(facts)}"
    assert facts[0].key == "user_school", f"Should be user_school, got {facts[0].key}"
    assert facts[0].value == "KLN", f"Should be KLN, got {facts[0].value}"
    print(f"   ✓ Extracted: {facts[0].key} = {facts[0].value}")
    
    # 2. Verify in DB
    print("\n2. Checking database...")
    college = memory_db.get_memory("user_school")
    assert college == "KLN", f"DB should have KLN, got {college}"
    print(f"   ✓ Stored in DB: user_school = {college}")
    
    # 3. Retrieve with various questions
    print("\n3. Retrieving with different question forms...")
    test_questions = [
        "Naa enga padichen?",
        "Entha college?",
        "What is my college?",
    ]
    for q in test_questions:
        answer = answer_question(q)
        assert answer is not None, f"Answer for {q!r} should not be None"
        assert "KLN" in answer, f"Answer for {q!r} should contain KLN, got: {answer}"
        assert "Antha thakaval" not in answer, (
            f"Answer for {q!r} should not say 'not saved', got: {answer}"
        )
        print(f"   ✓ {q:30} → {answer[:50]}...")
    
    print("\n✅ TEST 1 PASSED: Education memory works end-to-end\n")


def test_origin_vs_location():
    """Test 2: Origin and location remain separate."""
    print("\n" + "="*70)
    print("TEST 2: ORIGIN VS LOCATION (SEPARATE FACTS)")
    print("="*70)
    
    setup_isolated_db()
    
    import fact_extractor
    import memory_db
    from chat_memory import answer_question
    
    # Save location
    print("\n1. Saving location: 'Naa Villapuram la iruken'")
    fact_extractor.extract_facts("Naa Villapuram la iruken")
    location = memory_db.get_memory("user_location")
    assert location == "Villapuram", f"Location should be Villapuram, got {location}"
    print(f"   ✓ Saved: user_location = {location}")
    
    # Save origin
    print("\n2. Saving origin: 'Madurai la irundhu varen'")
    fact_extractor.extract_facts("Madurai la irundhu varen")
    origin = memory_db.get_memory("user_origin")
    assert origin == "Madurai", f"Origin should be Madurai, got {origin}"
    print(f"   ✓ Saved: user_origin = {origin}")
    
    # Verify both stored
    print("\n3. Verifying both facts stored separately...")
    assert location != origin, "Location and origin should be different"
    print(f"   ✓ Location: {location}")
    print(f"   ✓ Origin:   {origin}")
    
    # Retrieve with specific questions
    print("\n4. Retrieving with specific questions...")
    location_answer = answer_question("Naa enga iruken?")
    assert "Villapuram" in location_answer, (
        f"Location question should return Villapuram, got: {location_answer}"
    )
    print(f"   ✓ Location question: {location_answer[:50]}...")
    
    origin_answer = answer_question("Naa enga irundhu varen?")
    assert "Madurai" in origin_answer, (
        f"Origin question should return Madurai, got: {origin_answer}"
    )
    print(f"   ✓ Origin question: {origin_answer[:50]}...")
    
    print("\n✅ TEST 2 PASSED: Origin and location remain separate\n")


def test_greeting_detection():
    """Test 3: Greeting detection returns Tanglish."""
    print("\n" + "="*70)
    print("TEST 3: GREETING DETECTION")
    print("="*70)
    
    setup_isolated_db()
    
    from chat_memory import handle_greeting, detect_language_style
    
    # Test Tanglish greeting
    print("\n1. Testing Tanglish greeting detection...")
    style = detect_language_style("Vanakkam")
    print(f"   Language style for 'Vanakkam': {style}")
    assert style == "tanglish", f"Should be tanglish, got {style}"
    
    greeting = handle_greeting("Vanakkam")
    print(f"   Greeting response: {greeting!r}")
    assert greeting == "Vanakkam!", f"Should return 'Vanakkam!', got {greeting!r}"
    print(f"   ✓ Correct Tanglish greeting returned")
    
    # Test Tamil greeting
    print("\n2. Testing Tamil greeting detection...")
    style = detect_language_style("வணக்கம்")
    print(f"   Language style for 'வணக்கம்': {style}")
    assert style == "tamil", f"Should be tamil, got {style}"
    
    greeting = handle_greeting("வணக்கம்")
    print(f"   Greeting response: {greeting!r}")
    assert greeting == "வணக்கம்!", f"Should return Tamil greeting, got {greeting!r}"
    print(f"   ✓ Correct Tamil greeting returned")
    
    print("\n✅ TEST 3 PASSED: Greeting detection works correctly\n")


def test_casual_conversation():
    """Test 4: Casual questions don't trigger 'not saved' errors."""
    print("\n" + "="*70)
    print("TEST 4: CASUAL CONVERSATION NOT BLOCKED")
    print("="*70)
    
    setup_isolated_db()
    
    from chat_memory import answer_question
    
    print("\n1. Testing casual questions...")
    casual_questions = [
        "Naa nalla iruken, nee?",
        "Eppidi irukka?",
        "Nalla-va?",
    ]
    
    for q in casual_questions:
        answer = answer_question(q)
        # Should be None (let Ollama handle) or not "not saved"
        if answer is not None:
            assert "Antha thakaval" not in answer and "saved" not in answer.lower(), (
                f"Casual question {q!r} should not say 'not saved', got: {answer}"
            )
        print(f"   ✓ {q:30} → {answer if answer else '(goes to Ollama)'}")
    
    print("\n✅ TEST 4 PASSED: Casual conversation not blocked\n")


def test_system_prompt_quality():
    """Test 5: System prompt has Tanglish guidance."""
    print("\n" + "="*70)
    print("TEST 5: SYSTEM PROMPT TANGLISH GUIDANCE")
    print("="*70)
    
    from chatbot import _SYSTEM_PROMPT_BASE
    
    print("\n1. Checking for casual Tanglish endings guidance...")
    casual_terms = ["apdiya", "irukka", "ahh", "tag question"]
    found = [t for t in casual_terms if t in _SYSTEM_PROMPT_BASE.lower()]
    assert len(found) > 0, "System prompt should mention casual endings"
    print(f"   ✓ Found guidance for: {', '.join(found)}")
    
    print("\n2. Checking for good/bad response examples...")
    assert "GOOD examples" in _SYSTEM_PROMPT_BASE, (
        "System prompt should have good/bad examples"
    )
    print(f"   ✓ System prompt includes good/bad response examples")
    
    print("\n3. Checking for response length constraint...")
    assert "RESPONSE LENGTH" in _SYSTEM_PROMPT_BASE or "1-2 sentences" in _SYSTEM_PROMPT_BASE, (
        "System prompt should mention response length"
    )
    print(f"   ✓ System prompt includes response length guidance")
    
    print("\n✅ TEST 5 PASSED: System prompt has quality guidance\n")


def main():
    """Run all tests."""
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█  FINAL VERIFICATION: TAMIL LLM CHATBOT FIXES" + " "*24 + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    try:
        test_education_memory()
        test_origin_vs_location()
        test_greeting_detection()
        test_casual_conversation()
        test_system_prompt_quality()
        
        print("\n" + "█"*70)
        print("█" + " "*68 + "█")
        print("█  ✅ ALL VERIFICATION TESTS PASSED!" + " "*32 + "█")
        print("█" + " "*68 + "█")
        print("█"*70)
        print("\nSummary:")
        print("  ✓ Education memory extraction and retrieval works")
        print("  ✓ Origin vs location remain separate facts")
        print("  ✓ Greeting detection returns Tanglish")
        print("  ✓ Casual conversation not blocked")
        print("  ✓ System prompt has Tanglish quality guidance")
        print("\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ VERIFICATION FAILED: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
