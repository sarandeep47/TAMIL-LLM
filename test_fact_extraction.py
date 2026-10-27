#!/usr/bin/env python3
"""Test fact extraction integration."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from memory_db import initialize_database, list_memories, forget_memory
from fact_extractor import extract_facts

# Clear all existing memories
initialize_database()
for mem in list_memories():
    forget_memory(mem['key'])

test_messages = [
    "en peru Sarandeep",
    "naa Madurai la iruken",
    "naa KLNCE college la padichen",
]

for msg in test_messages:
    print(f"\nMessage: {msg}")
    
    # Try extract_facts
    extracted = extract_facts(msg)
    
    print(f"  extract_facts() returned {len(extracted)} fact(s)")
    for fact in extracted:
        print(f"    - {fact.key} = {fact.value} (conf={fact.confidence:.2f}, source={fact.source})")
    
    # Check what's in memory
    print(f"  Current memories:")
    for mem in list_memories():
        print(f"    - {mem['key']} = {mem['value']}")
