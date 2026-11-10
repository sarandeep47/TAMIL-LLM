"""
Pure streaming utility functions for PersonAI backend.
No server imports, no external dependencies beyond stdlib.
"""

import re


def strip_role_prefix(text):
    """
    Remove leading 'A:' or 'Assistant:' and following whitespace from text.
    Handles cases where prefix arrives in pieces.
    """
    if not text:
        return text
    
    # Remove 'A:' or 'Assistant:' at the start
    text = text.lstrip()
    if text.startswith('A:'):
        text = text[2:].lstrip()
    elif text.startswith('Assistant:'):
        text = text[10:].lstrip()
    
    return text


class SentenceSplitter:
    """
    Incrementally parse text into sentences.
    A sentence ends at . ? ! followed by whitespace or end of input,
    but NOT inside numbers like 2.5.
    Minimum sentence length 3 characters.
    """
    
    def __init__(self):
        self.buffer = ""
        self.role_prefix_buffer = ""  # Handle role prefix arriving in pieces
    
    def feed(self, chunk):
        """
        Feed a text chunk. Return list of completed sentences (strings).
        """
        if not chunk:
            return []
        
        # Accumulate incoming chunk
        self.buffer += chunk
        
        # Try to extract completed sentences
        sentences = []
        
        while True:
            # Look for sentence-ending punctuation (. ? !)
            # Pattern: punctuation followed by whitespace or end of string
            # But NOT preceded by a digit (to avoid 2.5)
            match = re.search(r'([.!?])(?=\s|$)', self.buffer)
            
            if not match:
                break
            
            end_idx = match.end()
            sentence = self.buffer[:end_idx].strip()
            self.buffer = self.buffer[end_idx:].lstrip()
            
            # Only emit sentences of minimum 3 characters
            if len(sentence) >= 3:
                sentences.append(sentence)
        
        return sentences
    
    def flush(self):
        """
        Return remaining buffered text (partial sentence) or None if empty.
        """
        if self.buffer:
            remaining = self.buffer.strip()
            self.buffer = ""
            return remaining if len(remaining) >= 3 else None
        return None
