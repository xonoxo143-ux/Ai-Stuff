from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from statistics import mean, pstdev

import torch

from .compile_motif import (
    PairComposite,
    collect_teacher_samples,
    evaluate_compiled,
    train_composite,
)
from .export_onnx import load_checkpoint


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument("--left", type=int, default=1)
    p.add_argument("--right", type=int, default=10)
    p.add_argument("--hidden-dim", type=int, default=64)
    p.add_argument("--collect-batches", type=int, default=80)
    p.add_argument("--collect-batch-size", type=int, default=128)
    p.add_argument("--sequence-length", type=int, default=6)
    p.add_argument("--train-steps", type=int, default=1800)
    p.add_argument("--train-batch-size", type=int, default=512)
    p.add_argument("--learning-rate", type=float, default=8e-4)
    p.add_argument("--eval-seeds", default="401,409,419,421,431,433")
    p.add_argument("--eval-batches", type=int, default=4)
    p.add_argument("--eval-batch-size", type=int, default=128)
    p.add_argument("--output-dir", default="artifacts/motif-probation")
    args = p.parse_args()

    model = load_checkpoint(Path(args.checkpoint)).eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)

    x, y, collection = collect_teacher_samples(
        model,
        left=args.left,
        right=args.right,
        batches=args.collect_batches,
        batch_size=args.collect_batch_size,
        sequence_length=args.sequence_length,
        seed=211,
    )

    composite, train_metrics = train_composite(
        x,
        y,
        hidden_dim=args.hidden_dim,
        steps=args.train_steps,
        batch_size=args.train_batch_size,
        learning_rate=args.learning_rate,
        seed=1000 + args.hidden_dim,
    )

    seeds = [
        int(value)
        for value in args.eval_seeds.split(",")
        if value.strip()
    ]
    evaluations = []

    for seed in seeds:
        teacher = evaluate_compiled(
            model,
            None,
            left=args.left,
            right=args.right,
            batches=args.eval_batches,
            batch_size=args.eval_batch_size,
            sequence_length=args.sequence_length,
            seed=seed,
        )
        student = evaluate_compiled(
            model,
            composite,
            left=args.left,
            right=args.right,
            batches=args.eval_batches,
            batch_size=args.eval_batch_size,
            sequence_length=args.sequence_length,
            seed=seed,
        )
        evaluations.append(
            {
                "seed": seed,
                "teacher_task_mae": teacher["task_mae"],
                "student_task_mae": student["task_mae"],
                "task_mae_delta": (
                    student["task_mae"] - teacher["task_mae"]
                ),
                "mean_abs_output_delta_vs_teacher": (
                    student["mean_abs_output_delta_vs_teacher"]
                ),
                "motif_use_fraction_of_thought_rows": (
                    student["motif_use_fraction_of_thought_rows"]
                ),
                "motif_uses": student["motif_uses"],
                "thought_rows": student["thought_rows"],
            }
        )

    deltas = [item["task_mae_delta"] for item in evaluations]
    output_deltas = [
        item["mean_abs_output_delta_vs_teacher"]
        for item in evaluations
    ]
    use_fractions = [
        item["motif_use_fraction_of_thought_rows"]
        for item in evaluations
    ]

    summary = {
        "mean_task_mae_delta": mean(deltas),
        "std_task_mae_delta": pstdev(deltas),
        "max_task_mae_delta": max(deltas),
        "min_task_mae_delta": min(deltas),
        "nonworse_fraction": (
            sum(value <= 0 for value in deltas) / len(deltas)
        ),
        "within_0_005_fraction": (
            sum(value <= 0.005 for value in deltas) / len(deltas)
        ),
        "mean_abs_output_delta_vs_teacher": mean(output_deltas),
        "mean_motif_use_fraction": mean(use_fractions),
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = out_dir / "motif-1-10-hidden64.pt"
    torch.save(
        {
            "schema": 1,
            "motif": [args.left, args.right],
            "hidden_dim": args.hidden_dim,
            "input_dim": x.shape[1],
            "target_dim": y.shape[1],
            "state_dict": composite.state_dict(),
            "training_collection": collection,
            "train_metrics": train_metrics,
            "probation_summary": summary,
        },
        checkpoint_path,
    )

    result = {
        "schema": 1,
        "motif": [args.left, args.right],
        "hidden_dim": args.hidden_dim,
        "parameters": composite.parameter_count(),
        "collection": {
            **collection,
            "samples": x.shape[0],
            "input_dim": x.shape[1],
            "target_dim": y.shape[1],
        },
        "train": train_metrics,
        "evaluations": evaluations,
        "summary": summary,
        "checkpoint": checkpoint_path.name,
    }

    result_path = out_dir / "probation.json"
    result_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
