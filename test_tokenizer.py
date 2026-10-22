
import sys
import io

# Force UTF-8 output so Tamil characters print correctly on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from model.tokenizer import TamilTokenizer

text = "வணக்கம். நான் தமிழ் கற்கிறேன்."

tokenizer = TamilTokenizer(text)

encoded = tokenizer.encode(text)
decoded = tokenizer.decode(encoded)

print("Original:", text)
print("Vocabulary size:", len(tokenizer.chars))
print("Encoded:", encoded)
print("Decoded:", decoded)

assert decoded == text
print("Tokenizer test passed!")
