from __future__ import annotations

import argparse
import json
import math
from statistics import mean
from time import perf_counter

import torch
import torch.nn.functional as F

from .data import ByteBatchStream, make_micro_english
from .models import build_model, parameter_count


def evaluate(
    model,
    stream,
    *,
    steps: int,
    batch_size: int,
    sequence_length: int,
) -> float:
    model.eval()
    losses = []
    with torch.no_grad():
        for _ in range(steps):
            x, y = stream.batch(
                batch_size,
                sequence_length,
            )
            logits = model(x)
            losses.append(
                F.cross_entropy(
                    logits.reshape(-1, 256),
                    y.reshape(-1),
                ).item()
            )
    return mean(losses)


def train_one(
    model_name: str,
    *,
    seed: int,
    steps: int,
    batch_size: int,
    sequence_length: int,
    learning_rate: float,
    threads: int,
) -> dict:
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    train_data = make_micro_english(
        1001,
        2200,
    )
    valid_data = make_micro_english(
        2001,
        400,
    )
    train_stream = ByteBatchStream(
        train_data,
        seed=seed * 17 + 1,
    )
    valid_stream = ByteBatchStream(
        valid_data,
        seed=seed * 17 + 2,
    )
    model = build_model(
        model_name,
        condition_dim=16,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=0.01,
    )

    started = perf_counter()
    model.train()
    last_loss = None
    for _ in range(steps):
        x, y = train_stream.batch(
            batch_size,
            sequence_length,
        )
        optimizer.zero_grad(
            set_to_none=True
        )
        logits = model(x)
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
        last_loss = float(loss.item())
    train_seconds = (
        perf_counter() - started
    )

    valid_loss = evaluate(
        model,
        valid_stream,
        steps=30,
        batch_size=batch_size,
        sequence_length=sequence_length,
    )

    x, _ = valid_stream.batch(
        2,
        sequence_length,
    )
    condition_a = torch.zeros(2, 16)
    condition_b = torch.ones(2, 16)
    with torch.no_grad():
        delta = float(
            (
                model(x, condition_a)
                - model(x, condition_b)
            ).abs().mean().item()
        )

    return {
        "model": model_name,
        "seed": seed,
        "parameters":
            parameter_count(model),
        "steps": steps,
        "train_seconds": train_seconds,
        "steps_per_second":
            steps / train_seconds,
        "last_train_loss_nats":
            last_loss,
        "valid_loss_nats":
            valid_loss,
        "valid_bits_per_byte":
            valid_loss / math.log(2.0),
        "conditioning_output_delta":
            delta,
    }


def summarize(
    rows: list[dict],
) -> dict:
    models = sorted({
        row["model"]
        for row in rows
    })
    by_model = {}
    for model in models:
        selected = [
            row
            for row in rows
            if row["model"] == model
        ]
        by_model[model] = {
            "runs": len(selected),
            "mean_parameters": mean(
                row["parameters"]
                for row in selected
            ),
            "mean_valid_bits_per_byte":
                mean(
                    row[
                        "valid_bits_per_byte"
                    ]
                    for row in selected
                ),
            "mean_train_seconds":
                mean(
                    row["train_seconds"]
                    for row in selected
                ),
            "mean_steps_per_second":
                mean(
                    row["steps_per_second"]
                    for row in selected
                ),
            "mean_conditioning_output_delta":
                mean(
                    row[
                        "conditioning_output_delta"
                    ]
                    for row in selected
                ),
        }

    seeds = sorted({
        row["seed"]
        for row in rows
    })
    wins = {
        model: 0
        for model in models
    }
    for seed in seeds:
        contenders = [
            row
            for row in rows
            if row["seed"] == seed
        ]
        winner = min(
            contenders,
            key=lambda row:
                row[
                    "valid_bits_per_byte"
                ],
        )
        wins[winner["model"]] += 1

    return {
        "by_model": by_model,
        "validation_wins_by_seed":
            wins,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        default=(
            "gru,transformer,patch_rnn"
        ),
    )
    parser.add_argument(
        "--seeds",
        default="1",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=160,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=16,
    )
    parser.add_argument(
        "--sequence-length",
        type=int,
        default=128,
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-3,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.sequence_length % 4:
        raise SystemExit(
            "sequence-length must be divisible by 4"
        )
    models = [
        item.strip()
        for item in args.models.split(",")
        if item.strip()
    ]
    seeds = [
        int(item.strip())
        for item in args.seeds.split(",")
        if item.strip()
    ]
    rows = [
        train_one(
            model,
            seed=seed,
            steps=args.steps,
            batch_size=args.batch_size,
            sequence_length=
                args.sequence_length,
            learning_rate=
                args.learning_rate,
            threads=args.threads,
        )
        for seed in seeds
        for model in models
    ]
    payload = {
        "summary": summarize(rows),
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
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
