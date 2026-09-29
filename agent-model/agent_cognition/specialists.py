from __future__ import annotations

import argparse
import json
import random
from statistics import mean
from time import perf_counter

import torch
import torch.nn.functional as F

from .benchmark import FAMILY_NAMES, generate_example
from .models import build_model, parameter_count


def batch(
    rng: random.Random,
    family: int,
    size: int,
    *,
    ood: bool = False,
):
    examples = [
        generate_example(rng, family, ood=ood)
        for _ in range(size)
    ]
    return (
        torch.stack([x.slots for x in examples]),
        torch.stack([x.mask for x in examples]),
        torch.tensor(
            [x.answer for x in examples],
            dtype=torch.long,
        ),
    )


def evaluate(
    model,
    family: int,
    seed: int,
    *,
    ood: bool,
    count: int = 200,
) -> float:
    rng = random.Random(
        seed + (100_000 if ood else 0)
    )
    correct = 0
    with torch.no_grad():
        for start in range(0, count, 50):
            size = min(50, count - start)
            slots, mask, answer = batch(
                rng,
                family,
                size,
                ood=ood,
            )
            correct += int(
                (
                    model(slots, mask).argmax(-1)
                    == answer
                ).sum().item()
            )
    return correct / count


def train_specialist(
    family: int,
    seed: int,
    *,
    steps: int,
    batch_size: int,
) -> dict:
    torch.manual_seed(seed * 101 + family)
    rng = random.Random(seed * 1009 + family)
    model = build_model("factor")
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
        weight_decay=0.01,
    )
    started = perf_counter()

    for _ in range(steps):
        slots, mask, answer = batch(
            rng,
            family,
            batch_size,
        )
        optimizer.zero_grad(set_to_none=True)
        loss = F.cross_entropy(
            model(slots, mask),
            answer,
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0,
        )
        optimizer.step()

    seconds = perf_counter() - started
    return {
        "family": FAMILY_NAMES[family],
        "seed": seed,
        "steps": steps,
        "parameters": parameter_count(model),
        "train_seconds": seconds,
        "iid": evaluate(
            model,
            family,
            seed + 2000,
            ood=False,
        ),
        "ood": evaluate(
            model,
            family,
            seed + 3000,
            ood=True,
        ),
        "last_loss": float(
            loss.detach().item()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        default="11,22,33",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=250,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    seeds = [
        int(x.strip())
        for x in args.seeds.split(",")
        if x.strip()
    ]
    rows = [
        train_specialist(
            family,
            seed,
            steps=args.steps,
            batch_size=args.batch_size,
        )
        for seed in seeds
        for family in range(
            len(FAMILY_NAMES)
        )
    ]

    summary = {}
    for family in FAMILY_NAMES:
        selected = [
            row
            for row in rows
            if row["family"] == family
        ]
        summary[family] = {
            "runs": len(selected),
            "mean_iid": mean(
                row["iid"]
                for row in selected
            ),
            "mean_ood": mean(
                row["ood"]
                for row in selected
            ),
            "mean_train_seconds": mean(
                row["train_seconds"]
                for row in selected
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
            handle.write(text + "
")


if __name__ == "__main__":
    main()
