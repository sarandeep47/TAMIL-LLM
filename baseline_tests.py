#!/usr/bin/env python3
"""
HTTP test runner for /api/chat baseline (15 cases, exact spec).
Usage: python baseline_tests.py [http://localhost:8000] --label NAME
Writes baseline_<label>.csv (UTF-8 with BOM).
"""

import csv
import json
import re
import sys
import time
import urllib.request
from urllib.error import URLError, HTTPError


# Grading config
TAMIL = re.compile(r"[\u0B80-\u0BFF]")
FALLBACKS = ["புரியவில்லை", "இருக்கீன்"]
MAX_MS = 10_000

# Test cases: (input, kind, any_list)
CASES = [
    ("vanakam", "ta", ["வணக்கம்"]),
    ("வணக்கம்", "ta", ["உதவி"]),
    ("epdi irukinga", "ta", []),
    ("nalla iruken", "ta", []),
    ("nandri", "ta", []),
    ("enna panreenga", "ta", ["உதவ"]),
    ("Hello", "en", []),
    ("கேப் புக் பண்ணனும்", "ta", ["பிக்அப்", "பிக்கப்", "இடம்", "எங்க", "லொகேஷன்"]),
    ("Madurai la iruken", "ta", []),
    ("enna sonnenga?", "manual", []),
    ("நீ எப்படி இருக்கீங்க?", "ta", ["நல்லா", "நலம்"]),
    ("கார் வேணும்", "ta", ["பிக்கப்", "லொகேஷன்", "இடம்"]),
    ("சரி", "ta", []),
    ("hi, i want cab", "en", ["pickup", "Pickup"]),
    ("how are you?", "en", []),
]


def ask(base, text):
    """POST {text} to /api/chat, return (bot_text, ms, route, wall_ms)."""
    req = urllib.request.Request(
        base + "/api/chat",
        data=json.dumps({"text": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    wall_t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.load(r)
    except (URLError, HTTPError) as e:
        raise Exception(f"HTTP {e.code}: {e.reason}")
    wall_ms = int((time.time() - wall_t0) * 1000)
    ms = data.get("llm_latency_ms", -1)  # Server-reported latency
    return data.get("bot_text", ""), ms, data.get("route", "n/a"), wall_ms


def judge(case, reply, ms):
    """Auto-grade. Returns (verdict, note)."""
    kind, any_list = case[1], case[2]
    
    if not reply.strip():
        return "FAIL", "empty reply"
    if kind == "manual":
        return "MANUAL", "needs conversation history"
    
    problems = []
    if any(f in reply for f in FALLBACKS):
        problems.append("known-bad phrase")
    if kind == "ta" and not TAMIL.search(reply):
        problems.append("no Tamil script")
    if kind == "en" and len(TAMIL.findall(reply)) > 3:
        problems.append("Tamil in English reply")
    if any_list and not any(k in reply for k in any_list):
        problems.append("missing expected content")
    if ms > MAX_MS:
        problems.append(f"slow (>{MAX_MS}ms)")
    
    if problems:
        return "FAIL", "; ".join(problems)
    return "PASS", ""


def main():
    args = sys.argv[1:]
    label = args[args.index("--label") + 1] if "--label" in args else "baseline"
    base = next((a for a in args if a.startswith("http")), "http://127.0.0.1:8000")
    
    rows = []
    for text, kind, any_list in CASES:
        try:
            reply, ms, route, wall_ms = ask(base, text)
        except Exception as e:
            reply, ms, route, wall_ms = f"ERROR: {e}", -1, "error", -1
        
        verdict, note = judge((text, kind, any_list), reply, ms)
        rows.append([text, verdict, ms, wall_ms, route, reply, note, ""])
        print(f"[{verdict}] {text!r:40} {ms:6d}ms {route:20s} {reply[:50]!r} | {note}")
    
    # Write CSV
    csv_file = f"baseline_{label}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["input", "auto", "ms", "wall_ms", "route", "reply", "note", "manual_grade"])
        w.writerows(rows)
    
    ok = sum(1 for r in rows if r[1] == "PASS")
    print(f"\n{ok}/{len(rows)} auto-pass. Saved {csv_file}")


if __name__ == "__main__":
    main()
