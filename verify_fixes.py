"""Quick smoke test — run before adding regression test suite."""
from chat_memory import (
    detect_intent, _detect_statement_intent, detect_language_style,
    answer_question, is_personal_history_question
)
from fact_extractor import _looks_like_personal_statement, _extract_by_regex

cases = [
    # (message, expected_detect_intent)
    ("naa KLNCE il padikuren",                          "user_school"),
    ("naa enna college padikuren",                      "user_school"),
    ("which college am i have done my college degree",  "user_school"),
    ("naa enna college la padichen",                    "user_school"),
    ("Naan endha college la padichen?",                 "user_school"),
    ("En college enna?",                                "user_school"),
    # Existing intents must still work
    ("What is my name?",                                "user_name"),
    ("En goal enna?",                                   "user_goal"),
    ("naan enna kathukkiren?",                          "user_learning"),
    ("What am I learning?",                             "user_learning"),
]

stmt_cases = [
    # (message, expected_stmt_intent)
    ("naa KLNCE il padikuren",          "user_school"),
    ("naa KLNCE la padikuren",          "user_school"),
    ("naan KLNCE la padikuren",         "user_school"),
    ("Naan Anna University la padichen","user_school"),
    ("I studied at KLNCE",              "user_school"),
    ("I'm studying at KLNCE",           "user_school"),
    ("My name is Sarandeep",            "user_name"),
    ("Naan Python kathukittu irukken",  "user_learning"),
]

heuristic_cases = [
    # (message, expected_bool)
    ("naa KLNCE il padikuren",          True),
    ("naa KLNCE la padikuren",          True),
    ("naan KLNCE la padikuren",         True),
    ("I'm studying at KLNCE",           True),
    ("I studied at KLNCE",              True),
    ("naa enna college padikuren",      True),   # ambiguous but matches padikuren stmt pattern
    ("which college am i",              False),   # question → heuristic False is correct
]

regex_cases = [
    # (message, expected_key, expected_edu_status)
    ("naa KLNCE il padikuren",              "user_school", "current"),
    ("naa KLNCE la padikuren",              "user_school", "current"),
    ("naan KLNCE la padikuren",             "user_school", "current"),
    ("naa KLNCE il padichen",               "user_school", "past"),
    ("naa KLNCE la padichen",               "user_school", "past"),
    ("I'm studying at KLNCE",               "user_school", "current"),
    ("I studied at KLNCE",                  "user_school", "past"),
]

print("=== detect_intent ===")
all_ok = True
for msg, expected in cases:
    got = detect_intent(msg)
    status = "OK  " if got == expected else "FAIL"
    if got != expected:
        all_ok = False
    print(f"  {status}  {msg!r}")
    if got != expected:
        print(f"         got={got!r}  want={expected!r}")

print()
print("=== _detect_statement_intent ===")
for msg, expected in stmt_cases:
    got = _detect_statement_intent(msg)
    status = "OK  " if got == expected else "FAIL"
    if got != expected:
        all_ok = False
    print(f"  {status}  {msg!r}")
    if got != expected:
        print(f"         got={got!r}  want={expected!r}")

print()
print("=== heuristic ===")
for msg, expected in heuristic_cases:
    got = _looks_like_personal_statement(msg)
    status = "OK  " if got == expected else "FAIL"
    if got != expected:
        all_ok = False
    print(f"  {status}  {msg!r}")
    if got != expected:
        print(f"         got={got!r}  want={expected!r}")

print()
print("=== regex ===")
for msg, exp_key, exp_edu in regex_cases:
    facts = _extract_by_regex(msg)
    if not facts:
        print(f"  FAIL  {msg!r}  -> no facts extracted")
        all_ok = False
        continue
    f = facts[0]
    ok = (f.key == exp_key and f.education_status == exp_edu)
    status = "OK  " if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"  {status}  {msg!r}")
    if not ok:
        print(f"         got key={f.key!r} edu={f.education_status!r}  want key={exp_key!r} edu={exp_edu!r}")

print()
print("=== is_personal_history_question (guard) ===")
guard_cases = [
    ("which college am i have done my college degree", True),
    ("what degree do i have",                          True),
    ("did i graduate",                                 True),
    ("naa enna college padikuren",                     True),
    ("En college enna?",                               True),
    ("Tell me about the universe",                     False),
    ("What is my name?",                               False),  # handled by intent, not guard
]
for msg, expected in guard_cases:
    intent = detect_intent(msg)
    # guard matters only when detect_intent returns None
    got = is_personal_history_question(msg)
    status = "OK  " if got == expected else "FAIL"
    if got != expected:
        all_ok = False
    print(f"  {status}  guard={got}  intent={intent!r}  {msg!r}")

print()
print("ALL OK:" if all_ok else "SOME FAILURES")
