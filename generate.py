"""
generate.py -- Generate Tamil text using a trained TinyTamilGPT checkpoint.

Usage (from the project root):
    python generate.py
    python generate.py --prompt "வணக்கம்" --max_new_tokens 200 --temperature 0.8
    python generate.py --checkpoint checkpoints/tiny_tamil_gpt.pt

Options:
    --prompt          Starting Tamil text (default: first character of vocabulary)
    --max_new_tokens  Number of new characters to generate (default: 200)
    --temperature     Sampling temperature: lower=focused, higher=creative (default: 1.0)
    --checkpoint      Path to the saved .pt checkpoint file
"""

import argparse
import os
import sys

import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Resolve project root so this script can be run from any directory
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.tokenizer import TamilTokenizer
from model.transformer import TinyTamilGPT

DEFAULT_CHECKPOINT = os.path.join("checkpoints", "tiny_tamil_gpt.pt")
DEFAULT_MAX_TOKENS = 200
DEFAULT_TEMPERATURE = 1.0


# ---------------------------------------------------------------------------
# Checkpoint loading
# ---------------------------------------------------------------------------

def load_checkpoint(checkpoint_path: str):
    """Load model and tokenizer from a saved checkpoint."""
    abs_path = (
        os.path.join(_ROOT, checkpoint_path)
        if not os.path.isabs(checkpoint_path)
        else checkpoint_path
    )
    if not os.path.exists(abs_path):
        sys.exit(
            f"\n[ERROR] Checkpoint not found: {abs_path}\n"
            "Train the model first:\n"
            "    python -m model.train\n"
        )

    print(f"Loading checkpoint from '{abs_path}' ...")
    ckpt = torch.load(abs_path, map_location="cpu", weights_only=False)

    # Reconstruct the tokenizer from the saved character list.
    # IMPORTANT: use the saved order directly rather than re-sorting,
    # so that char_to_id indices match those stored in the model weights.
    chars = ckpt["chars"]
    tokenizer = TamilTokenizer.__new__(TamilTokenizer)
    tokenizer.chars = chars
    tokenizer.char_to_id = {ch: i for i, ch in enumerate(chars)}
    tokenizer.id_to_char = {i: ch for i, ch in enumerate(chars)}

    # Rebuild the model with identical architecture
    model = TinyTamilGPT(
        vocab_size=ckpt["vocab_size"],
        context_length=ckpt["context_length"],
        embedding_size=ckpt["embedding_size"],
        num_heads=ckpt["num_heads"],
        num_layers=ckpt["num_layers"],
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    print(
        f"  Architecture: vocab={ckpt['vocab_size']}, "
        f"ctx={ckpt['context_length']}, "
        f"emb={ckpt['embedding_size']}, "
        f"heads={ckpt['num_heads']}, "
        f"layers={ckpt['num_layers']}"
    )
    if "best_val_loss" in ckpt:
        print(f"  Best val loss during training: {ckpt['best_val_loss']:.4f}")
    return model, tokenizer, ckpt


# ---------------------------------------------------------------------------
# Text generation
# ---------------------------------------------------------------------------

@torch.no_grad()
def generate(
    model: TinyTamilGPT,
    tokenizer: TamilTokenizer,
    prompt: str,
    max_new_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    """
    Generate text one character at a time, starting from `prompt`.

    The context window is always capped at model.context_length so that
    position embeddings are never exceeded.
    """
    context_length = model.context_length

    # Encode prompt, skipping characters not seen during training
    unknown_chars = [c for c in prompt if c not in tokenizer.char_to_id]
    if unknown_chars:
        unique_unk = sorted(set(unknown_chars))
        print(
            f"[WARNING] {len(unique_unk)} character(s) in the prompt were not "
            f"seen during training and will be skipped: {unique_unk}"
        )

    ids = tokenizer.encode(prompt)  # encode() already silently skips unknowns
    if not ids:
        # Fall back to the first character in vocabulary
        fallback = tokenizer.chars[0]
        print(
            f"[WARNING] Prompt produced no tokens. "
            f"Using vocabulary start character as seed: '{fallback}'"
        )
        ids = tokenizer.encode(fallback)

    tokens = torch.tensor(ids, dtype=torch.long).unsqueeze(0)  # (1, T)

    generated = list(ids)

    for _ in range(max_new_tokens):
        # Crop to context window
        context = tokens[:, -context_length:]

        logits = model(context)          # (1, T, vocab_size)
        next_logits = logits[:, -1, :]  # (1, vocab_size) -- last position only

        # Apply temperature
        if temperature != 1.0:
            next_logits = next_logits / temperature

        # Greedy decoding when temperature is essentially zero
        if temperature <= 0.01:
            next_id = next_logits.argmax(dim=-1, keepdim=True)  # (1, 1)
        else:
            probs = F.softmax(next_logits, dim=-1)  # (1, vocab_size)
            next_id = torch.multinomial(probs, num_samples=1)  # (1, 1)

        tokens = torch.cat([tokens, next_id], dim=1)
        generated.append(next_id.item())

    return tokenizer.decode(generated)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Tamil text using a trained TinyTamilGPT model."
    )
    parser.add_argument(
        "--checkpoint",
        default=DEFAULT_CHECKPOINT,
        help=f"Path to checkpoint file (default: {DEFAULT_CHECKPOINT})",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Starting Tamil text prompt (default: first vocabulary character)",
    )
    parser.add_argument(
        "--max_new_tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Characters to generate (default: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help=(
            f"Sampling temperature (default: {DEFAULT_TEMPERATURE}). "
            "Lower values are more predictable; higher values are more varied."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    model, tokenizer, ckpt = load_checkpoint(args.checkpoint)

    # Default prompt: use first vocab character if none given
    prompt = args.prompt if args.prompt else tokenizer.chars[0]
    print(f"\nPrompt : {prompt!r}")
    print(f"Tokens : {args.max_new_tokens}  |  Temperature: {args.temperature}\n")
    print("-" * 60)

    output = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
    )

    print(output)
    print("-" * 60)


if __name__ == "__main__":
    main()
