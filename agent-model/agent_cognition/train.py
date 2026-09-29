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


def make_batch(
    rng: random.Random,
    batch_size: int,
    *,
    family: int | None = None,
    ood: bool = False,
):
    examples = [
        generate_example(rng, family, ood=ood)
        for _ in range(batch_size)
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
    seed: int,
    *,
    per_family: int = 200,
    ood: bool = False,
):
    model.eval()
    rows = {}
    with torch.no_grad():
        for family, name in enumerate(FAMILY_NAMES):
            rng = random.Random(
                seed
                + family * 10007
                + (99991 if ood else 0)
            )
            correct = 0
            total = 0
            while total < per_family:
                size = min(64, per_family - total)
                slots, mask, answer = make_batch(
                    rng,
                    size,
                    family=family,
                    ood=ood,
                )
                prediction = model(slots, mask).argmax(-1)
                correct += int(
                    (prediction == answer).sum().item()
                )
                total += size
            rows[name] = correct / total
    rows["mean"] = mean(rows.values())
    return rows


def train_one(
    name: str,
    seed: int,
    *,
    steps: int = 1200,
    batch_size: int = 64,
    lr: float = 2e-3,
    eval_per_family: int = 200,
):
    torch.manual_seed(seed)
    rng = random.Random(seed * 31 + 5)
    model = build_model(name)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=0.01,
    )
    started = perf_counter()
    checkpoints = []

    for step in range(1, steps + 1):
        slots, mask, answer = make_batch(
            rng,
            batch_size,
        )
        optimizer.zero_grad(set_to_none=True)
        logits = model(slots, mask)
        loss = F.cross_entropy(logits, answer)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            model.parameters(),
            1.0,
        )
        optimizer.step()

        if step in {
            1,
            steps // 4,
            steps // 2,
            steps,
        }:
            checkpoints.append(
                {
                    "step": step,
                    "loss": float(loss.item()),
                }
            )

    seconds = perf_counter() - started
    return {
        "model": name,
        "seed": seed,
        "parameters": parameter_count(model),
        "steps": steps,
        "train_seconds": seconds,
        "steps_per_second": steps / seconds,
        "loss_checkpoints": checkpoints,
        "iid": evaluate(
            model,
            seed + 1000,
            ood=False,
            per_family=eval_per_family,
        ),
        "ood": evaluate(
            model,
            seed + 2000,
            ood=True,
            per_family=eval_per_family,
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        default=(
            "flat,factor_onepass,"
            "factor,factor_no_reinject"
        ),
    )
    parser.add_argument("--seeds", default="11")
    parser.add_argument(
        "--steps",
        type=int,
        default=1200,
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
    parser.add_argument(
        "--eval-per-family",
        type=int,
        default=200,
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    models = [
        x.strip()
        for x in args.models.split(",")
        if x.strip()
    ]
    seeds = [
        int(x)
        for x in args.seeds.split(",")
        if x.strip()
    ]

    rows = [
        train_one(
            model,
            seed,
            steps=args.steps,
            batch_size=args.batch_size,
            eval_per_family=args.eval_per_family,
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
            "mean_iid": mean(
                row["iid"]["mean"]
                for row in selected
            ),
            "mean_ood": mean(
                row["ood"]["mean"]
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
