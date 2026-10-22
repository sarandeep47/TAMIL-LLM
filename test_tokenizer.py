
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
