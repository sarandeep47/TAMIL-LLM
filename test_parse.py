#!/usr/bin/env python3
r"""Test parsing functions for Tamil cab booking dialogue.
All strings are in \uXXXX escapes to avoid encoding issues.
This test file has an encoding check to ensure no non-ASCII bytes.
"""

import sys
import re

# Encoding check: ensure no non-ASCII characters in source
with open(__file__, 'rb') as f:
    content = f.read()
    if any(b > 127 for b in content):
        print("ERROR: test_parse.py contains non-ASCII characters")
        sys.exit(1)

# Also check dialogue_parse.py
try:
    with open('dialogue_parse.py', 'rb') as f:
        dp_content = f.read()
        if any(b > 127 for b in dp_content):
            print("ERROR: dialogue_parse.py contains non-ASCII characters")
            sys.exit(1)
except FileNotFoundError:
    print("ERROR: dialogue_parse.py not found")
    sys.exit(1)

from dialogue_parse import parse_places, parse_time, is_question, dat, loc


def test_places():
    """Test place parsing."""
    tests = [
        # (input, expected_pickup, expected_drop, expected_bare, expected_vague)
        ("naa chennai ponnum", None, "\u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8", None, False),  # Chennai
        ("kk nagar poganum", None, "\u0B95\u0BC7.\u0B95\u0BC7. \u0BA8\u0B95\u0BB0\u0BCD", None, False),  # KK Nagar
        ("naa trichy pognum", None, "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", None, False),  # Trichy
        ("thrichy la irundhu poganum", "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", None, None, False),  # Trichy
        ("Madurai la iruken", "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8", None, None, False),  # Madurai
        ("teppakulam poganum", None, "\u0BA4\u0BC6\u0BAA\u0BCD\u0BAA\u0B95\u0BCD\u0B95\u0BC1\u0BB3\u0BAE\u0BCD", None, False),  # Teppakulam
        ("airport ku poganum", None, "\u0BB5\u0BBF\u0BAE\u0BBE\u0BA9 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD", None, False),  # Airport
        ("madurai railway station ku poganum", None, "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8 \u0BB0\u0BAF\u0BBF\u0BB2\u0BCD \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD", None, False),  # Madurai Railway Station
        ("from anna nagar to airport", "\u0B85\u0BA3\u0BCD\u0BA3\u0BBE \u0BA8\u0B95\u0BB0\u0BCD", "\u0BB5\u0BBF\u0BAE\u0BBE\u0BA9 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD", None, False),  # Anna Nagar -> Airport
        ("location trichy", None, None, "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", False),  # Trichy
        ("madurai la irundhu trichy ku", "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8", "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", None, False),  # Madurai -> Trichy
        ("ila trichy la irundhu madurai ku poganum", "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8", None, False),  # Trichy -> Madurai
        ("madurai", None, None, "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8", False),  # Madurai
        ("kovil", None, None, None, True),  # Vague
        ("enaku parota kadaiku poganum", None, "Parota Kadai", None, False),  # Parota Kadai
    ]
    
    passed = 0
    failed = 0
    failures = []
    
    for input_text, exp_pickup, exp_drop, exp_bare, exp_vague in tests:
        result = parse_places(input_text)
        
        match = (result["pickup"] == exp_pickup and
                 result["drop"] == exp_drop and
                 result["bare"] == exp_bare and
                 result["vague"] == exp_vague)
        
        if match:
            print(f"PASS places: {input_text}")
            passed += 1
        else:
            print(f"FAIL places: {input_text}")
            failed += 1
            failures.append((
                f"places({input_text})",
                f"pickup={repr(exp_pickup)} drop={repr(exp_drop)} bare={repr(exp_bare)} vague={exp_vague}",
                f"pickup={repr(result['pickup'])} drop={repr(result['drop'])} bare={repr(result['bare'])} vague={result['vague']}"
            ))
    
    return passed, failed, failures


def test_time():
    """Test time parsing."""
    tests = [
        ("naliki 7 30 ku", {"date": "tomorrow", "now": False, "hour": 7, "minute": 30, "ampm": None}),
        ("naliki 730 ku", {"date": "tomorrow", "now": False, "hour": 7, "minute": 30, "ampm": None}),
        ("ezharai", {"date": None, "now": False, "hour": 7, "minute": 30, "ampm": None}),
        ("arai", {"date": None, "now": False, "hour": 6, "minute": 30, "ampm": None}),
        ("ettarai", {"date": None, "now": False, "hour": 8, "minute": 30, "ampm": None}),
        ("7 mani", {"date": None, "now": False, "hour": 7, "minute": 0, "ampm": None}),
        ("ezhu mani", {"date": None, "now": False, "hour": 7, "minute": 0, "ampm": None}),
        ("19:30", {"date": None, "now": False, "hour": 7, "minute": 30, "ampm": "pm"}),
        ("kalai", {"date": None, "now": False, "ampm": "am"}),
        ("malai", {"date": None, "now": False, "ampm": "pm"}),
        ("inniki raathri 9 mani ku", {"date": "today", "now": False, "hour": 9, "minute": 0, "ampm": "pm"}),
        ("ippo cab venum", {"now": True}),
        ("ippove", {"now": True}),
        ("naliki", {"date": "tomorrow"}),
    ]
    
    passed = 0
    failed = 0
    failures = []
    
    for input_text, expected in tests:
        result = parse_time(input_text)
        
        match = True
        for key in expected:
            if key not in result:
                if expected[key] is not None:
                    match = False
                    break
            elif result[key] != expected[key]:
                match = False
                break
        
        if match:
            print(f"PASS time: {input_text}")
            passed += 1
        else:
            print(f"FAIL time: {input_text}")
            failed += 1
            failures.append((
                f"time({input_text})",
                str(expected),
                str(result)
            ))
    
    return passed, failed, failures


def test_questions():
    """Test question detection."""
    tests = [
        ("madurai la enna famous", True),
        ("time enna", True),
        ("2 * 3 evlo", True),
        ("nee epidi iruka", True),
        ("naa madurai la iruken atha pathi sollu", True),
        ("madurai la irundhu trichy ku", False),
        ("cab venum", False),
        ("chenni ponnum", False),
        # New tests for whole-word matching
        ("chennai", False),
        ("enaku oru cab book pannanum", False),
        ("naa trichy pognum", False),
        ("naa chennai ponnum", False),
        ("enna macha pannure", True),
        ("madurai la enna famous", True),
        ("time enna", True),
        ("naa madurai la iruken atha pathi sollu", True),
        ("2 * 3 evlo", True),
    ]
    
    passed = 0
    failed = 0
    failures = []
    
    for input_text, expected in tests:
        result = is_question(input_text)
        
        if result == expected:
            print(f"PASS question: {input_text}")
            passed += 1
        else:
            print(f"FAIL question: {input_text}")
            failed += 1
            failures.append((
                f"is_question({input_text})",
                str(expected),
                str(result)
            ))
    
    return passed, failed, failures


def test_endings():
    """Test Tamil endings (dat/loc). Cases from check_endings.py ground truth."""
    tests = [
        # Madurai
        ("\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8", "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8\u0B95\u0BCD\u0B95\u0BC1", "\u0BAE\u0BA4\u0BC1\u0BB0\u0BC8\u0BAF\u0BBF\u0BB2\u0BCD"),
        # Trichy
        ("\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF", "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF\u0B95\u0BCD\u0B95\u0BC1", "\u0BA4\u0BBF\u0BB0\u0BC1\u0B9A\u0BCD\u0B9A\u0BBF\u0BAF\u0BBF\u0BB2\u0BCD"),
        # Anna Nagar (no locative)
        ("\u0B85\u0BA3\u0BCD\u0BA3\u0BBE \u0BA8\u0B95\u0BB0\u0BCD", "\u0B85\u0BA3\u0BCD\u0BA3\u0BBE \u0BA8\u0B95\u0BB0\u0BC1\u0B95\u0BCD\u0B95\u0BC1", None),
        # Teppakulam
        ("\u0BA4\u0BC6\u0BAA\u0BCD\u0BAA\u0B95\u0BCD\u0B95\u0BC1\u0BB3\u0BAE\u0BCD", "\u0BA4\u0BC6\u0BAA\u0BCD\u0BAA\u0B95\u0BCD\u0B95\u0BC1\u0BB3\u0BA4\u0BCD\u0BA4\u0BC1\u0B95\u0BCD\u0B95\u0BC1", "\u0BA4\u0BC6\u0BAA\u0BCD\u0BAA\u0B95\u0BCD\u0B95\u0BC1\u0BB3\u0BA4\u0BCD\u0BA4\u0BBF\u0BB2\u0BCD"),
        # Airport (Vimaan Nilayam)
        ("\u0BB5\u0BBF\u0BAE\u0BBE\u0BA9 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BAE\u0BCD", "\u0BB5\u0BBF\u0BAE\u0BBE\u0BA9 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BA4\u0BCD\u0BA4\u0BC1\u0B95\u0BCD\u0B95\u0BC1", "\u0BB5\u0BBF\u0BAE\u0BBE\u0BA9 \u0BA8\u0BBF\u0BB2\u0BC8\u0BAF\u0BA4\u0BCD\u0BA4\u0BBF\u0BB2\u0BCD"),
        # Meenakshi Amman Kovil (no locative)
        ("\u0BAE\u0BC0\u0BA9\u0BBE\u0B9F\u0BCD\u0B9A\u0BBF \u0B85\u0BAE\u0BCD\u0BAE\u0BA9\u0BCD \u0B95\u0BCB\u0BB5\u0BBF\u0BB2\u0BCD", "\u0BAE\u0BC0\u0BA9\u0BBE\u0B9F\u0BCD\u0B9A\u0BBF \u0B85\u0BAE\u0BCD\u0BAE\u0BA9\u0BCD \u0B95\u0BCB\u0BB5\u0BBF\u0BB2\u0BC1\u0B95\u0BCD\u0B95\u0BC1", None),
        # Chennai
        ("\u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8", "\u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0B95\u0BCD\u0B95\u0BC1", "\u0B9A\u0BC6\u0BA9\u0BCD\u0BA9\u0BC8\u0BAF\u0BBF\u0BB2\u0BCD"),
    ]
    
    passed = 0
    failed = 0
    failures = []
    
    for input_text, exp_dat, exp_loc in tests:
        result_dat = dat(input_text)
        result_loc = loc(input_text)
        
        dat_ok = result_dat == exp_dat
        loc_ok = (exp_loc is None) or (result_loc == exp_loc)
        
        if dat_ok and loc_ok:
            print(f"PASS endings: {repr(input_text)}")
            passed += 1
        else:
            print(f"FAIL endings: {repr(input_text)}")
            failed += 1
            if not dat_ok:
                failures.append((
                    f"dat({repr(input_text)})",
                    repr(exp_dat),
                    repr(result_dat)
                ))
            if not loc_ok:
                failures.append((
                    f"loc({repr(input_text)})",
                    repr(exp_loc),
                    repr(result_loc)
                ))
    
    return passed, failed, failures


def test_lexicon_vs_place_names():
    """Check that every display name in lexicon is in PLACE_NAMES.txt and vice versa."""
    from dialogue_parse import PLACES
    
    # Read PLACE_NAMES.txt
    try:
        with open("PLACE_NAMES.txt", "r", encoding="utf-8") as f:
            place_names_content = f.read().strip()
    except FileNotFoundError:
        print("FAIL lexicon: PLACE_NAMES.txt not found")
        return 0, 1, [("PLACE_NAMES.txt", "exists", "not found")]
    
    place_names_lines = {line.strip() for line in place_names_content.split("\n") if line.strip()}
    
    # Get all Tamil display names from PLACES dict
    lexicon_names = set(PLACES.keys())
    
    # Check for mismatches
    mismatches = []
    
    # Check lexicon names not in PLACE_NAMES.txt
    in_lexicon_not_in_file = lexicon_names - place_names_lines
    if in_lexicon_not_in_file:
        for name in sorted(in_lexicon_not_in_file):
            mismatches.append(("IN LEXICON NOT IN FILE", name))
    
    # Check PLACE_NAMES.txt lines not in lexicon
    in_file_not_in_lexicon = place_names_lines - lexicon_names
    if in_file_not_in_lexicon:
        for name in sorted(in_file_not_in_lexicon):
            mismatches.append(("IN FILE NOT IN LEXICON", name))
    
    if mismatches:
        print(f"FAIL lexicon: {len(mismatches)} mismatch(es)")
        for mtype, name in mismatches:
            print(f"  {mtype}: {repr(name)}")
        return 0, 1, [("lexicon_vs_place_names", "match", f"{len(mismatches)} mismatches")]
    else:
        print(f"PASS lexicon: all {len(lexicon_names)} names match")
        return 1, 0, []


def main():
    print("=" * 80)
    print("Checking lexicon vs PLACE_NAMES.txt")
    print("=" * 80)
    p0, f0, fail0 = test_lexicon_vs_place_names()
    
    print("\n" + "=" * 80)
    print("Testing place parsing")
    print("=" * 80)
    p1, f1, fail1 = test_places()
    
    print("\n" + "=" * 80)
    print("Testing time parsing")
    print("=" * 80)
    p2, f2, fail2 = test_time()
    
    print("\n" + "=" * 80)
    print("Testing question detection")
    print("=" * 80)
    p3, f3, fail3 = test_questions()
    
    print("\n" + "=" * 80)
    print("Testing Tamil endings")
    print("=" * 80)
    p4, f4, fail4 = test_endings()
    
    total_passed = p0 + p1 + p2 + p3 + p4
    total_failed = f0 + f1 + f2 + f3 + f4
    all_failures = fail0 + fail1 + fail2 + fail3 + fail4
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    
    if all_failures:
        print("\nFAILURES:")
        for case, expected, actual in all_failures:
            print(f"\n{case}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")
    
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
