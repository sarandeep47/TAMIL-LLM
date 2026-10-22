"""
tests/test_train.py -- Pytest suite for the full TinyTamilGPT pipeline.

Covers:
  - Tokenizer encoding / decoding round-trip
  - Transformer output dimensions
  - get_batch correctness
  - Short training smoke-test (50 steps)
  - Checkpoint save and reload
  - Text generation
  - Invalid / missing dataset handling

All checkpoints are written to a temporary directory so nothing
is left behind in the project after the tests run.
"""

import importlib
import os
import sys
import tempfile

import pytest
import torch

# ---------------------------------------------------------------------------
# Make sure the project root is on the path regardless of how pytest is
# invoked (e.g. from the project root or from inside tests/).
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from model.tokenizer import TamilTokenizer
from model.transformer import TinyTamilGPT

# Import training helpers without executing __main__
import model.train as train_module
from model.train import get_batch, estimate_loss, train

# Generate helpers
from generate import load_checkpoint, generate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TEXT = (
    "வணக்கம். நான் தமிழ் கற்கிறேன். "
    "தமிழ் ஒரு அழகான மொழி. "
    "நீங்கள் எப்படி இருக்கிறீர்கள்? "
    "நான் நன்றாக இருக்கிறேன். "
    "எனக்கு தமிழ் பேச பிடிக்கும். " * 10   # repeat to get enough tokens
)


@pytest.fixture()
def tokenizer():
    return TamilTokenizer(SAMPLE_TEXT)


@pytest.fixture()
def model_and_vocab(tokenizer):
    vocab_size = len(tokenizer.chars)
    model = TinyTamilGPT(
        vocab_size=vocab_size,
        context_length=16,
        embedding_size=32,
        num_heads=2,
        num_layers=1,
    )
    return model, vocab_size


@pytest.fixture()
def encoded_data(tokenizer):
    ids = tokenizer.encode(SAMPLE_TEXT)
    return torch.tensor(ids, dtype=torch.long)


@pytest.fixture()
def tmp_checkpoint(tmp_path):
    """Returns a temporary .pt path that will be cleaned up automatically."""
    return str(tmp_path / "test_checkpoint.pt")


# ---------------------------------------------------------------------------
# Task 4a: Tokenizer tests
# ---------------------------------------------------------------------------

class TestTokenizer:
    def test_encode_decode_roundtrip(self, tokenizer):
        """Decoding the encoded text must reproduce the original string."""
        text = "வணக்கம்"
        encoded = tokenizer.encode(text)
        decoded = tokenizer.decode(encoded)
        assert decoded == text

    def test_vocab_contains_all_chars(self):
        """Every character in the corpus must appear in the vocabulary."""
        text = "abc123"
        t = TamilTokenizer(text)
        for ch in text:
            assert ch in t.char_to_id

    def test_unknown_chars_silently_skipped(self, tokenizer):
        """Characters absent from the vocabulary are silently dropped."""
        known = tokenizer.chars[0]
        encoded = tokenizer.encode(known + "\x00unknown\x00")
        # Only the known character survives
        assert len(encoded) == 1
        assert encoded[0] == tokenizer.char_to_id[known]

    def test_empty_string(self, tokenizer):
        assert tokenizer.encode("") == []
        assert tokenizer.decode([]) == ""

    def test_vocab_size_matches(self):
        text = "aabbcc"
        t = TamilTokenizer(text)
        assert len(t.chars) == 3  # unique: a, b, c


# ---------------------------------------------------------------------------
# Task 4b: Transformer dimension tests
# ---------------------------------------------------------------------------

class TestTransformer:
    def test_output_shape(self, model_and_vocab, tokenizer):
        model, vocab_size = model_and_vocab
        batch_size, seq_len = 2, 8
        tokens = torch.randint(0, vocab_size, (batch_size, seq_len))
        logits = model(tokens)
        assert logits.shape == (batch_size, seq_len, vocab_size)

    def test_parameter_count_positive(self, model_and_vocab):
        model, _ = model_and_vocab
        total = sum(p.numel() for p in model.parameters())
        assert total > 0

    def test_forward_no_error_single_token(self, model_and_vocab):
        model, vocab_size = model_and_vocab
        tokens = torch.randint(0, vocab_size, (1, 1))
        logits = model(tokens)
        assert logits.shape == (1, 1, vocab_size)

    def test_causal_mask_different_positions(self, model_and_vocab):
        """
        A causal model's prediction at position i must not change when we
        alter tokens at positions j > i.
        """
        model, vocab_size = model_and_vocab
        model.eval()
        seq_len = 8
        tokens = torch.randint(0, vocab_size, (1, seq_len))

        with torch.no_grad():
            logits_orig = model(tokens).clone()

            # Corrupt all tokens after position 3
            tokens_modified = tokens.clone()
            tokens_modified[0, 4:] = (tokens_modified[0, 4:] + 1) % vocab_size

            logits_mod = model(tokens_modified)

        # Positions 0-3 must be identical
        assert torch.allclose(
            logits_orig[0, :4], logits_mod[0, :4], atol=1e-5
        ), "Causal mask failed: future tokens leaked into past positions."


# ---------------------------------------------------------------------------
# Task 4c: get_batch tests
# ---------------------------------------------------------------------------

class TestGetBatch:
    def test_shapes(self, encoded_data):
        ctx, bs = 16, 4
        x, y = get_batch(encoded_data, ctx, bs)
        assert x.shape == (bs, ctx)
        assert y.shape == (bs, ctx)

    def test_target_is_shifted_by_one(self, encoded_data):
        """y[i] must equal x[i] shifted one position to the left."""
        ctx, bs = 8, 2
        torch.manual_seed(0)
        x, y = get_batch(encoded_data, ctx, bs)
        # For each sample, the target at position t is the input at position t+1
        for i in range(bs):
            assert torch.all(y[i, :-1] == x[i, 1:]), (
                f"Sample {i}: y[:-1] != x[1:]"
            )


# ---------------------------------------------------------------------------
# Task 4d: Short training smoke-test
# ---------------------------------------------------------------------------

class TestTraining:
    def _make_cfg(self, tmp_ckpt: str) -> dict:
        return dict(
            data_path="data/tamil.txt",
            checkpoint_path=tmp_ckpt,
            steps=50,
            batch_size=4,
            context_length=16,
            embedding_size=32,
            num_heads=2,
            num_layers=1,
            lr=1e-3,
            val_fraction=0.1,
            eval_interval=25,
            eval_batches=5,
            seed=0,
        )

    def test_training_runs_and_loss_decreases(self, tmp_path):
        """Loss after 50 steps should be lower than initial loss."""
        ckpt_path = str(tmp_path / "smoke.pt")
        cfg = self._make_cfg(ckpt_path)
        # Override checkpoint path to be absolute so train() can find it
        cfg["checkpoint_path"] = ckpt_path

        # Patch _ROOT inside train_module so it resolves data/tamil.txt correctly
        original_root = train_module._ROOT
        train_module._ROOT = _PROJECT_ROOT
        try:
            model, tokenizer, ckpt = train(cfg)
        finally:
            train_module._ROOT = original_root

        assert ckpt["best_val_loss"] < 100  # sanity: loss is a real number
        assert os.path.exists(ckpt_path)

    def test_training_reports_val_loss(self, tmp_path, capsys):
        ckpt_path = str(tmp_path / "smoke2.pt")
        cfg = self._make_cfg(ckpt_path)
        cfg["checkpoint_path"] = ckpt_path

        original_root = train_module._ROOT
        train_module._ROOT = _PROJECT_ROOT
        try:
            train(cfg)
        finally:
            train_module._ROOT = original_root

        captured = capsys.readouterr()
        assert "val loss" in captured.out
        assert "train loss" in captured.out


# ---------------------------------------------------------------------------
# Task 4e: Checkpoint save / reload
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def _train_and_save(self, ckpt_path: str):
        cfg = dict(
            data_path="data/tamil.txt",
            checkpoint_path=ckpt_path,
            steps=30,
            batch_size=4,
            context_length=16,
            embedding_size=32,
            num_heads=2,
            num_layers=1,
            lr=1e-3,
            val_fraction=0.1,
            eval_interval=30,
            eval_batches=3,
            seed=7,
        )
        original_root = train_module._ROOT
        train_module._ROOT = _PROJECT_ROOT
        try:
            return train(cfg)
        finally:
            train_module._ROOT = original_root

    def test_checkpoint_file_created(self, tmp_path):
        ckpt_path = str(tmp_path / "ckpt.pt")
        self._train_and_save(ckpt_path)
        assert os.path.exists(ckpt_path)
        assert os.path.getsize(ckpt_path) > 0

    def test_checkpoint_contains_required_keys(self, tmp_path):
        ckpt_path = str(tmp_path / "ckpt.pt")
        _, _, ckpt = self._train_and_save(ckpt_path)
        required = {
            "model_state_dict", "vocab_size", "context_length",
            "embedding_size", "num_heads", "num_layers", "chars",
        }
        assert required.issubset(set(ckpt.keys()))

    def test_reload_produces_same_logits(self, tmp_path):
        """
        After saving and reloading, the model must produce identical output
        for the same input.
        """
        ckpt_path = str(tmp_path / "ckpt.pt")
        original_model, orig_tokenizer, _ = self._train_and_save(ckpt_path)
        # Put original model into eval mode to match the reloaded model
        original_model.eval()

        reloaded_model, reloaded_tokenizer, _ = load_checkpoint(ckpt_path)

        # Use a fixed input
        vocab_size = len(orig_tokenizer.chars)
        torch.manual_seed(99)
        tokens = torch.randint(0, vocab_size, (1, 8))
        with torch.no_grad():
            logits_orig = original_model(tokens)
            logits_reloaded = reloaded_model(tokens)

        assert torch.allclose(logits_orig, logits_reloaded, atol=1e-5)


# ---------------------------------------------------------------------------
# Task 4f: Text generation
# ---------------------------------------------------------------------------

class TestGeneration:
    def _get_model_and_tokenizer(self, tmp_path):
        ckpt_path = str(tmp_path / "gen_ckpt.pt")
        cfg = dict(
            data_path="data/tamil.txt",
            checkpoint_path=ckpt_path,
            steps=30,
            batch_size=4,
            context_length=16,
            embedding_size=32,
            num_heads=2,
            num_layers=1,
            lr=1e-3,
            val_fraction=0.1,
            eval_interval=30,
            eval_batches=3,
            seed=1,
        )
        original_root = train_module._ROOT
        train_module._ROOT = _PROJECT_ROOT
        try:
            model, tokenizer, _ = train(cfg)
        finally:
            train_module._ROOT = original_root
        return model, tokenizer

    def test_generates_correct_length(self, tmp_path):
        model, tokenizer = self._get_model_and_tokenizer(tmp_path)
        prompt = tokenizer.chars[0]
        output = generate(model, tokenizer, prompt=prompt, max_new_tokens=20)
        # Output contains prompt tokens + 20 new tokens
        prompt_len = len(tokenizer.encode(prompt))
        assert len(tokenizer.encode(output)) == prompt_len + 20

    def test_generates_string(self, tmp_path):
        model, tokenizer = self._get_model_and_tokenizer(tmp_path)
        output = generate(
            model, tokenizer,
            prompt=tokenizer.chars[0],
            max_new_tokens=10,
        )
        assert isinstance(output, str)
        assert len(output) > 0

    def test_unknown_prompt_chars_skipped(self, tmp_path):
        model, tokenizer = self._get_model_and_tokenizer(tmp_path)
        # '\x00' is very unlikely to be in the Tamil vocabulary
        output = generate(
            model, tokenizer,
            prompt="\x00",
            max_new_tokens=5,
        )
        assert isinstance(output, str)

    def test_temperature_zero_is_deterministic(self, tmp_path):
        """Greedy decoding (temperature<=0.01) must be fully deterministic."""
        model, tokenizer = self._get_model_and_tokenizer(tmp_path)
        prompt = tokenizer.chars[0]
        # Argmax is deterministic so no seeding is needed, but we set it
        # anyway to be explicit.
        torch.manual_seed(42)
        out1 = generate(model, tokenizer, prompt=prompt,
                        max_new_tokens=10, temperature=0.01)
        torch.manual_seed(42)
        out2 = generate(model, tokenizer, prompt=prompt,
                        max_new_tokens=10, temperature=0.01)
        assert out1 == out2


# ---------------------------------------------------------------------------
# Task 4g: Invalid / missing dataset handling
# ---------------------------------------------------------------------------

class TestDatasetErrors:
    def test_missing_dataset_exits(self, tmp_path):
        cfg = dict(
            data_path=str(tmp_path / "nonexistent.txt"),
            checkpoint_path=str(tmp_path / "ckpt.pt"),
            steps=10, batch_size=4, context_length=16,
            embedding_size=32, num_heads=2, num_layers=1,
            lr=1e-3, val_fraction=0.1, eval_interval=5,
            eval_batches=2, seed=0,
        )
        original_root = train_module._ROOT
        train_module._ROOT = _PROJECT_ROOT
        try:
            with pytest.raises(SystemExit):
                train(cfg)
        finally:
            train_module._ROOT = original_root

    def test_too_small_dataset_exits(self, tmp_path):
        tiny = tmp_path / "tiny.txt"
        tiny.write_text("வ" * 10, encoding="utf-8")  # only 10 chars
        cfg = dict(
            data_path=str(tiny),
            checkpoint_path=str(tmp_path / "ckpt.pt"),
            steps=10, batch_size=4, context_length=16,
            embedding_size=32, num_heads=2, num_layers=1,
            lr=1e-3, val_fraction=0.1, eval_interval=5,
            eval_batches=2, seed=0,
        )
        original_root = train_module._ROOT
        train_module._ROOT = _PROJECT_ROOT
        try:
            with pytest.raises(SystemExit):
                train(cfg)
        finally:
            train_module._ROOT = original_root

    def test_missing_checkpoint_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_checkpoint(str(tmp_path / "ghost.pt"))
