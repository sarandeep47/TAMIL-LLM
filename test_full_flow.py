#!/usr/bin/env python3
"""Test full flow: message → extraction → acknowledgment."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from memory_db import initialize_database, list_memories, forget_memory, get_memory
from chatbot import ask_ollama, save_chat
from chat_memory import acknowledge_statement
from fact_extractor import extract_facts

# Clear memories
initialize_database()
for mem in list_memories():
    forget_memory(mem['key'])

print("=" * 70)
print("FULL FLOW TEST: Message → Extraction → Acknowledgment")
print("=" * 70)

test_cases = [
    ("en peru Sarandeep", "user_name"),
    ("naa Madurai la iruken", "user_location"),
    ("naa KLNCE college la padichen", "user_school"),
]

for msg, expected_key in test_cases:
    print(f"\n{'-'*70}")
    print(f"Test: {msg}")
    print(f"Expected: {expected_key}")
    print(f"{'-'*70}")
    
    # Clear previous memories
    for mem in list_memories():
        forget_memory(mem['key'])
    
    # Simulate backend flow:
    # 1. Extract facts
    extracted = extract_facts(msg)
    print(f"Extracted {len(extracted)} facts:")
    for f in extracted:
        print(f"  - {f.key} = {f.value}")
    
    # 2. Call ask_ollama
    response = ask_ollama(msg)
    print(f"Response: {response[:80]}..." if len(response) > 80 else f"Response: {response}")
    
    # 3. Save chat history
    save_chat("user", msg)
    save_chat("assistant", response)
    
    # Check if fact was saved
    saved_value = get_memory(expected_key)
    if saved_value:
        print(f"✅ Fact saved: {expected_key} = {saved_value}")
    else:
        print(f"❌ Fact NOT saved for {expected_key}")
    
    # Try to get acknowledgment now that fact is saved
    ack = acknowledge_statement(msg)
    if ack:
        print(f"✅ Acknowledgment: {ack}")
    else:
        print(f"⚠️ No acknowledgment (expected if fact not saved)")
