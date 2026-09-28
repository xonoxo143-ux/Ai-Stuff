from __future__ import annotations

import argparse
import itertools
import json
import random
from statistics import mean
from time import perf_counter

import torch
import torch.nn.functional as F

from .conditioning_probe import (
    BOS_ID,
    SLOTS,
    condition_for,
    sentence_for,
)
from .models import build_model
from .perception_probe import (
    ByteBiGRUPerceiver,
    TRAIN_TEMPLATES,
    VALID_TEMPLATES,
    encode_bytes,
    render,
    semantic_labels,
    semantic_split,
)


def predicted_conditions(
    logits: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    probabilities = logits.softmax(
        dim=-1
    )
    hard_indices = probabilities.argmax(
        dim=-1
    )
    hard = torch.zeros_like(
        probabilities
    )
    hard.scatter_(
        -1,
        hard_indices.unsqueeze(-1),
        1.0,
    )
    return (
        hard.flatten(1),
        probabilities.flatten(1),
    )


def train_perceiver(
    seed: int,
    steps: int,
) -> ByteBiGRUPerceiver:
    torch.manual_seed(seed)
    rng = random.Random(
        seed * 17 + 5
    )
    train_items, _ = semantic_split()
    model = ByteBiGRUPerceiver()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
        weight_decay=0.01,
    )

    for _ in range(steps):
        items = [
            rng.choice(train_items)
            for _ in range(64)
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

    return model


def train_producer(
    seed: int,
    steps: int,
):
    torch.manual_seed(
        seed + 1000
    )
    rng = random.Random(
        seed * 29 + 11
    )
    all_items = list(
        itertools.product(*SLOTS)
    )
    model = build_model(
        "gru",
        condition_dim=16,
        scale="micro",
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
    )

    for _ in range(steps):
        items = [
            rng.choice(all_items)
            for _ in range(32)
        ]
        targets = torch.tensor(
            [
                list(
                    sentence_for(item)
                )
                for item in items
            ],
            dtype=torch.long,
        )
        bos = torch.full(
            (len(items), 1),
            BOS_ID,
            dtype=torch.long,
        )
        inputs = torch.cat(
            [
                bos,
                targets[:, :-1],
            ],
            dim=1,
        )
        conditions = torch.stack(
            [
                condition_for(item)
                for item in items
            ]
        )

        optimizer.zero_grad(
            set_to_none=True
        )
        logits = model(
            inputs,
            conditions,
        )
        loss = F.cross_entropy(
            logits.reshape(-1, 256),
            targets.reshape(-1),
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0,
        )
        optimizer.step()

    return model


def teacher_forced_metrics(
    producer,
    items,
    conditions: torch.Tensor,
) -> dict:
    targets = torch.tensor(
        [
            list(sentence_for(item))
            for item in items
        ],
        dtype=torch.long,
    )
    bos = torch.full(
        (len(items), 1),
        BOS_ID,
        dtype=torch.long,
    )
    inputs = torch.cat(
        [
            bos,
            targets[:, :-1],
        ],
        dim=1,
    )
    with torch.no_grad():
        predictions = producer(
            inputs,
            conditions,
        ).argmax(-1)

    correct = (
        predictions
        == targets
    )
    sequence_exact = (
        correct.all(-1)
        .float()
        .mean()
        .item()
    )
    byte_accuracy = (
        correct.float()
        .mean()
        .item()
    )
    return {
        "sequence_exact":
            sequence_exact,
        "byte_accuracy":
            byte_accuracy,
    }


def run_one(
    seed: int,
    *,
    perception_steps: int,
    production_steps: int,
) -> dict:
    started = perf_counter()
    perceiver = train_perceiver(
        seed,
        perception_steps,
    )
    producer = train_producer(
        seed,
        production_steps,
    )
    train_seconds = (
        perf_counter() - started
    )

    _, valid_items = semantic_split()
    state_exact = []
    oracle_metrics = []
    hard_metrics = []
    soft_metrics = []
    examples = []

    perceiver.eval()
    producer.eval()

    for template in VALID_TEMPLATES:
        texts = [
            render(
                item,
                template,
            )
            for item in valid_items
        ]
        tokens, mask = encode_bytes(
            texts
        )
        truth = torch.stack(
            [
                semantic_labels(item)
                for item in valid_items
            ]
        )
        oracle = torch.stack(
            [
                condition_for(item)
                for item in valid_items
            ]
        )

        with torch.no_grad():
            logits = perceiver(
                tokens,
                mask,
            )
        hard, soft = (
            predicted_conditions(
                logits
            )
        )
        predicted_slots = logits.argmax(
            dim=-1
        )
        state_exact.append(
            (
                predicted_slots
                == truth
            )
            .all(-1)
            .float()
            .mean()
            .item()
        )

        oracle_metrics.append(
            teacher_forced_metrics(
                producer,
                valid_items,
                oracle,
            )
        )
        hard_metrics.append(
            teacher_forced_metrics(
                producer,
                valid_items,
                hard,
            )
        )
        soft_metrics.append(
            teacher_forced_metrics(
                producer,
                valid_items,
                soft,
            )
        )

        if len(examples) < 4:
            for index in range(
                min(4, len(texts))
            ):
                examples.append(
                    {
                        "input":
                            texts[index],
                        "true_slots":
                            truth[
                                index
                            ].tolist(),
                        "predicted_slots":
                            predicted_slots[
                                index
                            ].tolist(),
                    }
                )

    def avg(
        rows,
        key,
    ) -> float:
        return mean(
            row[key]
            for row in rows
        )

    return {
        "seed": seed,
        "perception_steps":
            perception_steps,
        "production_steps":
            production_steps,
        "train_seconds":
            train_seconds,
        "mean_state_exact":
            mean(state_exact),
        "oracle_sequence_exact":
            avg(
                oracle_metrics,
                "sequence_exact",
            ),
        "oracle_byte_accuracy":
            avg(
                oracle_metrics,
                "byte_accuracy",
            ),
        "hard_sequence_exact":
            avg(
                hard_metrics,
                "sequence_exact",
            ),
        "hard_byte_accuracy":
            avg(
                hard_metrics,
                "byte_accuracy",
            ),
        "soft_sequence_exact":
            avg(
                soft_metrics,
                "sequence_exact",
            ),
        "soft_byte_accuracy":
            avg(
                soft_metrics,
                "byte_accuracy",
            ),
        "examples": examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        default="11,22,33",
    )
    parser.add_argument(
        "--perception-steps",
        type=int,
        default=200,
    )
    parser.add_argument(
        "--production-steps",
        type=int,
        default=300,
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
    seeds = [
        int(item.strip())
        for item
        in args.seeds.split(",")
        if item.strip()
    ]
    rows = [
        run_one(
            seed,
            perception_steps=
                args.perception_steps,
            production_steps=
                args.production_steps,
        )
        for seed in seeds
    ]

    summary = {
        key: mean(
            row[key]
            for row in rows
        )
        for key in (
            "mean_state_exact",
            "oracle_sequence_exact",
            "oracle_byte_accuracy",
            "hard_sequence_exact",
            "hard_byte_accuracy",
            "soft_sequence_exact",
            "soft_byte_accuracy",
            "train_seconds",
        )
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
