from __future__ import annotations

from dataclasses import dataclass, field

import torch
from torch import nn

BYTE_VOCAB = 256
INPUT_VOCAB = 257
BOS_ID = 256


@dataclass
class StreamState:
    global_state: torch.Tensor
    condition: torch.Tensor | None
    history: list[torch.Tensor] = field(default_factory=list)
    patch_bytes: list[int] = field(default_factory=list)
    local_hidden: torch.Tensor | None = None
    next_logits: torch.Tensor | None = None


class BytePatchHybridV0(nn.Module):
    """V0 language core: local byte patches + recurrent state + bounded access."""

    def __init__(
        self,
        embedding_dim: int = 96,
        local_hidden_dim: int = 160,
        global_hidden_dim: int = 256,
        patch_size: int = 4,
        attention_heads: int = 4,
        attention_patches: int = 64,
        condition_dim: int = 16,
    ) -> None:
        super().__init__()
        if global_hidden_dim % attention_heads:
            raise ValueError("global_hidden_dim must divide attention_heads")
        self.embedding_dim = embedding_dim
        self.local_hidden_dim = local_hidden_dim
        self.global_hidden_dim = global_hidden_dim
        self.patch_size = patch_size
        self.attention_patches = attention_patches
        self.condition_dim = condition_dim
        self.vectorized_forward = False

        self.embedding = nn.Embedding(INPUT_VOCAB, embedding_dim)
        self.patch_encoder = nn.Sequential(
            nn.Linear(patch_size * embedding_dim, global_hidden_dim),
            nn.GELU(),
            nn.Linear(global_hidden_dim, global_hidden_dim),
        )
        self.global_cell = nn.GRUCell(global_hidden_dim, global_hidden_dim)
        self.precise_access = nn.MultiheadAttention(
            global_hidden_dim,
            attention_heads,
            batch_first=True,
        )
        self.access_norm = nn.LayerNorm(global_hidden_dim)
        self.global_to_local = nn.Linear(global_hidden_dim, local_hidden_dim)
        self.local_gru = nn.GRU(
            embedding_dim,
            local_hidden_dim,
            batch_first=True,
        )
        self.output = nn.Linear(local_hidden_dim, BYTE_VOCAB)
        self.bos_embedding = nn.Parameter(torch.zeros(embedding_dim))
        self.initial_global = nn.Parameter(torch.zeros(1, global_hidden_dim))

        self.condition_to_global = self._projection(condition_dim, global_hidden_dim)
        self.condition_to_local = self._projection(condition_dim, embedding_dim)
        self.condition_to_patch = self._projection(condition_dim, global_hidden_dim)

    @staticmethod
    def _projection(source: int, target: int) -> nn.Module | None:
        if source <= 0:
            return None
        return nn.Linear(source, target, bias=False)

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
            return torch.zeros(batch, self.condition_dim, device=device, dtype=dtype)
        if condition.shape != (batch, self.condition_dim):
            raise ValueError(
                f"condition must be {(batch, self.condition_dim)}, "
                f"got {tuple(condition.shape)}"
            )
        return condition.to(device=device, dtype=dtype)

    def _initial_global(self, batch: int, cond: torch.Tensor | None) -> torch.Tensor:
        state = self.initial_global.expand(batch, -1)
        if cond is not None:
            state = state + self.condition_to_global(cond)
        return torch.tanh(state)

    def _access(
        self,
        global_state: torch.Tensor,
        history: list[torch.Tensor],
    ) -> torch.Tensor:
        if not history:
            return global_state
        memory = torch.stack(history[-self.attention_patches :], dim=1)
        query = global_state.unsqueeze(1)
        recalled, _ = self.precise_access(
            query,
            memory,
            memory,
            need_weights=False,
        )
        return self.access_norm(global_state + recalled[:, 0])

    def _local_inputs(
        self,
        patch: torch.Tensor,
        cond: torch.Tensor | None,
    ) -> torch.Tensor:
        embedded = self.embedding(patch)
        if cond is not None:
            embedded = embedded + self.condition_to_local(cond)[:, None, :]
        return embedded

    def _encode_patch(
        self,
        patch: torch.Tensor,
        cond: torch.Tensor | None,
    ) -> torch.Tensor:
        embedded = self.embedding(patch)
        summary = self.patch_encoder(embedded.reshape(patch.shape[0], -1))
        if cond is not None:
            summary = summary + self.condition_to_patch(cond)
        return summary

    def set_vectorized_forward(self, enabled: bool = True) -> "BytePatchHybridV0":
        """Use the cloud-oriented training forward without changing parameters."""
        self.vectorized_forward = bool(enabled)
        return self

    def _forward_reference(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None,
    ) -> torch.Tensor:
        batch, length = tokens.shape
        cond = self._condition(
            condition,
            batch,
            self.embedding.weight.device,
            self.embedding.weight.dtype,
        )
        global_state = self._initial_global(batch, cond)
        history: list[torch.Tensor] = []
        outputs: list[torch.Tensor] = []

        for start in range(0, length, self.patch_size):
            patch = tokens[:, start : start + self.patch_size]
            context = self._access(global_state, history)
            local_initial = torch.tanh(
                self.global_to_local(context)
            ).unsqueeze(0)
            local_hidden, _ = self.local_gru(
                self._local_inputs(patch, cond),
                local_initial,
            )
            outputs.append(self.output(local_hidden))
            patch_summary = self._encode_patch(patch, cond)
            global_state = self.global_cell(patch_summary, global_state)
            history.append(patch_summary)

        return torch.cat(outputs, dim=1)

    def _forward_vectorized(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None,
    ) -> torch.Tensor:
        batch, length = tokens.shape
        patch_count = length // self.patch_size
        cond = self._condition(
            condition,
            batch,
            self.embedding.weight.device,
            self.embedding.weight.dtype,
        )
        patches = tokens.reshape(batch, patch_count, self.patch_size)
        flat_patches = patches.reshape(batch * patch_count, self.patch_size)
        flat_cond = (
            None
            if cond is None
            else cond[:, None, :].expand(-1, patch_count, -1).reshape(
                batch * patch_count,
                self.condition_dim,
            )
        )

        patch_summaries = self._encode_patch(
            flat_patches,
            flat_cond,
        ).reshape(batch, patch_count, self.global_hidden_dim)
        local_inputs = self._local_inputs(
            flat_patches,
            flat_cond,
        ).reshape(
            batch,
            patch_count,
            self.patch_size,
            self.embedding_dim,
        )

        global_state = self._initial_global(batch, cond)
        history: list[torch.Tensor] = []
        contexts: list[torch.Tensor] = []
        for index in range(patch_count):
            contexts.append(self._access(global_state, history))
            patch_summary = patch_summaries[:, index]
            global_state = self.global_cell(patch_summary, global_state)
            history.append(patch_summary)

        context_tensor = torch.stack(contexts, dim=1)
        local_initial = torch.tanh(
            self.global_to_local(context_tensor)
        ).reshape(batch * patch_count, self.local_hidden_dim).unsqueeze(0)
        local_hidden, _ = self.local_gru(
            local_inputs.reshape(
                batch * patch_count,
                self.patch_size,
                self.embedding_dim,
            ),
            local_initial,
        )
        logits = self.output(local_hidden).reshape(
            batch,
            length,
            BYTE_VOCAB,
        )
        return logits

    def forward(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None = None,
    ) -> torch.Tensor:
        _, length = tokens.shape
        if length % self.patch_size:
            raise ValueError("sequence length must be divisible by patch_size")
        if self.vectorized_forward:
            return self._forward_vectorized(tokens, condition)
        return self._forward_reference(tokens, condition)

    def _reset_stream_patch(self, state: StreamState) -> None:
        context = self._access(state.global_state, state.history)
        state.local_hidden = torch.tanh(
            self.global_to_local(context)
        ).unsqueeze(0)

    def _start_stream(self, state: StreamState) -> None:
        self._reset_stream_patch(state)
        batch = state.global_state.shape[0]
        token = self.bos_embedding.view(1, 1, -1).expand(batch, 1, -1)
        if state.condition is not None:
            token = token + self.condition_to_local(state.condition)[:, None, :]
        out, _ = self.local_gru(token, state.local_hidden)
        state.next_logits = self.output(out[:, -1])

    @torch.no_grad()
    def begin_stream(
        self,
        condition: torch.Tensor | None = None,
    ) -> StreamState:
        device = self.embedding.weight.device
        dtype = self.embedding.weight.dtype
        cond = self._condition(condition, 1, device, dtype)
        state = StreamState(
            global_state=self._initial_global(1, cond),
            condition=cond,
        )
        self._start_stream(state)
        return state

    @torch.no_grad()
    def accept_byte(self, state: StreamState, value: int) -> None:
        value = int(value)
        if not 0 <= value < 256:
            raise ValueError("stream byte must be in [0, 255]")
        token = torch.tensor(
            [[value]],
            device=self.embedding.weight.device,
            dtype=torch.long,
        )
        embedded = self.embedding(token)
        if state.condition is not None:
            embedded = embedded + self.condition_to_local(state.condition)[:, None, :]
        out, hidden = self.local_gru(embedded, state.local_hidden)
        state.local_hidden = hidden
        state.next_logits = self.output(out[:, -1])
        state.patch_bytes.append(value)

        if len(state.patch_bytes) == self.patch_size:
            patch = torch.tensor(
                [state.patch_bytes],
                device=self.embedding.weight.device,
                dtype=torch.long,
            )
            summary = self._encode_patch(patch, state.condition)
            state.global_state = self.global_cell(summary, state.global_state)
            state.history.append(summary)
            if len(state.history) > self.attention_patches:
                state.history = state.history[-self.attention_patches :]
            state.patch_bytes.clear()
            self._reset_stream_patch(state)

    @torch.no_grad()
    def generate(
        self,
        prompt: str | bytes,
        *,
        max_new_bytes: int = 128,
        condition: torch.Tensor | None = None,
    ) -> bytes:
        prefix = prompt.encode("utf-8") if isinstance(prompt, str) else bytes(prompt)
        state = self.begin_stream(condition)
        for value in prefix:
            self.accept_byte(state, value)

        generated = bytearray()
        for _ in range(max_new_bytes):
            value = int(state.next_logits.argmax(dim=-1).item())
            generated.append(value)
            self.accept_byte(state, value)
        return prefix + bytes(generated)


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
