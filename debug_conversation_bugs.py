#!/usr/bin/env python
"""
Debug script to trace the four bugs through the current routing logic.
"""

import sys
import os
from pathlib import Path

_ROOT = str(Path(__file__).parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import tempfile
import shutil

def debug_routing():
    temp_dir = tempfile.mkdtemp(prefix="debug_chat_")
    mem_db = Path(temp_dir) / "memory.db"
    chat_db = Path(temp_dir) / "chatbot.db"
    
    try:
        import memory_db
        import training_review
        import chatbot
        import fact_extractor
        from chat_memory import (
            detect_language_style, 
            detect_intent,
            is_personal_history_question,
            answer_question,
            handle_greeting
        )
        from tanglish_understanding import understand_tanglish
        
        memory_db.DB_PATH = mem_db
        training_review.DB_PATH = chat_db
        chatbot.CHAT_DB_PATH = chat_db
        
        memory_db.initialize_database()
        training_review.initialize_training_db()
        chatbot.initialize_chatbot()
        
        print("=" * 80)
        print("DEBUGGING CONVERSATION ROUTING")
        print("=" * 80)
        
        test_messages = [
            ("Vanakkam", "greeting"),
            ("Naa Sarandeep", "name statement"),
            ("Naa nalla iruken, nee?", "casual question - BUG 1"),
            ("Naa Madurai la irundhu varen", "origin statement"),
            ("Villapuram", "short clarification"),
            ("Naa BE pannen KLN la", "college statement"),
            ("AI automation", "general topic"),
            ("Naa enga irundhu varen?", "direct origin question"),
            ("Naa enga padichen?", "direct college question - BUG 3"),
        ]
        
        for msg, description in test_messages:
            print(f"\n{'-' * 80}")
            print(f"Message: '{msg}'")
            print(f"Description: {description}")
            print(f"{'-' * 80}")
            
            # Run all detection functions
            greeting = handle_greeting(msg)
            language_style = detect_language_style(msg)
            detect_intent_result = detect_intent(msg)
            is_personal_hist = is_personal_history_question(msg)
            tanglish_intent = understand_tanglish(msg)
            
            # Check what answer_question returns
            answer = answer_question(msg)
            
            print(f"Language style: {language_style}")
            print(f"Greeting: {greeting}")
            print(f"detect_intent(): {detect_intent_result}")
            print(f"is_personal_history_question(): {is_personal_hist}")
            print(f"answer_question(): {answer}")
            print(f"Tanglish intent type: {tanglish_intent.sentence_type}")
            print(f"Tanglish memory_key: {tanglish_intent.memory_key}")
            print(f"Tanglish confidence: {tanglish_intent.confidence}")
            
            # Extract facts
            facts = fact_extractor._extract_by_regex(msg)
            if facts:
                for f in facts:
                    print(f"Fact extracted: {f.key} = {f.value}")
                    memory_db.save_memory(f.key, f.value, category=f.category, 
                                         confidence=f.confidence, source=f.source)
            
            # Trace routing decision
            print("\nRouting decision:")
            if greeting:
                print(f"  -> GREETING: return '{greeting}'")
            elif answer:
                print(f"  -> MEMORY QUESTION: return '{answer}'")
            else:
                print(f"  -> OLLAMA: call LLM with message")
            
        print("\n" + "=" * 80)
        print("MEMORY STATE AT END")
        print("=" * 80)
        memories = memory_db.list_memories()
        for m in memories:
            print(f"{m['key']:30} = {m['value']}")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    debug_routing()
