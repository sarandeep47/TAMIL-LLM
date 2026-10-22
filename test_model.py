
import torch
from model.transformer import TinyTamilGPT

vocab_size = 20

model = TinyTamilGPT(vocab_size=vocab_size)

# Two sample sequences, each containing 8 token IDs.
tokens = torch.randint(0, vocab_size, (2, 8))

logits = model(tokens)

print("Input shape:", tokens.shape)
print("Output shape:", logits.shape)
print("Parameter count:", sum(p.numel() for p in model.parameters()))

assert logits.shape == (2, 8, vocab_size)

print("Transformer test passed!")
