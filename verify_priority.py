"""
Verify that question detection takes priority over statement extraction
for ambiguous Tanglish inputs (requirement 2 from user spec).
"""
from chat_memory import detect_intent, _detect_statement_intent, answer_question
from fact_extractor import _looks_like_personal_statement, _extract_by_regex, extract_facts
from unittest.mock import patch
import requests as req_lib

# ── Cases that MUST be treated as questions ──────────────────────────────────
question_priority_cases = [
    # (message, must_have_intent, must_NOT_extract_fact)
    ("naa enna college padikuren?",       "user_school",  True),
    ("naa KLNCE il padikuren?",           "user_school",  True),   # question mark
    ("En college enna?",                   "user_school",  True),
    ("which college did I graduate from?", "user_school",  True),
    ("what degree do i have?",             "user_school",  True),
]

print("=== Question priority (with ?) ===")
all_ok = True
for msg, exp_intent, must_not_extract in question_priority_cases:
    intent = detect_intent(msg)
    heuristic = _looks_like_personal_statement(msg)
    regex = _extract_by_regex(msg)
    ok_intent = (intent == exp_intent)
    ok_heur = (not heuristic)          # question → heuristic must be False
    ok_regex = (regex == [] if must_not_extract else True)
    ok = ok_intent and ok_heur and ok_regex
    if not ok:
        all_ok = False
    print(f"  {'OK  ' if ok else 'FAIL'} {msg!r}")
    if not ok_intent:
        print(f"       intent: got={intent!r}  want={exp_intent!r}")
    if not ok_heur:
        print(f"       heuristic: got={heuristic}  want=False")
    if not ok_regex:
        print(f"       regex: got={regex}  want=[]")

# ── Cases that MUST be treated as statements (no ?) ──────────────────────────
statement_cases = [
    # (message, must_extract_key, must_extract_edu_status)
    ("naa KLNCE il padikuren",  "user_school", "current"),
    ("naa KLNCE la padichen",   "user_school", "past"),
    ("I'm studying at KLNCE",   "user_school", "current"),
    ("I'm studying Python",     "user_learning", None),       # NOT school
]

print()
print("=== Statement extraction ===")
for msg, exp_key, exp_edu in statement_cases:
    heuristic = _looks_like_personal_statement(msg)
    with patch("fact_extractor.requests.post",
               side_effect=req_lib.exceptions.ConnectionError):
        facts = []
        try:
            from fact_extractor import extract_facts as ef
            facts = ef(msg)
        except Exception as e:
            print(f"  ERROR: {e}")
    matched = [f for f in facts if f.key == exp_key]
    ok = bool(matched)
    if ok and exp_edu is not None:
        ok = matched[0].education_status == exp_edu
    if not ok:
        all_ok = False
    print(f"  {'OK  ' if ok else 'FAIL'} {msg!r}")
    if not matched:
        print(f"       no {exp_key!r} fact extracted; got {facts!r}")
    elif exp_edu is not None and matched[0].education_status != exp_edu:
        print(f"       edu_status={matched[0].education_status!r}  want={exp_edu!r}")

# ── Ask/ack pipeline priority check ─────────────────────────────────────────
# For ambiguous input like "naa KLNCE il padikuren" (no ?):
# answer_question() must check intent BEFORE acknowledge_statement()
# If the question matches intent AND a fact is stored, answer_question wins.
print()
print("=== Pipeline priority: question > statement ack ===")
import memory_db, sqlite3
from pathlib import Path
import tempfile, os

# Use a real temp DB
tmpdir = tempfile.mkdtemp()
tmp_db = Path(tmpdir) / "test.db"

import importlib
orig_db = memory_db.DB_PATH
memory_db.DB_PATH = tmp_db
memory_db.initialize_database()
memory_db.save_memory("user_school", "KLNCE", category="education",
                      source="manual", education_status="current")

# Patch chat_memory to use temp DB
import chat_memory
orig_get = chat_memory.get_memory
orig_get_edu = chat_memory.get_education_status
chat_memory.get_memory = lambda k, language="english": memory_db.get_memory(k, language)
chat_memory.get_education_status = lambda k="user_school": memory_db.get_education_status(k)

# "naa enna college padikuren?" — has intent AND matches statement pattern
# It ends with '?', so heuristic→False, no fact extracted.
# answer_question should return KLNCE; acknowledge_statement should get None.
aq = answer_question("naa enna college padikuren?")
stmt = _detect_statement_intent("naa enna college padikuren?")
heur = _looks_like_personal_statement("naa enna college padikuren?")

print(f"  'naa enna college padikuren?':")
print(f"    heuristic={heur}  stmt_intent={stmt!r}  answer_question={aq!r}")
ok = (aq is not None and "KLNCE" in aq and not heur)
print(f"  {'OK  ' if ok else 'FAIL'} question correctly handled, fact retrieved")
if not ok:
    all_ok = False

# Restore
memory_db.DB_PATH = orig_db
chat_memory.get_memory = orig_get
chat_memory.get_education_status = orig_get_edu
import shutil; shutil.rmtree(tmpdir, ignore_errors=True)

print()
print("ALL OK" if all_ok else "SOME FAILURES")
