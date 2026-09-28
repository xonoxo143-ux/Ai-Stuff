from __future__ import annotations

import torch
from torch import nn

BYTE_VOCAB = 256
INPUT_VOCAB = 257
BOS_ID = 256


class ConditionedByteModel(nn.Module):
    condition_dim: int

    def _condition(
        self,
        condition: torch.Tensor | None,
        batch: int,
        device,
        dtype,
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


class ByteGRU(ConditionedByteModel):
    def __init__(
        self,
        embedding_dim: int = 64,
        hidden_dim: int = 96,
        layers: int = 2,
        condition_dim: int = 16,
    ) -> None:
        super().__init__()
        self.condition_dim = condition_dim
        self.embedding = nn.Embedding(INPUT_VOCAB, embedding_dim)
        self.gru = nn.GRU(
            embedding_dim,
            hidden_dim,
            layers,
            batch_first=True,
        )
        self.condition_to_hidden = (
            nn.Linear(condition_dim, layers * hidden_dim)
            if condition_dim > 0
            else None
        )
        self.output = nn.Linear(hidden_dim, BYTE_VOCAB)
        self.layers = layers
        self.hidden_dim = hidden_dim

    def forward(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None = None,
    ) -> torch.Tensor:
        embedded = self.embedding(tokens)
        batch = tokens.shape[0]
        initial = None
        cond = self._condition(
            condition,
            batch,
            embedded.device,
            embedded.dtype,
        )
        if cond is not None:
            initial = torch.tanh(
                self.condition_to_hidden(cond)
            ).view(
                batch,
                self.layers,
                self.hidden_dim,
            ).transpose(0, 1).contiguous()
        hidden, _ = self.gru(embedded, initial)
        return self.output(hidden)


class ByteTransformer(ConditionedByteModel):
    def __init__(
        self,
        model_dim: int = 64,
        layers: int = 2,
        heads: int = 4,
        feedforward_dim: int = 192,
        max_length: int = 256,
        condition_dim: int = 16,
    ) -> None:
        super().__init__()
        self.condition_dim = condition_dim
        self.embedding = nn.Embedding(INPUT_VOCAB, model_dim)
        self.position = nn.Embedding(max_length, model_dim)
        self.condition_projection = (
            nn.Linear(condition_dim, model_dim)
            if condition_dim > 0
            else None
        )
        layer = nn.TransformerEncoderLayer(
            d_model=model_dim,
            nhead=heads,
            dim_feedforward=feedforward_dim,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.network = nn.TransformerEncoder(
            layer,
            num_layers=layers,
        )
        self.norm = nn.LayerNorm(model_dim)
        self.output = nn.Linear(model_dim, BYTE_VOCAB)

    def forward(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None = None,
    ) -> torch.Tensor:
        batch, length = tokens.shape
        positions = torch.arange(length, device=tokens.device)
        hidden = (
            self.embedding(tokens)
            + self.position(positions)[None]
        )
        cond = self._condition(
            condition,
            batch,
            hidden.device,
            hidden.dtype,
        )
        if cond is not None:
            hidden = (
                hidden
                + self.condition_projection(cond)[:, None, :]
            )
        mask = torch.triu(
            torch.full(
                (length, length),
                float("-inf"),
                device=tokens.device,
            ),
            diagonal=1,
        )
        hidden = self.network(
            hidden,
            mask=mask,
            is_causal=True,
        )
        return self.output(self.norm(hidden))


class BytePatchRNN(ConditionedByteModel):
    """First multiscale candidate: local byte GRU + slower patch state."""

    def __init__(
        self,
        embedding_dim: int = 48,
        local_hidden_dim: int = 72,
        global_hidden_dim: int = 96,
        patch_size: int = 4,
        condition_dim: int = 16,
    ) -> None:
        super().__init__()
        self.condition_dim = condition_dim
        self.patch_size = patch_size
        self.embedding = nn.Embedding(INPUT_VOCAB, embedding_dim)
        self.patch_encoder = nn.Sequential(
            nn.Linear(
                patch_size * embedding_dim,
                global_hidden_dim,
            ),
            nn.GELU(),
            nn.Linear(
                global_hidden_dim,
                global_hidden_dim,
            ),
        )
        self.global_cell = nn.GRUCell(
            global_hidden_dim,
            global_hidden_dim,
        )
        self.condition_to_global = (
            nn.Linear(
                condition_dim,
                global_hidden_dim,
            )
            if condition_dim > 0
            else None
        )
        self.global_to_local = nn.Linear(
            global_hidden_dim,
            local_hidden_dim,
        )
        self.local_gru = nn.GRU(
            embedding_dim,
            local_hidden_dim,
            batch_first=True,
        )
        self.output = nn.Linear(
            local_hidden_dim,
            BYTE_VOCAB,
        )
        self.bos_embedding = nn.Parameter(
            torch.zeros(embedding_dim)
        )

    def forward(
        self,
        tokens: torch.Tensor,
        condition: torch.Tensor | None = None,
    ) -> torch.Tensor:
        batch, length = tokens.shape
        if length % self.patch_size:
            raise ValueError(
                "sequence length must be divisible by patch_size"
            )
        embedded = self.embedding(tokens)
        cond = self._condition(
            condition,
            batch,
            embedded.device,
            embedded.dtype,
        )
        global_state = torch.zeros(
            batch,
            self.global_cell.hidden_size,
            device=embedded.device,
            dtype=embedded.dtype,
        )
        if cond is not None:
            global_state = torch.tanh(
                self.condition_to_global(cond)
            )

        logits: list[torch.Tensor] = []
        patch_size = self.patch_size
        for patch_index in range(
            length // patch_size
        ):
            patch = embedded[
                :,
                patch_index * patch_size
                : (patch_index + 1) * patch_size,
            ]
            local_input = torch.cat(
                [
                    self.bos_embedding.view(
                        1,
                        1,
                        -1,
                    ).expand(batch, 1, -1),
                    patch[:, :-1],
                ],
                dim=1,
            )
            local_initial = torch.tanh(
                self.global_to_local(global_state)
            ).unsqueeze(0)
            local_hidden, _ = self.local_gru(
                local_input,
                local_initial,
            )
            logits.append(
                self.output(local_hidden)
            )
            patch_summary = self.patch_encoder(
                patch.reshape(batch, -1)
            )
            global_state = self.global_cell(
                patch_summary,
                global_state,
            )
        return torch.cat(logits, dim=1)


def build_model(
    name: str,
    condition_dim: int = 16,
) -> ConditionedByteModel:
    if name == "gru":
        return ByteGRU(
            condition_dim=condition_dim
        )
    if name == "transformer":
        return ByteTransformer(
            condition_dim=condition_dim
        )
    if name == "patch_rnn":
        return BytePatchRNN(
            condition_dim=condition_dim
        )
    raise ValueError(f"unknown model: {name}")


def parameter_count(model: nn.Module) -> int:
    return sum(
        parameter.numel()
        for parameter in model.parameters()
    )
