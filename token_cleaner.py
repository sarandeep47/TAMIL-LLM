"""TokenCleaner: removes a leading "A:" or "Assistant:" from a streamed reply.

Usage:
    cleaner = TokenCleaner()
    for chunk in stream:
        out = cleaner.feed(chunk)
        if out:
            emit(out)
    tail = cleaner.flush()
    if tail:
        emit(tail)

It holds text back only while the start of the reply could still turn into one
of the prefixes ("A", "As", ..., "Assistant"). Anything else is passed through
at once, so normal replies are not delayed.
"""

PREFIXES = ("A:", "Assistant:")


class TokenCleaner:
    def __init__(self):
        self._buf = ""
        self._decided = False
        self._lead = False  # trim leading spaces of the first emitted text

    def _emit(self, text: str) -> str:
        if self._lead:
            text = text.lstrip()
            if text:
                self._lead = False
        return text

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        if self._decided:
            return self._emit(chunk)
        self._buf += chunk
        s = self._buf.lstrip()
        if not s:
            return ""  # only whitespace so far, keep waiting
        for p in PREFIXES:
            if s.startswith(p):
                self._decided = True
                self._lead = True
                self._buf = ""
                return self._emit(s[len(p):])
        if any(p.startswith(s) for p in PREFIXES):
            return ""  # could still become a prefix, hold back
        self._decided = True
        self._lead = True
        self._buf = ""
        return self._emit(s)

    def flush(self) -> str:
        if self._decided or not self._buf:
            self._buf = ""
            return ""
        out = self._buf.lstrip()
        self._buf = ""
        self._decided = True
        return out
