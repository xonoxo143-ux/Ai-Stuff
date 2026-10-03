"""Synthetic long-context current-state tracking benchmark.

Both lanes receive the same 256-token exact local window:
128 carried past tokens + a 128-token current segment.
Only Delta may carry its recurrent matrices beyond that window.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn

from agent_language.models import ByteTransformer
from .delta_reference import DeltaState
from .model_v1 import DeltaHybridV1
from .persistent_state import (
    AttentionHistory,
    DeltaHybridState,
    StatefulDeltaHybridV1,
    state_size_bytes,
)

UPDATE = 240
QUERY = 241
KEY_BASE = 16
KEY_COUNT = 32
VALUE_BASE = 64
VALUE_COUNT = 16
FILL_LOW = 128
FILL_HIGH = 224
def _sample(length: int, seed: int):
    rng = random.Random(seed)
    seq, labels, distances = [], [], []
    current: dict[int, int] = {}
    last_update: dict[int, int] = {}

    initial = rng.sample(range(KEY_COUNT), 16)
    for key in initial:
        if len(seq) + 3 > length:
            break
        value = VALUE_BASE + rng.randrange(VALUE_COUNT)
        start = len(seq)
        seq.extend([UPDATE, KEY_BASE + key, value])
        labels.extend([-100, -100, -100])
        distances.extend([-1, -1, -1])
        current[key] = value
        last_update[key] = start + 2

    while len(seq) < length:
        remain = length - len(seq)
        draw = rng.random()
        if remain >= 3 and (draw < 0.18 or not current):
            key = rng.randrange(KEY_COUNT)
            value = VALUE_BASE + rng.randrange(VALUE_COUNT)
            start = len(seq)
            seq.extend([UPDATE, KEY_BASE + key, value])
            labels.extend([-100, -100, -100])
            distances.extend([-1, -1, -1])
            current[key] = value
            last_update[key] = start + 2
        elif remain >= 2 and draw < 0.50 and current:
            key_pos = len(seq) + 1
            stale = [
                key for key in current
                if key_pos - last_update[key] > 256
            ]
            if stale and rng.random() < 0.70:
                key = rng.choice(stale)
            else:
                key = rng.choice(list(current))
            distance = key_pos - last_update[key]
            seq.extend([QUERY, KEY_BASE + key])
            labels.extend([-100, current[key]])
            distances.extend([-1, distance])
        else:
            seq.append(rng.randrange(FILL_LOW, FILL_HIGH))
            labels.append(-100)
            distances.append(-1)

    return (
        torch.tensor(seq[:length], dtype=torch.long),
        torch.tensor(labels[:length], dtype=torch.long),
        torch.tensor(distances[:length], dtype=torch.long),
    )
def generate_batch(batch: int, length: int, seed: int):
    rows = [_sample(length, seed + i * 10007) for i in range(batch)]
    tokens = torch.stack([r[0] for r in rows])
    labels = torch.stack([r[1] for r in rows])
    distances = torch.stack([r[2] for r in rows])
    if not bool((labels >= 0).any()):
        raise RuntimeError("generated batch has no queries")
    return tokens, labels, distances


def build_transformer():
    return ByteTransformer(
        model_dim=128,
        layers=5,
        heads=4,
        feedforward_dim=480,
        max_length=256,
        condition_dim=16,
    )


def zero_recurrent(state: DeltaHybridState) -> DeltaHybridState:
    delta = tuple(
        DeltaState(torch.zeros_like(item.memory))
        for item in state.delta_states
    )
    return DeltaHybridState(delta, state.attention)


def zero_attention(state: DeltaHybridState) -> DeltaHybridState:
    att = state.attention
    if att is None:
        return state
    empty = AttentionHistory(
        att.hidden[:, :0],
        att.valid[:, :0],
    )
    return DeltaHybridState(state.delta_states, empty)


def delta_forward(
    model,
    tokens,
    *,
    segment_size=128,
    history=128,
    ablation=None,
):
    runner = StatefulDeltaHybridV1(
        model,
        max_attention_history=history,
    )
    state = None
    outputs = []
    for start in range(0, tokens.shape[1], segment_size):
        stop = min(tokens.shape[1], start + segment_size)
        out, state = runner.forward_segment(
            tokens[:, start:stop],
            state,
        )
        outputs.append(out)
        if ablation == "no_recurrent":
            state = zero_recurrent(state)
        elif ablation == "no_attention":
            state = zero_attention(state)
    return torch.cat(outputs, dim=1), state
def transformer_forward(
    model,
    tokens,
    *,
    segment_size=128,
    past_window=128,
):
    outputs = []
    for start in range(0, tokens.shape[1], segment_size):
        stop = min(tokens.shape[1], start + segment_size)
        context_start = max(0, start - past_window)
        context = tokens[:, context_start:stop]
        out = model(context)
        outputs.append(out[:, -(stop - start):])
    return torch.cat(outputs, dim=1)


def query_loss(logits, labels):
    mask = labels >= 0
    return F.cross_entropy(logits[mask], labels[mask])


BUCKETS = {
    "le128": (0, 128),
    "129_256": (129, 256),
    "257_512": (257, 512),
    "gt512": (513, 10**9),
    "gt256": (257, 10**9),
}
def new_counts():
    result = {"all": [0, 0]}
    result.update({name: [0, 0] for name in BUCKETS})
    return result


def update_counts(counts, logits, labels, distances):
    pred = logits.argmax(dim=-1)
    query = labels >= 0

    correct = (pred == labels) & query
    counts["all"][0] += int(correct.sum())
    counts["all"][1] += int(query.sum())

    for name, (low, high) in BUCKETS.items():
        mask = query & (distances >= low) & (distances <= high)
        counts[name][0] += int((correct & mask).sum())
        counts[name][1] += int(mask.sum())


def finalize_counts(counts):
    result = {}
    for name, (correct, total) in counts.items():
        result[name] = {
            "correct": correct,
            "count": total,
            "accuracy": (correct / total) if total else None,
        }
    return result
@torch.no_grad()
def evaluate(
    model,
    lane,
    *,
    length,
    batches,
    batch_size,
    seed,
    device,
    ablation=None,
):
    model.eval()
    counts = new_counts()
    state_bytes = []
    for index in range(batches):
        tokens, labels, distances = generate_batch(
            batch_size,
            length,
            seed + index * 1000003,
        )
        tokens = tokens.to(device)
        labels = labels.to(device)
        distances = distances.to(device)

        if lane == "delta":
            logits, state = delta_forward(
                model,
                tokens,
                ablation=ablation,
            )
            if state is not None:
                state_bytes.append(
                    state_size_bytes(state) // batch_size
                )
        else:
            logits = transformer_forward(model, tokens)

        update_counts(counts, logits, labels, distances)

    result = {
        "metrics": finalize_counts(counts),
        "state_bytes_per_sample": (
            max(state_bytes) if state_bytes else 0
        ),
    }
    return result


def build_model(lane, device, seed):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if lane == "delta":
        model = DeltaHybridV1()
    elif lane == "transformer":
        model = build_transformer()
    else:
        raise ValueError(lane)
    return model.to(device)


def parameter_count(model):
    return sum(p.numel() for p in model.parameters())
def train(args):
    device = torch.device(args.device)
    model = build_model(args.lane, device, args.model_seed)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=0.01,
    )

    model.train()
    start_time = time.perf_counter()
    last_loss = None
    query_targets = 0

    for step in range(1, args.steps + 1):
        tokens, labels, _ = generate_batch(
            args.batch_size,
            args.train_length,
            args.data_seed + step,
        )
        query_targets += int((labels >= 0).sum())
        tokens = tokens.to(device)
        labels = labels.to(device)

        optimizer.zero_grad(set_to_none=True)
        if args.lane == "delta":
            logits, _ = delta_forward(model, tokens)
        else:
            logits = transformer_forward(model, tokens)
        loss = query_loss(logits, labels)
        if not bool(torch.isfinite(loss)):
            raise RuntimeError(f"non-finite loss at step {step}")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        last_loss = float(loss.detach())

        if step == 1 or step % 50 == 0 or step == args.steps:
            print(
                json.dumps({
                    "lane": args.lane,
                    "step": step,
                    "loss": last_loss,
                }),
                flush=True,
            )

    if device.type == "cuda":
        torch.cuda.synchronize(device)
    train_seconds = time.perf_counter() - start_time

    checkpoint = args.output.with_suffix(".pt")
    torch.save(model.state_dict(), checkpoint)

    evals = {}
    for length in args.eval_lengths:
        if args.lane == "delta":
            variants = {}
            for ablation in (None, "no_recurrent", "no_attention"):
                name = "full" if ablation is None else ablation
                variants[name] = evaluate(
                    model,
                    "delta",
                    length=length,
                    batches=args.eval_batches,
                    batch_size=args.eval_batch_size,
                    seed=args.eval_seed + length * 1009,
                    device=device,
                    ablation=ablation,
                )
            evals[str(length)] = variants
        else:
            evals[str(length)] = {
                "windowed": evaluate(
                    model,
                    "transformer",
                    length=length,
                    batches=args.eval_batches,
                    batch_size=args.eval_batch_size,
                    seed=args.eval_seed + length * 1009,
                    device=device,
                )
            }

    return {
        "lane": args.lane,
        "parameters": parameter_count(model),
        "steps": args.steps,
        "train_length": args.train_length,
        "batch_size": args.batch_size,
        "segment_size": 128,
        "exact_past_window": 128,
        "exact_local_span_max": 256,
        "learning_rate": args.learning_rate,
        "model_seed": args.model_seed,
        "data_seed": args.data_seed,
        "query_targets_seen": query_targets,
        "final_loss": last_loss,
        "train_seconds": train_seconds,
        "checkpoint": str(checkpoint),
        "evaluations": evals,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lane",
        choices=("delta", "transformer"),
        required=True,
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--train-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--eval-batch-size", type=int, default=4)
    parser.add_argument("--eval-batches", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--model-seed", type=int, default=20261002)
    parser.add_argument("--data-seed", type=int, default=771000)
    parser.add_argument("--eval-seed", type=int, default=991000)
    parser.add_argument("--eval-lengths", default="128,512,2048")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.eval_lengths = tuple(
        int(item) for item in args.eval_lengths.split(",") if item
    )

    summary = train(args)
    args.output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
