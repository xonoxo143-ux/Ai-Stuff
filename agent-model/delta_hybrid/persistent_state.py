"""Explicit segmented-execution state for DeltaHybrid V1.

This wrapper does not change model parameters or the training forward path.
It carries recurrent Delta matrices plus exact-attention history across calls.
Resets are boundary resets: one boolean per batch row at segment start.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from .delta_chunk import chunk_parallel_scan
from .delta_reference import DeltaState, scan
from .model_v1 import DeltaHybridV1


@dataclass
class AttentionHistory:
    hidden: torch.Tensor
    valid: torch.Tensor


@dataclass
class DeltaHybridState:
    delta_states: tuple[DeltaState, ...]
    attention: AttentionHistory | None
def _reset_delta(
    state: DeltaState | None,
    reset_mask: torch.Tensor | None,
) -> DeltaState | None:
    if state is None or reset_mask is None:
        return state
    keep = (~reset_mask.bool()).to(state.memory.dtype).view(-1, 1, 1)
    return DeltaState(state.memory * keep)


def state_to_payload(state: DeltaHybridState) -> dict[str, Any]:
    """Create an owned, detached payload suitable for torch.save."""
    attention = None
    if state.attention is not None:
        attention = {
            "hidden": state.attention.hidden.detach().clone(),
            "valid": state.attention.valid.detach().clone(),
        }
    return {
        "schema_version": 1,
        "delta": [s.memory.detach().clone() for s in state.delta_states],
        "attention": attention,
    }


def state_from_payload(payload: dict[str, Any]) -> DeltaHybridState:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported DeltaHybrid state schema")
    delta = tuple(DeltaState(t.clone()) for t in payload["delta"])
    raw_attention = payload.get("attention")
    attention = None
    if raw_attention is not None:
        attention = AttentionHistory(
            raw_attention["hidden"].clone(),
            raw_attention["valid"].clone().bool(),
        )
    return DeltaHybridState(delta, attention)


def state_size_bytes(state: DeltaHybridState) -> int:
    tensors = [s.memory for s in state.delta_states]
    if state.attention is not None:
        tensors.extend([state.attention.hidden, state.attention.valid])
    return sum(t.numel() * t.element_size() for t in tensors)


class StatefulDeltaHybridV1:
    """State-carrying execution view over an existing DeltaHybridV1."""

    def __init__(
        self,
        model: DeltaHybridV1,
        max_attention_history: int | None = None,
    ) -> None:
        self.model = model
        if max_attention_history is not None and max_attention_history < 0:
            raise ValueError("max_attention_history must be >= 0 or None")
        self.max_attention_history = max_attention_history

    def _run_delta_block(
        self,
        block,
        x: torch.Tensor,
        state: DeltaState | None,
        reset_mask: torch.Tensor | None,
    ) -> tuple[torch.Tensor, DeltaState]:
        state = _reset_delta(state, reset_mask)
        h = block.norm1(x)
        q, k, v = block.qkv(h).chunk(3, dim=-1)
        gate_logits = block.gates(h)
        beta = torch.sigmoid(gate_logits[..., 0])
        decay = torch.sigmoid(gate_logits[..., 1])

        if block.execution == "reference":
            mixed, new_state = scan(
                q, k, v, beta, decay, state=state
            )
        else:
            mixed, new_state = chunk_parallel_scan(
                q,
                k,
                v,
                beta,
                decay,
                state=state,
                chunk_size=block.chunk_size,
            )
        x = x + block.out_proj(mixed)
        x = x + block.ff(block.norm2(x))
        return x, new_state

    @staticmethod
    def _validate_reset(
        reset_mask: torch.Tensor | None,
        batch: int,
        device: torch.device,
    ) -> torch.Tensor | None:
        if reset_mask is None:
            return None
        if reset_mask.shape != (batch,):
            raise ValueError(
                f"reset_mask must be {(batch,)}, got {tuple(reset_mask.shape)}"
            )
        return reset_mask.to(device=device, dtype=torch.bool)

    def _run_attention(
        self,
        x: torch.Tensor,
        cache: AttentionHistory | None,
        reset_mask: torch.Tensor | None,
    ) -> tuple[torch.Tensor, AttentionHistory]:
        block = self.model.exact_attention
        h = block.norm1(x)
        batch, length, dim = h.shape

        if cache is not None:
            if cache.hidden.shape[0] != batch or cache.hidden.shape[2] != dim:
                raise ValueError("attention cache shape does not match batch/model")
            if cache.valid.shape != cache.hidden.shape[:2]:
                raise ValueError("attention validity mask shape is invalid")
            if reset_mask is not None and bool(reset_mask.all()):
                cache = None

        if cache is None:
            mask = torch.triu(
                torch.full(
                    (length, length),
                    float("-inf"),
                    device=h.device,
                    dtype=h.dtype,
                ),
                diagonal=1,
            )
            recalled, _ = block.attn(
                h,
                h,
                h,
                attn_mask=mask,
                need_weights=False,
                is_causal=True,
            )
            keys = h
            valid = torch.ones(
                batch, length, device=h.device, dtype=torch.bool
            )
        else:
            cached_valid = cache.valid.to(device=h.device).bool()
            if reset_mask is not None:
                cached_valid = cached_valid & (~reset_mask[:, None])
            keys = torch.cat([cache.hidden.to(h.device), h], dim=1)
            current_valid = torch.ones(
                batch, length, device=h.device, dtype=torch.bool
            )
            valid = torch.cat([cached_valid, current_valid], dim=1)
            past = cache.hidden.shape[1]
            key_pos = torch.arange(keys.shape[1], device=h.device)[None, :]
            query_pos = (
                past + torch.arange(length, device=h.device)[:, None]
            )
            future = key_pos > query_pos
            attn_mask = torch.zeros(
                length,
                keys.shape[1],
                device=h.device,
                dtype=h.dtype,
            ).masked_fill(future, float("-inf"))

            key_padding = None
            if not bool(valid.all()):
                key_padding = torch.zeros(
                    batch,
                    keys.shape[1],
                    device=h.device,
                    dtype=h.dtype,
                ).masked_fill(~valid, float("-inf"))

            recalled, _ = block.attn(
                h,
                keys,
                keys,
                attn_mask=attn_mask,
                key_padding_mask=key_padding,
                need_weights=False,
                is_causal=False,
            )
        x = x + recalled
        x = x + block.ff(block.norm2(x))

        next_keys = keys
        next_valid = valid
        if self.max_attention_history is not None:
            keep = min(self.max_attention_history, keys.shape[1])
            if keep == 0:
                next_keys = keys[:, :0]
                next_valid = valid[:, :0]
            else:
                next_keys = keys[:, -keep:]
                next_valid = valid[:, -keep:]

        return x, AttentionHistory(next_keys, next_valid)

    def forward_segment(
        self,
        tokens: torch.Tensor,
        state: DeltaHybridState | None = None,
        condition: torch.Tensor | None = None,
        reset_mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, DeltaHybridState]:
        """Run one segment and return logits plus the continuation state."""
        batch, _ = tokens.shape
        reset_mask = self._validate_reset(
            reset_mask, batch, tokens.device
        )
        hidden = self.model.embedding(tokens)
        cond = self.model._condition(
            condition,
            batch,
            hidden.device,
            hidden.dtype,
        )
        if cond is not None:
            hidden = hidden + self.model.condition_projection(cond)[:, None, :]

        if state is None:
            prior_delta = (None,) * len(self.model.delta_blocks)
            prior_attention = None
        else:
            if len(state.delta_states) != len(self.model.delta_blocks):
                raise ValueError("Delta state count does not match model")
            prior_delta = state.delta_states
            prior_attention = state.attention

        next_delta = []
        for block, block_state in zip(
            self.model.delta_blocks, prior_delta
        ):
            hidden, block_state = self._run_delta_block(
                block,
                hidden,
                block_state,
                reset_mask,
            )
            next_delta.append(block_state)

        hidden, next_attention = self._run_attention(
            hidden,
            prior_attention,
            reset_mask,
        )
        logits = self.model.output(self.model.norm(hidden))
        return logits, DeltaHybridState(
            tuple(next_delta),
            next_attention,
        )
