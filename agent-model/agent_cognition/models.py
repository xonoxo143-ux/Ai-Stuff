from __future__ import annotations

import torch
from torch import nn

from .benchmark import MAX_OPERATOR, MAX_POSITION, MAX_SLOTS, MAX_SYMBOL

ANSWER_VOCAB = MAX_SYMBOL + 1


class SlotEncoder(nn.Module):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self.kind = nn.Embedding(8, dim)
        self.symbol = nn.Embedding(MAX_SYMBOL + 1, dim)
        self.a_proj = nn.Linear(dim, dim, bias=False)
        self.b_proj = nn.Linear(dim, dim, bias=False)
        self.c_proj = nn.Linear(dim, dim, bias=False)
        self.op = nn.Embedding(MAX_OPERATOR + 1, dim)
        self.pos = nn.Embedding(MAX_POSITION + 1, dim)
        self.norm = nn.LayerNorm(dim)

    def forward(self, slots: torch.Tensor) -> torch.Tensor:
        kind, a, b, c, op, pos = slots.unbind(-1)
        return self.norm(
            self.kind(kind)
            + self.a_proj(self.symbol(a))
            + self.b_proj(self.symbol(b))
            + self.c_proj(self.symbol(c))
            + self.op(op)
            + self.pos(pos.clamp_max(MAX_POSITION))
        )


class FlatMLP(nn.Module):
    def __init__(self, dim: int = 48, hidden: int = 256) -> None:
        super().__init__()
        self.encoder = SlotEncoder(dim)
        self.net = nn.Sequential(
            nn.Linear(MAX_SLOTS * dim, hidden),
            nn.GELU(),
            nn.Linear(hidden, hidden),
            nn.GELU(),
            nn.Linear(hidden, ANSWER_VOCAB),
        )

    def forward(self, slots: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(slots) * mask.unsqueeze(-1)
        return self.net(encoded.flatten(1))


class FactorGraphCore(nn.Module):
    def __init__(
        self,
        dim: int = 64,
        steps: int = 6,
        reinject: bool = True,
    ) -> None:
        super().__init__()
        self.encoder = SlotEncoder(dim)
        self.steps = int(steps)
        self.reinject = bool(reinject)

        self.to_symbol = nn.ModuleList(
            [nn.Linear(dim, dim, bias=False) for _ in range(3)]
        )
        self.from_symbol = nn.ModuleList(
            [nn.Linear(dim, dim, bias=False) for _ in range(3)]
        )
        self.slot_global = nn.Linear(dim, dim, bias=False)
        self.symbol_update = nn.GRUCell(dim, dim)
        self.slot_update = nn.GRUCell(dim, dim)
        self.symbol_norm = nn.LayerNorm(dim)
        self.slot_norm = nn.LayerNorm(dim)

        self.query_proj = nn.Linear(dim, dim, bias=False)
        self.answer_proj = nn.Linear(dim, dim, bias=False)
        self.output_bias = nn.Parameter(torch.zeros(ANSWER_VOCAB))

    @staticmethod
    def _scatter_role(
        messages: torch.Tensor,
        ids: torch.Tensor,
        valid: torch.Tensor,
        vocab: int,
    ):
        batch, _slots, dim = messages.shape
        out = torch.zeros(
            batch,
            vocab,
            dim,
            device=messages.device,
            dtype=messages.dtype,
        )
        count = torch.zeros(
            batch,
            vocab,
            1,
            device=messages.device,
            dtype=messages.dtype,
        )
        expanded_ids = ids.unsqueeze(-1).expand(-1, -1, dim)
        weighted = messages * valid.unsqueeze(-1).to(messages.dtype)
        out.scatter_add_(1, expanded_ids, weighted)
        count.scatter_add_(
            1,
            ids.unsqueeze(-1),
            valid.unsqueeze(-1).to(messages.dtype),
        )
        return out, count

    @staticmethod
    def _gather_symbols(
        symbols: torch.Tensor,
        ids: torch.Tensor,
    ) -> torch.Tensor:
        dim = symbols.shape[-1]
        return torch.gather(
            symbols,
            1,
            ids.unsqueeze(-1).expand(-1, -1, dim),
        )

    def forward(
        self,
        slots: torch.Tensor,
        mask: torch.Tensor,
        *,
        steps: int | None = None,
    ) -> torch.Tensor:
        slot_init = self.encoder(slots) * mask.unsqueeze(-1)
        slot_state = slot_init
        batch, slot_count, dim = slot_state.shape
        vocab = ANSWER_VOCAB

        symbol_init = self.encoder.symbol.weight[:vocab][None].expand(
            batch, -1, -1
        )
        symbol_state = symbol_init
        role_ids = [slots[..., 1], slots[..., 2], slots[..., 3]]

        for _ in range(self.steps if steps is None else int(steps)):
            total = torch.zeros_like(symbol_state)
            counts = torch.zeros(
                batch,
                vocab,
                1,
                device=slot_state.device,
                dtype=slot_state.dtype,
            )

            for role, ids in enumerate(role_ids):
                valid = mask & ids.ne(0)
                messages = self.to_symbol[role](slot_state)
                part, part_count = self._scatter_role(
                    messages,
                    ids,
                    valid,
                    vocab,
                )
                total = total + part
                counts = counts + part_count

            symbol_message = total / counts.clamp_min(1.0)
            if self.reinject:
                symbol_message = symbol_message + symbol_init

            symbol_state = self.symbol_update(
                symbol_message.reshape(batch * vocab, dim),
                symbol_state.reshape(batch * vocab, dim),
            ).view(batch, vocab, dim)
            symbol_state = self.symbol_norm(symbol_state)

            incoming = torch.zeros_like(slot_state)
            for role, ids in enumerate(role_ids):
                gathered = self._gather_symbols(symbol_state, ids)
                incoming = incoming + (
                    self.from_symbol[role](gathered)
                    * ids.ne(0).unsqueeze(-1)
                )

            valid_slots = mask.unsqueeze(-1).to(slot_state.dtype)
            global_context = (
                self.slot_global(slot_state) * valid_slots
            ).sum(1) / valid_slots.sum(1).clamp_min(1.0)
            incoming = incoming + global_context[:, None, :]
            if self.reinject:
                incoming = incoming + slot_init

            slot_state = self.slot_update(
                incoming.reshape(batch * slot_count, dim),
                slot_state.reshape(batch * slot_count, dim),
            ).view(batch, slot_count, dim)
            slot_state = self.slot_norm(slot_state) * valid_slots

        query_mask = slots[..., 0].eq(6)
        query_index = query_mask.float().argmax(1)
        query = slot_state[
            torch.arange(batch, device=slots.device),
            query_index,
        ]

        query_key = self.query_proj(query)
        answer_keys = self.answer_proj(symbol_state)
        logits = torch.einsum(
            "bd,bvd->bv",
            query_key,
            answer_keys,
        ) / (dim ** 0.5)
        logits = logits + self.output_bias
        logits[:, 0] = -1e9
        return logits


def build_model(name: str):
    if name == "flat":
        return FlatMLP()
    if name == "factor_onepass":
        return FactorGraphCore(steps=1)
    if name == "factor":
        return FactorGraphCore(steps=6, reinject=True)
    if name == "factor_no_reinject":
        return FactorGraphCore(steps=6, reinject=False)
    raise ValueError(name)


def parameter_count(model: nn.Module) -> int:
    return sum(
        parameter.numel()
        for parameter in model.parameters()
    )
