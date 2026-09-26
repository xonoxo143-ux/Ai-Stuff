from __future__ import annotations

import argparse
from argparse import Namespace
import json
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List

from .v1_controls import run_control


CONTROLS = ("fixed16", "sparse64", "dense64")


def summarize_runs(runs: Iterable[Dict[str, object]]) -> Dict[str, object]:
    rows = list(runs)
    by_pair: Dict[int, Dict[str, Dict[str, object]]] = {}
    for row in rows:
        pair = int(row["pair_index"])
        by_pair.setdefault(pair, {})[str(row["control"])] = row

    paired = []
    regime_deltas: Dict[str, List[float]] = {}

    for pair in sorted(by_pair):
        group = by_pair[pair]
        if set(group) != set(CONTROLS):
            raise ValueError(f"incomplete control set for pair {pair}")

        f16 = float(group["fixed16"]["mean_task_loss"])
        s64 = float(group["sparse64"]["mean_task_loss"])
        d64 = float(group["dense64"]["mean_task_loss"])

        paired.append(
            {
                "pair_index": pair,
                "world_seed": int(group["fixed16"]["world_seed"]),
                "model_seed": int(group["fixed16"]["model_seed"]),
                "fixed16": f16,
                "sparse64": s64,
                "dense64": d64,
                "sparse64_minus_fixed16": s64 - f16,
                "dense64_minus_fixed16": d64 - f16,
                "dense64_minus_sparse64": d64 - s64,
            }
        )

        fixed_regimes = group["fixed16"]["per_regime"]
        sparse_regimes = group["sparse64"]["per_regime"]
        for regime in fixed_regimes:
            if regime in sparse_regimes:
                delta = (
                    float(sparse_regimes[regime]["mean_task_loss"])
                    - float(fixed_regimes[regime]["mean_task_loss"])
                )
                regime_deltas.setdefault(regime, []).append(delta)

    sparse_deltas = [row["sparse64_minus_fixed16"] for row in paired]
    dense_vs_fixed = [row["dense64_minus_fixed16"] for row in paired]
    dense_vs_sparse = [row["dense64_minus_sparse64"] for row in paired]

    return {
        "pairs": paired,
        "aggregate": {
            "num_pairs": len(paired),
            "sparse64_wins_vs_fixed16": sum(x < 0 for x in sparse_deltas),
            "dense64_wins_vs_fixed16": sum(x < 0 for x in dense_vs_fixed),
            "sparse64_wins_vs_dense64": sum(x > 0 for x in dense_vs_sparse),
            "mean_sparse64_minus_fixed16": mean(sparse_deltas),
            "mean_dense64_minus_fixed16": mean(dense_vs_fixed),
            "mean_dense64_minus_sparse64": mean(dense_vs_sparse),
            "mean_regime_sparse64_minus_fixed16": {
                regime: mean(values)
                for regime, values in sorted(regime_deltas.items())
            },
        },
    }


def parse_seed_list(value: str) -> List[int]:
    seeds = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not seeds:
        raise ValueError("at least one world seed is required")
    return seeds


def build_run_args(
    args: argparse.Namespace,
    *,
    control: str,
    world_seed: int,
    model_seed: int,
) -> Namespace:
    return Namespace(
        control=control,
        world_size=args.world_size,
        experiences=args.experiences,
        start=0,
        sequence_length=args.sequence_length,
        world_seed=world_seed,
        model_seed=model_seed,
        state_dim=args.state_dim,
        workspace_slots=args.workspace_slots,
        signature_dim=args.signature_dim,
        message_dim=args.message_dim,
        thought_steps=args.thought_steps,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        balance_weight=args.balance_weight,
        routing_noise_std=args.routing_noise_std,
        log_every=args.log_every,
        device=args.device,
        output=None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paired multi-seed Agent v1-A1 control replication."
    )
    parser.add_argument("--seeds", default="91,92,93,94,95")
    parser.add_argument("--model-seed-base", type=int, default=1700)
    parser.add_argument("--world-size", type=int, default=500)
    parser.add_argument("--experiences", type=int, default=500)
    parser.add_argument("--sequence-length", type=int, default=4)
    parser.add_argument("--state-dim", type=int, default=24)
    parser.add_argument("--workspace-slots", type=int, default=3)
    parser.add_argument("--signature-dim", type=int, default=12)
    parser.add_argument("--message-dim", type=int, default=12)
    parser.add_argument("--thought-steps", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--balance-weight", type=float, default=0.01)
    parser.add_argument("--routing-noise-std", type=float, default=0.0)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    world_seeds = parse_seed_list(args.seeds)
    runs = []

    for pair_index, world_seed in enumerate(world_seeds):
        model_seed = args.model_seed_base + pair_index
        for control in CONTROLS:
            result = run_control(
                build_run_args(
                    args,
                    control=control,
                    world_seed=world_seed,
                    model_seed=model_seed,
                )
            )
            result["pair_index"] = pair_index
            runs.append(result)

    summary = summarize_runs(runs)
    payload = {
        "config": {
            "world_seeds": world_seeds,
            "model_seed_base": args.model_seed_base,
            "world_size": args.world_size,
            "experiences": args.experiences,
            "sequence_length": args.sequence_length,
            "state_dim": args.state_dim,
            "thought_steps": args.thought_steps,
        },
        "summary": summary,
        "runs": runs,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
