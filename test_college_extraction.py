#!/usr/bin/env python
"""Test college extraction for 'Naa BE pannen KLN la'"""

import sys, re, tempfile, shutil
from pathlib import Path

_ROOT = str(Path('.').absolute())
sys.path.insert(0, _ROOT)

msg = 'Naa BE pannen KLN la'
print(f'Message: {msg}')

# Debug the pattern carefully
print('\n=== Testing pattern variants ===')

# Original pattern from our fix
pattern1 = re.compile(
    r'(?:naa|naan)\s+(?:[A-Z]{2,}|[A-Z][A-Za-z]*)\s+pannen\s+(?=[A-Z])([A-Za-z][\w\s.,\-]{2,}?)(?:\s+(?:la|il|le))?(?:[.!,]|$)'
)
m = pattern1.search(msg)
print(f'Pattern 1 (uppercase): {m.group(1) if m else "NO MATCH"}')

# Try case-insensitive
pattern2 = re.compile(
    r'(?:naa|naan)\s+(?:[A-Z]{2,}|[A-Z][A-Za-z]*)\s+pannen\s+(?=[A-Z])([A-Za-z][\w\s.,\-]{2,}?)(?:\s+(?:la|il|le))?(?:[.!,]|$)',
    re.IGNORECASE
)
m = pattern2.search(msg)
print(f'Pattern 2 (case-insensitive): {m.group(1) if m else "NO MATCH"}')

# Simplified pattern - just test the pannen part
pattern3 = re.compile(r'pannen\s+([A-Z][A-Za-z]*)')
m = pattern3.search(msg)
print(f'Pattern 3 (simplified): {m.group(1) if m else "NO MATCH"}')

# Test matching the degrees
pattern4 = re.compile(r'(?:naa|naan)\s+([A-Z]{2,}|[A-Z][A-Za-z]*)\s+pannen')
m = pattern4.search(msg)
print(f'Pattern 4 (get degree): {m.group(1) if m else "NO MATCH"}')

# The issue might be that we need to get KLN which comes AFTER pannen
# Let's check if the lookahead (?=[A-Z]) is the issue
pattern5 = re.compile(r'pannen\s+([A-Za-z][\w\s.,\-]{2,}?)(?:\s+(?:la|il|le))?(?:[.!,]|$)')
m = pattern5.search(msg)
print(f'Pattern 5 (no lookahead): {m.group(1) if m else "NO MATCH"}')

# Check what the actual KLN la matches
pattern6 = re.compile(r'([A-Za-z][\w\s.,\-]{2,}?)\s+(?:la|il|le)(?:[.!,]|$)')
m = pattern6.search('KLN la')
print(f'Pattern 6 (KLN capture): {m.group(1) if m else "NO MATCH"}')

