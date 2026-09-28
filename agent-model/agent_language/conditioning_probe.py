from __future__ import annotations

import argparse
import itertools
import json
import random
from statistics import mean
from time import perf_counter

import torch
import torch.nn.functional as F

from .models import (
    BOS_ID,
    build_model,
    parameter_count,
)

NAMES = ("Mia", "Leo", "Ava", "Ivy")
COLORS = ("red", "tan", "sky", "ash")
ANIMALS = ("cat", "dog", "fox", "owl")
PLACES = ("park", "hill", "yard", "home")
SLOTS = (
    NAMES,
    COLORS,
    ANIMALS,
    PLACES,
)


def condition_for(
    item: tuple[str, str, str, str],
) -> torch.Tensor:
    vector = torch.zeros(16)
    for slot_index, (
        values,
        value,
    ) in enumerate(zip(SLOTS, item)):
        vector[
            slot_index * 4
            + values.index(value)
        ] = 1.0
    return vector


def sentence_for(
    item: tuple[str, str, str, str],
) -> bytes:
    name, color, animal, place = item
    return (
        f"{name} saw a {color} {animal} "
        f"near the {place}.\n"
    ).encode("utf-8")


def split_examples():
    all_items = list(
        itertools.product(*SLOTS)
    )
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


def batch(
    rng: random.Random,
    train,
    batch_size: int,
):
    items = [
        rng.choice(train)
        for _ in range(batch_size)
    ]
    targets = torch.tensor(
        [
            list(sentence_for(item))
            for item in items
        ],
        dtype=torch.long,
    )
    bos = torch.full(
        (batch_size, 1),
        BOS_ID,
        dtype=torch.long,
    )
    inputs = torch.cat(
        [bos, targets[:, :-1]],
        dim=1,
    )
    conditions = torch.stack(
        [
            condition_for(item)
            for item in items
        ]
    )
    return (
        inputs,
        targets,
        conditions,
    )


def generate(
    model,
    condition: torch.Tensor,
    length: int,
) -> bytes:
    tokens = torch.tensor(
        [[BOS_ID]],
        dtype=torch.long,
    )
    for _ in range(length):
        logits = model(
            tokens,
            condition[None],
        )
        next_byte = logits[
            :,
            -1,
        ].argmax(
            dim=-1,
            keepdim=True,
        )
        tokens = torch.cat(
            [tokens, next_byte],
            dim=1,
        )
    return bytes(
        tokens[0, 1:].tolist()
    )


def run_one(
    model_name: str,
    seed: int,
    steps: int = 300,
) -> dict:
    if model_name not in {
        "gru",
        "transformer",
    }:
        raise ValueError(
            "conditioning probe supports "
            "gru,transformer"
        )
    torch.manual_seed(seed)
    rng = random.Random(
        seed * 31 + 7
    )
    train, valid = split_examples()
    model = build_model(
        model_name,
        condition_dim=16,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
    )

    started = perf_counter()
    last_loss = None
    for _ in range(steps):
        x, y, condition = batch(
            rng,
            train,
            32,
        )
        optimizer.zero_grad(
            set_to_none=True
        )
        logits = model(
            x,
            condition,
        )
        loss = F.cross_entropy(
            logits.reshape(-1, 256),
            y.reshape(-1),
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

    length = len(
        sentence_for(valid[0])
    )
    exact = 0
    slot_hits = 0
    examples = []

    for item in valid:
        generated = generate(
            model,
            condition_for(item),
            length,
        )
        exact += int(
            generated
            == sentence_for(item)
        )
        decoded = generated.decode(
            "utf-8",
            errors="replace",
        )
        slot_hits += sum(
            value in decoded
            for value in item
        )
        if len(examples) < 4:
            examples.append(
                {
                    "target":
                        sentence_for(
                            item
                        ).decode().strip(),
                    "generated":
                        decoded.strip(),
                }
            )

    return {
        "model": model_name,
        "seed": seed,
        "parameters":
            parameter_count(model),
        "steps": steps,
        "train_seconds":
            train_seconds,
        "last_loss_nats":
            last_loss,
        "held_out_combinations":
            len(valid),
        "exact_combinations":
            exact,
        "exact_rate":
            exact / len(valid),
        "slot_hits":
            slot_hits,
        "slot_total":
            len(valid) * 4,
        "slot_accuracy":
            slot_hits
            / (len(valid) * 4),
        "examples":
            examples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        default="gru,transformer",
    )
    parser.add_argument(
        "--seeds",
        default="1",
    )
    parser.add_argument(
        "--steps",
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
        run_one(
            model,
            seed,
            steps=args.steps,
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
            "runs":
                len(selected),
            "mean_exact_rate":
                mean(
                    row["exact_rate"]
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
