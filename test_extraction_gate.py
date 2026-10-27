#!/usr/bin/env python3
"""Quick test of the extraction gate."""
from fact_extractor import _looks_like_personal_statement

# Test the extraction gate with all problematic messages from the summary
test_cases = [
    ('vannakam', False),  # Greeting
    ('en peru Sarandeep', True),  # Statement - should extract
    ('naa Madurai la iruken', True),  # Statement - should extract  
    ('naa enga iruken', False),  # Question - should NOT extract
    ('naa enna padichen nu sollu', False),  # Recall - should NOT extract
    ('naa enga college la padichen', False),  # Question - should NOT extract
    ('Which degree have I completed', False),  # Question - should NOT extract
]

print('EXTRACTION GATE TEST:')
all_pass = True
for msg, expected in test_cases:
    result = _looks_like_personal_statement(msg)
    status = '✓' if result == expected else '✗'
    if result != expected:
        all_pass = False
    print(f'{status} "{msg}" -> {result} (expected {expected})')

print(f'\nResult: {"ALL PASS" if all_pass else "SOME FAILED"}')
