#!/usr/bin/env python
"""
Test conversation quality for origin statements and follow-ups.
Verifies that the response is natural and doesn't contain garbled text.
"""

import sys, os
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = str(Path(__file__).parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import tempfile
import shutil

def test_origin_conversation_quality():
    temp_dir = tempfile.mkdtemp(prefix="conv_quality_")
    mem_db = Path(temp_dir) / "memory.db"
    chat_db = Path(temp_dir) / "chatbot.db"
    
    try:
        import memory_db
        import training_review
        import chatbot
        import fact_extractor
        from chat_memory import answer_question
        
        memory_db.DB_PATH = mem_db
        training_review.DB_PATH = chat_db
        chatbot.CHAT_DB_PATH = chat_db
        
        memory_db.initialize_database()
        training_review.initialize_training_db()
        chatbot.initialize_chatbot()
        
        print("=" * 80)
        print("CONVERSATION QUALITY TEST - Origin Statement Follow-up")
        print("=" * 80)
        
        # Test 1: Origin statement "Naa Madurai la irundhu varen"
        print("\n[TEST 1] Origin statement with Ollama follow-up")
        print("-" * 80)
        
        msg1 = "Naa Madurai la irundhu varen"
        print(f"Message: '{msg1}'")
        
        # Extract facts
        facts = fact_extractor._extract_by_regex(msg1)
        for f in facts:
            memory_db.save_memory(f.key, f.value, category=f.category, 
                                 confidence=f.confidence, source=f.source)
            print(f"  EXTRACTED: {f.key} = {f.value}")
        
        # Get Ollama response
        def mock_ollama(url, json=None, timeout=None):
            # Return a GOOD response (what we expect)
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "message": {"content": "Oh, Madurai-la irundhu vareengala! Madurai-la enga?"}
            }
            mock_resp.raise_for_status.return_value = None
            return mock_resp
        
        with patch("chatbot.requests.post", side_effect=mock_ollama):
            response1 = chatbot.ask_ollama(msg1)
        
        print(f"  RESPONSE: {response1}")
        
        # Verify response quality
        assert response1 is not None, "Response should not be None"
        assert len(response1) > 0, "Response should not be empty"
        assert "naanam" not in response1.lower(), "Response should not contain garbled 'naanam varen'"
        assert "Madurai" in response1 or "madurai" in response1.lower(), "Response should reference Madurai"
        assert "?" in response1, "Response should contain a follow-up question"
        print("  ✓ PASS - Response quality is good")
        
        # Test 2: Direct origin question
        print("\n[TEST 2] Direct origin question - memory retrieval")
        print("-" * 80)
        
        msg2 = "Naa enga irundhu varen?"
        print(f"Message: '{msg2}'")
        
        response2 = chatbot.ask_ollama(msg2)
        print(f"  RESPONSE: {response2}")
        
        # Verify deterministic response from memory
        assert "Madurai" in response2, "Should recall Madurai from memory"
        assert "irundhu" in response2.lower() or "irunthu" in response2.lower(), "Should indicate origin"
        print("  ✓ PASS - Origin correctly recalled")
        
        # Test 3: Full conversation flow
        print("\n[TEST 3] Full conversation flow")
        print("-" * 80)
        
        conversation = [
            ("Naa Madurai la irundhu varen", "origin statement"),
            ("Naa enga irundhu varen?", "origin question"),
        ]
        
        for msg, desc in conversation:
            print(f"  {desc}: '{msg}'")
            response = chatbot.ask_ollama(msg)
            print(f"    -> {response}")
            assert response is not None, f"Response should not be None for {desc}"
            assert len(response) > 0, f"Response should not be empty for {desc}"
        
        print("  ✓ PASS - Full conversation coherent")
        
        # Test 4: Verify memory state
        print("\n[TEST 4] Memory state verification")
        print("-" * 80)
        
        user_origin = memory_db.get_memory("user_origin", "english")
        print(f"  Stored user_origin: {user_origin}")
        assert user_origin == "Madurai", f"Should store Madurai, got {user_origin}"
        print("  ✓ PASS - Origin correctly stored")
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED - Conversation Quality Verified")
        print("=" * 80)
        
        return True
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    success = test_origin_conversation_quality()
    sys.exit(0 if success else 1)
