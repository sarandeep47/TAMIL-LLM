#!/usr/bin/env python3
"""Debug tanglish extraction fallback."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tanglish_understanding import understand_tanglish
from fact_extractor import _looks_like_personal_statement

msg = "naa Madurai la iruken"

print(f"Message: {msg}")
print()

# Check if it's a personal statement
is_stmt = _looks_like_personal_statement(msg)
print(f"_looks_like_personal_statement() = {is_stmt}")

# Check tanglish understanding
intent = understand_tanglish(msg)
print(f"\nTanglishIntent:")
print(f"  sentence_type = {intent.sentence_type}")
print(f"  topic = {intent.topic}")
print(f"  is_personal_fact() = {intent.is_personal_fact()}")
print(f"  confidence = {intent.confidence}")
print(f"  memory_key = {intent.memory_key}")
print(f"  entities = {intent.entities}")

# Check conditions
print(f"\nConditions for extraction:")
print(f"  statement? {intent.sentence_type == 'statement'}")
print(f"  personal fact? {intent.is_personal_fact()}")
print(f"  high confidence? {intent.confidence >= 0.7}")
print(f"  has memory_key? {intent.memory_key is not None}")
print(f"  has entity value? {intent.entities.get('value') is not None}")
