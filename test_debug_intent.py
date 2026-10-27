#!/usr/bin/env python3
"""Debug intent detection."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from chat_memory import _detect_statement_intent, acknowledge_statement, detect_language_style
from tanglish_understanding import understand_tanglish

test_messages = [
    "en peru Sarandeep",
    "naa Madurai la iruken",
    "naa KLNCE college la padichen",
    "na Madurai la iruken",
]

for msg in test_messages:
    print(f"\n{'='*70}")
    print(f"Message: {msg}")
    print(f"{'='*70}")
    
    # Tanglish understanding
    intent = understand_tanglish(msg)
    print(f"TanglishIntent:")
    print(f"  type={intent.sentence_type}, topic={intent.topic}")
    print(f"  operation={intent.operation}, confidence={intent.confidence:.2f}")
    print(f"  memory_key={intent.memory_key}")
    
    # Statement detection
    stmt_intent = _detect_statement_intent(msg)
    print(f"\n_detect_statement_intent() → {stmt_intent}")
    
    # Try acknowledgment (without pre-saved values)
    ack = acknowledge_statement(msg)
    print(f"acknowledge_statement() → {ack}")
