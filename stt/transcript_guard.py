"""
Transcript guard to detect echo and loop patterns in STT output.
"""
import re
import os


HINT_WORDS = {"வணக்கம்", "நன்றி", "கேப்", "கார்", "இருக்கேன்", "இருக்கிறது"}
PERSONAI_WHISPER_PROMPT = os.getenv("PERSONAI_WHISPER_PROMPT", "")


def check_transcript(text: str) -> str:
    """
    Check if transcript is 'ok', 'echo', or 'loop'.
    
    - echo: 3+ words, all words (lowercase, stripped of punctuation) are from hint list
    - loop: a word appears 4+ times in text of 6+ words, or 2-word sequence 3+ times
    - ok: otherwise
    
    Returns: "ok" | "echo" | "loop"
    """
    if not text:
        return "ok"
    
    # Normalize: lowercase, strip punctuation
    words = []
    for word in text.split():
        # Remove punctuation
        cleaned = re.sub(r'[^\w\u0B80-\u0BFF]', '', word).lower()
        if cleaned:
            words.append(cleaned)
    
    if not words:
        return "ok"
    
    # Build combined hint set: default hints + words from PERSONAI_WHISPER_PROMPT
    combined_hints = HINT_WORDS.copy()
    if PERSONAI_WHISPER_PROMPT:
        for word in PERSONAI_WHISPER_PROMPT.split(','):
            hint_word = re.sub(r'[^\w\u0B80-\u0BFF]', '', word).strip().lower()
            if hint_word:
                combined_hints.add(hint_word)
    
    # Check for ECHO: 3+ words, all from hint list
    if len(words) >= 3 and all(word in combined_hints for word in words):
        return "echo"
    
    # Check for LOOP: word appears 4+ times in 6+ words, or 2-word seq 3+ times
    if len(words) >= 6:
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Single word appears 4+ times
        if any(count >= 4 for count in word_counts.values()):
            return "loop"
    
    # Check 2-word sequences (appear 3+ times)
    if len(words) >= 5:
        bigram_counts = {}
        for i in range(len(words) - 1):
            bigram = (words[i], words[i + 1])
            bigram_counts[bigram] = bigram_counts.get(bigram, 0) + 1
        
        if any(count >= 3 for count in bigram_counts.values()):
            return "loop"
    
    return "ok"
