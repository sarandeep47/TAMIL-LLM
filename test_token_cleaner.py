"""Run: python test_token_cleaner.py   (no server, no model)"""
from token_cleaner import TokenCleaner


def run(chunks, flush=True):
    c = TokenCleaner()
    out = "".join(c.feed(x) for x in chunks)
    if flush:
        out += c.flush()
    return out


CASES = [
    # (name, chunks, expected total output)
    ("A: in pieces", ["A", ":", " \u0b85\u0ba4\u0bc1", " \u0b9a\u0bc6\u0ba9\u0bcd\u0ba9\u0bc8."],
     "\u0b85\u0ba4\u0bc1 \u0b9a\u0bc6\u0ba9\u0bcd\u0ba9\u0bc8."),
    ("A: in one chunk", ["A: Hello there"], "Hello there"),
    ("Assistant: then text", ["Assistant:", " Hi"], "Hi"),
    ("Assistant: in pieces", ["Ass", "istant", ":", " Hi"], "Hi"),
    ("no prefix", ["Hello"], "Hello"),
    ("Tamil, no prefix", ["\u0b9a\u0bb0\u0bbf, \u0b8e\u0b99\u0bcd\u0b95\u0bc7?"], "\u0b9a\u0bb0\u0bbf, \u0b8e\u0b99\u0bcd\u0b95\u0bc7?"),
    ("lone A then flush", ["A"], "A"),
    ("sentence starting with A", ["A", " cab", " is coming."], "A cab is coming."),
    ("word starting with Ass", ["Ass", "istance is here"], "Assistance is here"),
    ("empty chunks ignored", ["", "A", "", ":", "", " Hi"], "Hi"),
    ("leading spaces", ["  A: ", "Hi"], "Hi"),
    ("A: only", ["A:"], ""),
    ("A: appears later is kept", ["Hello A: world"], "Hello A: world"),
]

fails = 0
for name, chunks, expected in CASES:
    got = run(chunks)
    ok = got == expected
    fails += not ok
    print(("PASS" if ok else "FAIL"), name, "" if ok else f"-> {got!r} expected {expected!r}")

# no delay for normal replies: the first chunk must be emitted immediately
c = TokenCleaner()
first = c.feed("\u0b9a\u0bb0\u0bbf")
ok = first == "\u0b9a\u0bb0\u0bbf"
fails += not ok
print(("PASS" if ok else "FAIL"), "normal reply not delayed")

print(f"\n{len(CASES) + 1 - fails}/{len(CASES) + 1} passed")
raise SystemExit(1 if fails else 0)
