"""
train.py — Train TinyTamilGPT on a Tamil character-level corpus.

Usage (from the project root):
    python -m model.train
    python -m model.train --steps 500 --batch_size 8 --lr 3e-4

The script reads data/tamil.txt, builds a character-level tokenizer,
trains the tiny transformer, and saves a checkpoint to
checkpoints/tiny_tamil_gpt.pt.
"""

import argparse
import math
import os
import sys
import time

import torch
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Allow running as "python model/train.py" directly (adds project root to path)
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from model.tokenizer import TamilTokenizer
from model.transformer import TinyTamilGPT


# ---------------------------------------------------------------------------
# Default hyperparameters — conservative for an 8 GB CPU laptop
# ---------------------------------------------------------------------------
DEFAULTS = dict(
    data_path="data/tamil.txt",
    checkpoint_path="checkpoints/tiny_tamil_gpt.pt",
    steps=2000,
    batch_size=16,
    context_length=64,
    embedding_size=64,
    num_heads=2,
    num_layers=2,
    lr=1e-3,
    val_fraction=0.1,
    eval_interval=200,
    eval_batches=20,
    seed=42,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_text(path: str) -> str:
    """Read the dataset and return its full content as a string."""
    abs_path = os.path.join(_ROOT, path) if not os.path.isabs(path) else path
    if not os.path.exists(abs_path):
        sys.exit(
            f"\n[ERROR] Dataset not found: {abs_path}\n"
            "Please create data/tamil.txt with at least a few hundred Tamil characters."
        )
    with open(abs_path, encoding="utf-8") as f:
        text = f.read()
    if len(text) < 100:
        sys.exit(
            f"\n[ERROR] Dataset is too small ({len(text)} chars). "
            "Add more Tamil text to data/tamil.txt and try again."
        )
    return text


def get_batch(data: torch.Tensor, context_length: int, batch_size: int):
    """
    Sample a random batch of (inputs, targets).

    inputs  -- shape (batch_size, context_length)
    targets -- shape (batch_size, context_length)  [shifted by 1]
    """
    max_start = len(data) - context_length - 1
    if max_start < 1:
        sys.exit(
            "[ERROR] Dataset is too small for the requested context_length. "
            "Reduce --context_length or add more data."
        )
    starts = torch.randint(0, max_start, (batch_size,))
    xs = torch.stack([data[s : s + context_length] for s in starts])
    ys = torch.stack([data[s + 1 : s + context_length + 1] for s in starts])
    return xs, ys


@torch.no_grad()
def estimate_loss(
    model: TinyTamilGPT,
    train_data: torch.Tensor,
    val_data: torch.Tensor,
    context_length: int,
    batch_size: int,
    eval_batches: int,
) -> dict:
    """Estimate average loss on train and validation splits."""
    model.eval()
    results = {}
    for split_name, data in [("train", train_data), ("val", val_data)]:
        losses = []
        for _ in range(eval_batches):
            xb, yb = get_batch(data, context_length, batch_size)
            logits = model(xb)
            # Flatten to (batch*context, vocab) for cross-entropy
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)), yb.view(-1)
            )
            losses.append(loss.item())
        results[split_name] = sum(losses) / len(losses)
    model.train()
    return results


# ---------------------------------------------------------------------------
# Main training routine
# ---------------------------------------------------------------------------

def train(cfg: dict):
    torch.manual_seed(cfg["seed"])

    # 1. Load and tokenise the corpus
    print(f"[1/7] Loading dataset from '{cfg['data_path']}' ...")
    text = load_text(cfg["data_path"])
    print(f"      {len(text):,} characters loaded.")

    tokenizer = TamilTokenizer(text)
    vocab_size = len(tokenizer.chars)
    print(f"      Vocabulary size: {vocab_size} unique characters.")

    ids = tokenizer.encode(text)
    data = torch.tensor(ids, dtype=torch.long)

    # 2. Train / validation split (no shuffle to avoid data leakage)
    split_idx = int(len(data) * (1.0 - cfg["val_fraction"]))
    train_data = data[:split_idx]
    val_data = data[split_idx:]
    print(
        f"      Train tokens: {len(train_data):,}  |  "
        f"Val tokens: {len(val_data):,}"
    )

    # Guard: validation split must be large enough for at least one batch
    if len(val_data) < cfg["context_length"] + 1:
        sys.exit(
            "[ERROR] Validation split is too small. "
            "Add more data to data/tamil.txt or reduce --val_fraction."
        )

    # 3. Build model
    print("[2/7] Initialising TinyTamilGPT ...")
    model = TinyTamilGPT(
        vocab_size=vocab_size,
        context_length=cfg["context_length"],
        embedding_size=cfg["embedding_size"],
        num_heads=cfg["num_heads"],
        num_layers=cfg["num_layers"],
    )
    param_count = sum(p.numel() for p in model.parameters())
    print(f"      Parameters: {param_count:,}")

    # 4. Optimiser
    print("[3/7] Setting up AdamW optimiser ...")
    optimiser = torch.optim.AdamW(model.parameters(), lr=cfg["lr"])

    # 5. Training loop
    print(f"[4/7] Training for {cfg['steps']:,} steps ...")
    print(f"      Batch size: {cfg['batch_size']}  |  "
          f"Context length: {cfg['context_length']}  |  "
          f"Learning rate: {cfg['lr']}")
    print()

    best_val_loss = math.inf
    model.train()
    t0 = time.time()

    for step in range(1, cfg["steps"] + 1):
        xb, yb = get_batch(
            train_data, cfg["context_length"], cfg["batch_size"]
        )
        logits = model(xb)
        loss = F.cross_entropy(
            logits.view(-1, logits.size(-1)), yb.view(-1)
        )

        optimiser.zero_grad()
        loss.backward()
        optimiser.step()

        # Periodic evaluation
        if step % cfg["eval_interval"] == 0 or step == 1:
            elapsed = time.time() - t0
            losses = estimate_loss(
                model,
                train_data,
                val_data,
                cfg["context_length"],
                cfg["batch_size"],
                cfg["eval_batches"],
            )
            flag = " <- best" if losses["val"] < best_val_loss else ""
            if losses["val"] < best_val_loss:
                best_val_loss = losses["val"]
            print(
                f"  step {step:>5}/{cfg['steps']}  |  "
                f"train loss: {losses['train']:.4f}  |  "
                f"val loss: {losses['val']:.4f}  |  "
                f"elapsed: {elapsed:.1f}s{flag}"
            )

    print()
    print(f"[5/7] Training complete. Best val loss: {best_val_loss:.4f}")

    # 6. Save checkpoint
    print(f"[6/7] Saving checkpoint to '{cfg['checkpoint_path']}' ...")
    ckpt_dir = os.path.dirname(
        os.path.join(_ROOT, cfg["checkpoint_path"])
    )
    os.makedirs(ckpt_dir, exist_ok=True)

    checkpoint = {
        # Model state
        "model_state_dict": model.state_dict(),
        # Architecture -- needed to rebuild the exact same model at inference
        "vocab_size": vocab_size,
        "context_length": cfg["context_length"],
        "embedding_size": cfg["embedding_size"],
        "num_heads": cfg["num_heads"],
        "num_layers": cfg["num_layers"],
        # Tokenizer vocabulary -- maps character <-> integer id
        "chars": tokenizer.chars,
        # Training metadata
        "steps": cfg["steps"],
        "best_val_loss": best_val_loss,
        "seed": cfg["seed"],
    }
    ckpt_path = os.path.join(_ROOT, cfg["checkpoint_path"])
    torch.save(checkpoint, ckpt_path)
    print(f"      Saved  ({os.path.getsize(ckpt_path):,} bytes)")

    print("[7/7] Done.")
    return model, tokenizer, checkpoint


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> dict:
    parser = argparse.ArgumentParser(
        description="Train TinyTamilGPT on a Tamil character corpus."
    )
    parser.add_argument("--data_path",       default=DEFAULTS["data_path"])
    parser.add_argument("--checkpoint_path", default=DEFAULTS["checkpoint_path"])
    parser.add_argument("--steps",           type=int,   default=DEFAULTS["steps"])
    parser.add_argument("--batch_size",      type=int,   default=DEFAULTS["batch_size"])
    parser.add_argument("--context_length",  type=int,   default=DEFAULTS["context_length"])
    parser.add_argument("--embedding_size",  type=int,   default=DEFAULTS["embedding_size"])
    parser.add_argument("--num_heads",       type=int,   default=DEFAULTS["num_heads"])
    parser.add_argument("--num_layers",      type=int,   default=DEFAULTS["num_layers"])
    parser.add_argument("--lr",              type=float, default=DEFAULTS["lr"])
    parser.add_argument("--val_fraction",    type=float, default=DEFAULTS["val_fraction"])
    parser.add_argument("--eval_interval",   type=int,   default=DEFAULTS["eval_interval"])
    parser.add_argument("--eval_batches",    type=int,   default=DEFAULTS["eval_batches"])
    parser.add_argument("--seed",            type=int,   default=DEFAULTS["seed"])
    return vars(parser.parse_args())


if __name__ == "__main__":
    train(parse_args())
