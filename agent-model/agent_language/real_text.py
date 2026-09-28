from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from time import perf_counter

import torch
import torch.nn.functional as F

from .data import ByteBatchStream
from .models import (
    build_model,
    parameter_count,
)


def read_bytes(
    path: str | Path,
    max_bytes: int | None = None,
) -> bytes:
    data = Path(path).read_bytes()
    if max_bytes is not None:
        data = data[:max_bytes]
    if len(data) < 4096:
        raise ValueError(
            "real-text corpus is too small"
        )
    return data


def evaluate(
    model,
    stream: ByteBatchStream,
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


def generate(
    model,
    prompt: str,
    *,
    bytes_to_generate: int = 120,
    context_length: int = 256,
) -> str:
    model.eval()
    prefix = list(
        prompt.encode("utf-8")
    )
    if not prefix:
        prefix = [10]

    with torch.no_grad():
        for _ in range(
            bytes_to_generate
        ):
            context = prefix[
                -context_length:
            ]
            tokens = torch.tensor(
                [context],
                dtype=torch.long,
            )
            logits = model(tokens)
            next_byte = int(
                logits[
                    0,
                    -1,
                ].argmax().item()
            )
            prefix.append(next_byte)

    return bytes(prefix).decode(
        "utf-8",
        errors="replace",
    )


def train_one(
    model_name: str,
    *,
    seed: int,
    train_data: bytes,
    valid_data: bytes,
    steps: int,
    batch_size: int,
    sequence_length: int,
    learning_rate: float,
    eval_steps: int,
    checkpoint_dir: str | None,
) -> dict:
    torch.manual_seed(seed)
    train_stream = ByteBatchStream(
        train_data,
        seed=seed * 19 + 1,
    )
    valid_stream = ByteBatchStream(
        valid_data,
        seed=seed * 19 + 2,
    )
    model = build_model(
        model_name,
        condition_dim=16,
        scale="small",
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=0.01,
    )

    started = perf_counter()
    losses = []

    model.train()
    for step in range(1, steps + 1):
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

        if (
            step == 1
            or step == steps
            or step % 100 == 0
        ):
            losses.append(
                {
                    "step": step,
                    "loss_nats":
                        float(
                            loss.item()
                        ),
                }
            )

    train_seconds = (
        perf_counter() - started
    )

    valid_loss = evaluate(
        model,
        valid_stream,
        steps=eval_steps,
        batch_size=batch_size,
        sequence_length=
            sequence_length,
    )
    sample = generate(
        model,
        "Once upon a time",
        bytes_to_generate=120,
        context_length=
            sequence_length,
    )

    checkpoint_path = None
    if checkpoint_dir:
        directory = Path(
            checkpoint_dir
        )
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        checkpoint_path = (
            directory
            / (
                f"{model_name}-seed"
                f"{seed}.pt"
            )
        )
        torch.save(
            {
                "model":
                    model.state_dict(),
                "model_name":
                    model_name,
                "scale": "small",
                "seed": seed,
                "steps": steps,
                "valid_loss_nats":
                    valid_loss,
            },
            checkpoint_path,
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
        "valid_loss_nats":
            valid_loss,
        "valid_bits_per_byte":
            valid_loss
            / math.log(2.0),
        "loss_checkpoints":
            losses,
        "sample": sample,
        "checkpoint":
            (
                str(
                    checkpoint_path
                )
                if checkpoint_path
                else None
            ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--train-file",
        required=True,
    )
    parser.add_argument(
        "--valid-file",
        required=True,
    )
    parser.add_argument(
        "--models",
        default="gru,transformer",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=101,
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=800,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--sequence-length",
        type=int,
        default=256,
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-3,
    )
    parser.add_argument(
        "--eval-steps",
        type=int,
        default=40,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--train-max-bytes",
        type=int,
        default=12_000_000,
    )
    parser.add_argument(
        "--valid-max-bytes",
        type=int,
        default=2_000_000,
    )
    parser.add_argument(
        "--checkpoint-dir",
    )
    parser.add_argument(
        "--output",
        required=True,
    )
    args = parser.parse_args()

    torch.set_num_threads(
        args.threads
    )
    train_data = read_bytes(
        args.train_file,
        args.train_max_bytes,
    )
    valid_data = read_bytes(
        args.valid_file,
        args.valid_max_bytes,
    )
    models = [
        item.strip()
        for item
        in args.models.split(",")
        if item.strip()
    ]

    rows = [
        train_one(
            model,
            seed=args.seed,
            train_data=train_data,
            valid_data=valid_data,
            steps=args.steps,
            batch_size=
                args.batch_size,
            sequence_length=
                args.sequence_length,
            learning_rate=
                args.learning_rate,
            eval_steps=
                args.eval_steps,
            checkpoint_dir=
                args.checkpoint_dir,
        )
        for model in models
    ]

    payload = {
        "train_bytes":
            len(train_data),
        "valid_bytes":
            len(valid_data),
        "rows": rows,
    }
    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    print(text)
    Path(
        args.output
    ).write_text(
        text + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
