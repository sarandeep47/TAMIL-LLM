#!/usr/bin/env python3
"""
Test router.py: 35 cases.
"""
from router import route_message

CASES = [
    # greeting
    ("vanakam", "greeting"),
    ("Vanakkam!", "greeting"),
    ("வணக்கம்", "greeting"),
    ("வணக்கம். வணக்கம்.", "greeting"),
    ("Hello", "greeting"),
    ("hi", "greeting"),
    
    # how_are_you
    ("epdi irukinga", "how_are_you"),
    ("eppadi irukeenga?", "how_are_you"),
    ("எப்படி இருக்கீங்க?", "how_are_you"),
    ("how are you", "how_are_you"),
    ("நீ எப்படி இருக்கீங்க?", "how_are_you"),
    
    # im_fine
    ("nalla iruken", "im_fine"),
    ("நான் நல்லா இருக்கேன்", "im_fine"),
    
    # thanks
    ("nandri", "thanks"),
    ("நன்றி", "thanks"),
    ("thank you", "thanks"),
    
    # what_doing
    ("enna panreenga", "what_doing"),
    ("என்ன பண்றீங்க?", "what_doing"),
    
    # cab_request
    ("கேப் புக் பண்ணனும்", "cab_request"),
    ("enakku oru cab venum", "cab_request"),
    ("vanakam enakku cab venum", "cab_request"),
    ("car book pannunga", "cab_request"),
    ("I need a taxi", "cab_request"),
    ("கார் வேணும்", "cab_request"),
    ("hi, i want cab", "cab_request"),
    ("can you call a cab please", "cab_request"),
    ("cab book pannunga", "cab_request"),
    
    # goodbye
    ("bye", "goodbye"),
    ("goodbye", "goodbye"),
    
    # ack
    ("சரி", "ack"),
    ("okay", "ack"),
    
    # MUST NOT be hijacked (None = go to LLM)
    ("Madurai la iruken", None),
    ("enna sonnenga?", None),
    ("my car is red", None),
    ("கார்த்திக் வீட்டுக்கு போகணும்", None),
    ("tamil nadu oda thalainagaram enna", None),
    ("", None),
]

passed = 0
failed = 0

for text, expected_intent in CASES:
    result = route_message(text)
    got_intent = result["intent"] if result else None
    is_pass = (got_intent == expected_intent)
    
    if is_pass:
        passed += 1
        print(f"PASS: {text!r:50} -> {got_intent}")
    else:
        failed += 1
        print(f"FAIL: {text!r:50} -> {got_intent} (expected {expected_intent})")

print(f"\n{passed}/{len(CASES)} passed")
exit(1 if failed else 0)
