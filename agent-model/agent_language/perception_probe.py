from __future__ import annotations

import argparse
import itertools
import json
import random
from statistics import mean
from time import perf_counter

import torch
from torch import nn
import torch.nn.functional as F


NAMES = ("Mia", "Leo", "Ava", "Ivy")
COLORS = ("red", "tan", "sky", "ash")
ANIMALS = ("cat", "dog", "fox", "owl")
PLACES = ("park", "hill", "yard", "home")
SLOTS = (NAMES, COLORS, ANIMALS, PLACES)

TRAIN_TEMPLATES = (
    "{name} saw a {color} {animal} near the {place}.",
    "Near the {place}, {name} noticed a {color} {animal}.",
    "{name} found the {color} {animal} by the {place}.",
    "A {color} {animal} was beside the {place}, and {name} saw it.",
    "{name} spotted a {color} {animal} close to the {place}.",
)

VALID_TEMPLATES = (
    "By the {place} was a {color} {animal}; {name} noticed it.",
    "The {color} {animal} near the {place} was seen by {name}.",
    "{name} came across a {color} {animal} around the {place}.",
)


def semantic_split():
    all_items = list(itertools.product(*SLOTS))
    valid = [
        item
        for item in all_items
        if (
            sum(
                values.index(value)
                for values, value
                in zip(SLOTS, item)
            )
            % 4
            == 0
        )
    ]
    valid_set = set(valid)
    train = [
        item
        for item in all_items
        if item not in valid_set
    ]
    return train, valid


def render(item, template: str) -> str:
    name, color, animal, place = item
    return template.format(
        name=name,
        color=color,
        animal=animal,
        place=place,
    )


def semantic_labels(item) -> torch.Tensor:
    return torch.tensor(
        [
            values.index(value)
            for values, value
            in zip(SLOTS, item)
        ],
        dtype=torch.long,
    )


def encode_bytes(
    texts: list[str],
) -> tuple[torch.Tensor, torch.Tensor]:
    sequences = [
        list(text.encode("utf-8"))
        for text in texts
    ]
    length = max(
        len(sequence)
        for sequence in sequences
    )
    tokens = torch.zeros(
        len(sequences),
        length,
        dtype=torch.long,
    )
    mask = torch.zeros(
        len(sequences),
        length,
        dtype=torch.bool,
    )
    for index, sequence in enumerate(sequences):
        tokens[
            index,
            : len(sequence),
        ] = torch.tensor(
            sequence,
            dtype=torch.long,
        )
        mask[
            index,
            : len(sequence),
        ] = True
    return tokens, mask


class ByteGRUPerceiver(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 48,
        hidden_dim: int = 96,
        layers: int = 2,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(
            256,
            embedding_dim,
        )
        self.gru = nn.GRU(
            embedding_dim,
            hidden_dim,
            layers,
            batch_first=True,
        )
        self.head = nn.Linear(
            hidden_dim,
            16,
        )

    def forward(
        self,
        tokens: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        embedded = self.embedding(tokens)
        lengths = mask.sum(1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded,
            lengths,
            batch_first=True,
            enforce_sorted=False,
        )
        _, hidden = self.gru(packed)
        return self.head(
            hidden[-1]
        ).view(-1, 4, 4)


class ByteBiGRUPerceiver(nn.Module):
    def __init__(
        self,
        embedding_dim: int = 48,
        hidden_dim: int = 64,
        layers: int = 2,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(
            256,
            embedding_dim,
        )
        self.gru = nn.GRU(
            embedding_dim,
            hidden_dim,
            layers,
            batch_first=True,
            bidirectional=True,
        )
        self.head = nn.Linear(
            hidden_dim * 2,
            16,
        )

    def forward(
        self,
        tokens: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        embedded = self.embedding(tokens)
        lengths = mask.sum(1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded,
            lengths,
            batch_first=True,
            enforce_sorted=False,
        )
        _, hidden = self.gru(packed)
        state = torch.cat(
            [
                hidden[-2],
                hidden[-1],
            ],
            dim=-1,
        )
        return self.head(
            state
        ).view(-1, 4, 4)


class ByteAttentiveBiGRUPerceiver(nn.Module):
    """BiGRU sequence encoder with one learned query per semantic slot."""

    def __init__(
        self,
        embedding_dim: int = 48,
        hidden_dim: int = 64,
        layers: int = 2,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(
            256,
            embedding_dim,
        )
        self.gru = nn.GRU(
            embedding_dim,
            hidden_dim,
            layers,
            batch_first=True,
            bidirectional=True,
        )
        width = hidden_dim * 2
        self.queries = nn.Parameter(
            torch.randn(
                4,
                width,
            )
            * 0.02
        )
        self.heads = nn.ModuleList(
            [
                nn.Linear(
                    width,
                    4,
                )
                for _ in range(4)
            ]
        )

    def forward(
        self,
        tokens: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        embedded = self.embedding(tokens)
        lengths = mask.sum(1).cpu()
        packed = nn.utils.rnn.pack_padded_sequence(
            embedded,
            lengths,
            batch_first=True,
            enforce_sorted=False,
        )
        packed_hidden, _ = self.gru(
            packed
        )
        hidden, _ = nn.utils.rnn.pad_packed_sequence(
            packed_hidden,
            batch_first=True,
            total_length=tokens.shape[1],
        )

        scores = torch.einsum(
            "bld,sd->bsl",
            hidden,
            self.queries,
        ) / (hidden.shape[-1] ** 0.5)
        scores = scores.masked_fill(
            ~mask[:, None, :],
            -1e9,
        )
        weights = scores.softmax(
            dim=-1
        )
        pooled = torch.einsum(
            "bsl,bld->bsd",
            weights,
            hidden,
        )
        return torch.stack(
            [
                head(
                    pooled[:, slot]
                )
                for slot, head
                in enumerate(
                    self.heads
                )
            ],
            dim=1,
        )


class ByteTransformerPerceiver(nn.Module):
    def __init__(
        self,
        model_dim: int = 64,
        layers: int = 2,
        heads: int = 4,
        feedforward_dim: int = 192,
        max_length: int = 128,
    ) -> None:
        super().__init__()
        self.embedding = nn.Embedding(
            256,
            model_dim,
        )
        self.position = nn.Embedding(
            max_length,
            model_dim,
        )
        self.cls = nn.Parameter(
            torch.zeros(
                1,
                1,
                model_dim,
            )
        )
        layer = nn.TransformerEncoderLayer(
            d_model=model_dim,
            nhead=heads,
            dim_feedforward=
                feedforward_dim,
            dropout=0.0,
            batch_first=True,
            norm_first=True,
            activation="gelu",
        )
        self.network = nn.TransformerEncoder(
            layer,
            num_layers=layers,
        )
        self.norm = nn.LayerNorm(
            model_dim
        )
        self.head = nn.Linear(
            model_dim,
            16,
        )

    def forward(
        self,
        tokens: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        batch, length = tokens.shape
        positions = torch.arange(
            length,
            device=tokens.device,
        )
        hidden = (
            self.embedding(tokens)
            + self.position(
                positions
            )[None]
        )
        cls = self.cls.expand(
            batch,
            -1,
            -1,
        )
        hidden = torch.cat(
            [cls, hidden],
            dim=1,
        )
        full_mask = torch.cat(
            [
                torch.ones(
                    batch,
                    1,
                    dtype=torch.bool,
                    device=tokens.device,
                ),
                mask,
            ],
            dim=1,
        )
        hidden = self.network(
            hidden,
            src_key_padding_mask=
                ~full_mask,
        )
        return self.head(
            self.norm(
                hidden[:, 0]
            )
        ).view(-1, 4, 4)


def build_perceiver(name: str) -> nn.Module:
    if name == "gru":
        return ByteGRUPerceiver()
    if name == "bigru":
        return ByteBiGRUPerceiver()
    if name == "attn_bigru":
        return ByteAttentiveBiGRUPerceiver()
    if name == "transformer":
        return ByteTransformerPerceiver()
    raise ValueError(
        f"unknown perceiver: {name}"
    )


def parameter_count(
    model: nn.Module,
) -> int:
    return sum(
        parameter.numel()
        for parameter
        in model.parameters()
    )


def train_one(
    model_name: str,
    *,
    seed: int,
    steps: int,
    batch_size: int,
) -> dict:
    torch.manual_seed(seed)
    rng = random.Random(
        seed * 17 + 3
    )
    train_items, valid_items = (
        semantic_split()
    )
    model = build_perceiver(
        model_name
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
        weight_decay=0.01,
    )

    started = perf_counter()
    last_loss = None

    for _ in range(steps):
        items = [
            rng.choice(train_items)
            for _ in range(batch_size)
        ]
        texts = [
            render(
                item,
                rng.choice(
                    TRAIN_TEMPLATES
                ),
            )
            for item in items
        ]
        tokens, mask = encode_bytes(
            texts
        )
        targets = torch.stack(
            [
                semantic_labels(item)
                for item in items
            ]
        )

        optimizer.zero_grad(
            set_to_none=True
        )
        logits = model(
            tokens,
            mask,
        )
        loss = sum(
            F.cross_entropy(
                logits[:, slot],
                targets[:, slot],
            )
            for slot in range(4)
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0,
        )
        optimizer.step()
        last_loss = float(
            loss.item()
        )

    train_seconds = (
        perf_counter() - started
    )

    model.eval()
    exact = 0
    slot_hits = 0
    examples = 0
    template_exact = []

    with torch.no_grad():
        for template in VALID_TEMPLATES:
            texts = [
                render(
                    item,
                    template,
                )
                for item
                in valid_items
            ]
            tokens, mask = encode_bytes(
                texts
            )
            targets = torch.stack(
                [
                    semantic_labels(item)
                    for item
                    in valid_items
                ]
            )
            predictions = model(
                tokens,
                mask,
            ).argmax(-1)
            exact_rows = (
                predictions
                == targets
            ).all(-1)
            exact += int(
                exact_rows.sum().item()
            )
            slot_hits += int(
                (
                    predictions
                    == targets
                ).sum().item()
            )
            examples += len(
                valid_items
            )
            template_exact.append(
                float(
                    exact_rows
                    .float()
                    .mean()
                    .item()
                )
            )

    return {
        "model": model_name,
        "seed": seed,
        "parameters":
            parameter_count(model),
        "steps": steps,
        "train_seconds":
            train_seconds,
        "steps_per_second":
            steps / train_seconds,
        "last_train_loss":
            last_loss,
        "held_out_examples":
            examples,
        "exact_states":
            exact,
        "exact_state_rate":
            exact / examples,
        "slot_accuracy":
            slot_hits
            / (examples * 4),
        "template_exact_rates":
            template_exact,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        default=(
            "gru,bigru,attn_bigru,transformer"
        ),
    )
    parser.add_argument(
        "--seeds",
        default="11,22,33",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=200,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    torch.set_num_threads(
        args.threads
    )
    models = [
        item.strip()
        for item
        in args.models.split(",")
        if item.strip()
    ]
    seeds = [
        int(item.strip())
        for item
        in args.seeds.split(",")
        if item.strip()
    ]

    rows = [
        train_one(
            model,
            seed=seed,
            steps=args.steps,
            batch_size=
                args.batch_size,
        )
        for seed in seeds
        for model in models
    ]

    summary = {}
    for model in models:
        selected = [
            row
            for row in rows
            if row["model"] == model
        ]
        summary[model] = {
            "runs": len(selected),
            "mean_exact_state_rate":
                mean(
                    row[
                        "exact_state_rate"
                    ]
                    for row
                    in selected
                ),
            "mean_slot_accuracy":
                mean(
                    row[
                        "slot_accuracy"
                    ]
                    for row
                    in selected
                ),
            "mean_train_seconds":
                mean(
                    row[
                        "train_seconds"
                    ]
                    for row
                    in selected
                ),
            "mean_steps_per_second":
                mean(
                    row[
                        "steps_per_second"
                    ]
                    for row
                    in selected
                ),
        }

    payload = {
        "summary": summary,
        "rows": rows,
    }
    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    print(text)

    if args.output:
        with open(
            args.output,
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                text + "\n"
            )


if __name__ == "__main__":
    main()
