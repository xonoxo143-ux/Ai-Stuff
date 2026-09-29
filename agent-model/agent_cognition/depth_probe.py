from __future__ import annotations

import argparse
import json
import random
from statistics import mean

import torch
import torch.nn.functional as F

from .benchmark import FAMILY_NAMES, generate_example
from .models import build_model


def make_batch(
    rng: random.Random,
    size: int,
    *,
    family: int | None = None,
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


def train(
    seed: int,
    steps: int,
    batch_size: int,
):
    torch.manual_seed(seed)
    rng = random.Random(seed * 31 + 5)
    model = build_model("factor")
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=2e-3,
        weight_decay=0.01,
    )

    for _ in range(steps):
        slots, mask, answer = make_batch(
            rng,
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

    return model


def evaluate_depth(
    model,
    seed: int,
    thought_steps: int,
    per_family: int,
) -> dict:
    scores = {}
    with torch.no_grad():
        for family, name in enumerate(
            FAMILY_NAMES
        ):
            rng = random.Random(
                seed + family * 10007
            )
            correct = 0
            for start in range(
                0,
                per_family,
                50,
            ):
                size = min(
                    50,
                    per_family - start,
                )
                slots, mask, answer = make_batch(
                    rng,
                    size,
                    family=family,
                    ood=True,
                )
                prediction = model(
                    slots,
                    mask,
                    steps=thought_steps,
                ).argmax(-1)
                correct += int(
                    (
                        prediction
                        == answer
                    ).sum().item()
                )
            scores[name] = (
                correct / per_family
            )
    scores["mean"] = mean(
        scores.values()
    )
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seeds",
        default="11,22,33",
    )
    parser.add_argument(
        "--train-steps",
        type=int,
        default=250,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--depths",
        default="1,2,4,6,8",
    )
    parser.add_argument(
        "--eval-per-family",
        type=int,
        default=150,
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
    depths = [
        int(x.strip())
        for x in args.depths.split(",")
        if x.strip()
    ]

    rows = []
    for seed in seeds:
        model = train(
            seed,
            args.train_steps,
            args.batch_size,
        )
        for depth in depths:
            rows.append(
                {
                    "seed": seed,
                    "depth": depth,
                    "ood": evaluate_depth(
                        model,
                        seed + 5000,
                        depth,
                        args.eval_per_family,
                    ),
                }
            )

    summary = {}
    for depth in depths:
        selected = [
            row
            for row in rows
            if row["depth"] == depth
        ]
        summary[str(depth)] = {
            "runs": len(selected),
            "mean_ood": mean(
                row["ood"]["mean"]
                for row in selected
            ),
            **{
                family: mean(
                    row["ood"][family]
                    for row in selected
                )
                for family
                in FAMILY_NAMES
            },
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
            handle.write(text + "\\n")


if __name__ == "__main__":
    main()
