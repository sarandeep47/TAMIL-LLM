
import torch
import torch.nn as nn
import torch.nn.functional as F


class TinyTamilGPT(nn.Module):
    def __init__(
        self,
        vocab_size,
        context_length=64,
        embedding_size=64,
        num_heads=2,
        num_layers=2,
    ):
        super().__init__()

        self.context_length = context_length

        self.token_embedding = nn.Embedding(
            vocab_size, embedding_size
        )
        self.position_embedding = nn.Embedding(
            context_length, embedding_size
        )

        layer = nn.TransformerEncoderLayer(
            d_model=embedding_size,
            nhead=num_heads,
            dim_feedforward=128,
            batch_first=True,
            activation="gelu",
        )

        self.transformer = nn.TransformerEncoder(
            layer, num_layers=num_layers
        )

        self.output_layer = nn.Linear(
            embedding_size, vocab_size
        )

    def forward(self, tokens):
        batch_size, sequence_length = tokens.shape

        positions = torch.arange(
            sequence_length, device=tokens.device
        )

        x = (
            self.token_embedding(tokens)
            + self.position_embedding(positions)
        )

        # Prevent each position from seeing future tokens.
        mask = torch.triu(
            torch.ones(
                sequence_length,
                sequence_length,
                device=tokens.device,
                dtype=torch.bool,
            ),
            diagonal=1,
        )

        x = self.transformer(x, mask=mask)
        logits = self.output_layer(x)

        return logits
