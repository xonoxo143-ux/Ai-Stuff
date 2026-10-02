"""Raw-byte DeltaHybrid V1: 3 Gated-Delta blocks + 1 causal attention block."""
from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F

from .delta_chunk import chunk_parallel_scan

BYTE_VOCAB = 256
INPUT_VOCAB = 257
CONTROL_PARAMETERS = 1_051_232


class FeedForward(nn.Module):
    def __init__(self, model_dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.in_proj = nn.Linear(model_dim, hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, model_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.out_proj(F.gelu(self.in_proj(x)))
class DeltaBlock(nn.Module):
    def __init__(
        self,
        model_dim: int,
        feedforward_dim: int,
        chunk_size: int,
    ) -> None:
        super().__init__()
        self.chunk_size = int(chunk_size)
        self.norm1 = nn.LayerNorm(model_dim)
        self.qkv = nn.Linear(model_dim, model_dim * 3)
        self.gates = nn.Linear(model_dim, 2)
        self.out_proj = nn.Linear(model_dim, model_dim)
        self.norm2 = nn.LayerNorm(model_dim)
        self.ff = FeedForward(model_dim, feedforward_dim)

        nn.init.zeros_(self.gates.weight)
        with torch.no_grad():
            self.gates.bias[0] = 0.0
            self.gates.bias[1] = 4.0

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.norm1(x)
        q, k, v = self.qkv(h).chunk(3, dim=-1)
        gate_logits = self.gates(h)
        beta = torch.sigmoid(gate_logits[..., 0])
        decay = torch.sigmoid(gate_logits[..., 1])
        mixed, _ = chunk_parallel_scan(
            q,
            k,
            v,
            beta,
            decay,
            chunk_size=self.chunk_size,
        )
        x = x + self.out_proj(mixed)
        return x + self.ff(self.norm2(x))


class ExactAttentionBlock(nn.Module):
    def __init__(
        self,
        model_dim: int,
        heads: int,
        feedforward_dim: int,
    ) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(model_dim)
        self.attn = nn.MultiheadAttention(
            model_dim,
            heads,
            dropout=0.0,
            batch_first=True,
        )
        self.norm2 = nn.LayerNorm(model_dim)
        self.ff = FeedForward(model_dim, feedforward_dim)
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.norm1(x)
        length = h.shape[1]
        mask = torch.triu(
            torch.full(
                (length, length),
                float("-inf"),
                device=h.device,
                dtype=h.dtype,
            ),
            diagonal=1,
        )
        recalled, _ = self.attn(
            h,
            h,
            h,
            attn_mask=mask,
            need_weights=False,
            is_causal=True,
        )
        x = x + recalled
        return x + self.ff(self.norm2(x))


class DeltaHybridV1(nn.Module):
    """First parameter-matched raw-byte DeltaHybrid challenger."""
    def __init__(
        self,
        model_dim: int = 156,
        feedforward_dim: int = 468,
        heads: int = 6,
        condition_dim: int = 16,
        chunk_size: int = 64,
    ) -> None:
        super().__init__()
        if model_dim % heads:
            raise ValueError("model_dim must be divisible by heads")
        self.model_dim = int(model_dim)
        self.feedforward_dim = int(feedforward_dim)
        self.condition_dim = int(condition_dim)
        self.chunk_size = int(chunk_size)

        self.embedding = nn.Embedding(INPUT_VOCAB, model_dim)
        self.condition_projection = (
            nn.Linear(condition_dim, model_dim, bias=False)
            if condition_dim > 0
            else None
        )
        self.delta_blocks = nn.ModuleList(
            [
                DeltaBlock(model_dim, feedforward_dim, chunk_size)
                for _ in range(3)
            ]
        )
        self.exact_attention = ExactAttentionBlock(
            model_dim,
            heads,
            feedforward_dim,
        )
        self.norm = nn.LayerNorm(model_dim)
        self.output = nn.Linear(model_dim, BYTE_VOCAB)

    def _condition(
        self,
        condition: torch.Tensor | None,
        batch: int,
        device: torch.device,
        dtype: torch.dtype,
    ) -> torch.Tensor | None:
        if self.condition_dim <= 0:
            return None
        if condition is None:
            return torch.zeros(
                batch,
                self.condition_dim,
                device=device,
                dtype=dtype,
            )
        if condition.shape != (batch, self.condition_dim):
            raise ValueError(
                f"condition must be {(batch, self.condition_dim)}, "
                f"got {tuple(condition.shape)}"
            )
        return condition.to(device=device, dtype=dtype)

    def forward(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None = None,
    ) -> torch.Tensor:
        batch, _ = tokens.shape
        hidden = self.embedding(tokens)
        cond = self._condition(
            condition,
            batch,
            hidden.device,
            hidden.dtype,
        )
        if cond is not None:
            hidden = hidden + self.condition_projection(cond)[:, None, :]

        for block in self.delta_blocks:
            hidden = block(hidden)
        hidden = self.exact_attention(hidden)
        return self.output(self.norm(hidden))


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
