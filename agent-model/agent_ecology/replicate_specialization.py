from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

import torch

from .analyze_specialization import evaluate
from .curriculum import held_out_bigrams, sample_forced_bigram_batch
from .export_onnx import load_checkpoint


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument("--output", default="artifacts/specialization-replication.json")
    p.add_argument("--seeds", default="31,37,41,43,47,53")
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--batches", type=int, default=2)
    p.add_argument("--sequence-length", type=int, default=6)
    p.add_argument("--pair-candidates", type=int, default=20)
    args = p.parse_args()

    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    model = load_checkpoint(Path(args.checkpoint)).eval()
    thought_steps = model.config.max_thought_steps

    runs = []
    per_cell = defaultdict(list)
    per_pair = defaultdict(list)
    per_pair_coactivation = defaultdict(list)

    for seed in seeds:
        torch.manual_seed(seed)
        dataset = [
            sample_forced_bigram_batch(
                args.batch_size,
                args.sequence_length,
                bigrams=held_out_bigrams(),
            )
            for _ in range(args.batches)
        ]

        baseline = evaluate(
            model,
            dataset,
            lesion_cells=set(),
            thought_steps=thought_steps,
            collect_routing=True,
        )
        baseline_mae = baseline["mae"]

        singles = {}
        for cell in range(model.config.num_cells):
            result = evaluate(
                model,
                dataset,
                lesion_cells={cell},
                thought_steps=thought_steps,
            )
            delta = result["mae"] - baseline_mae
            singles[cell] = delta
            per_cell[cell].append(delta)

        pair_counts = []
        for key, count in baseline["pair_counts"].items():
            left, right = map(int, key.split(","))
            pair_counts.append((count, left, right))
        pair_counts.sort(reverse=True)

        pair_results = []
        for count, left, right in pair_counts[: args.pair_candidates]:
            result = evaluate(
                model,
                dataset,
                lesion_cells={left, right},
                thought_steps=thought_steps,
            )
            pair_delta = result["mae"] - baseline_mae
            synergy = pair_delta - singles[left] - singles[right]
            key = (left, right)
            per_pair[key].append(synergy)
            per_pair_coactivation[key].append(count)
            pair_results.append(
                {
                    "cells": [left, right],
                    "coactivation_count": count,
                    "delta_mae": pair_delta,
                    "interaction_synergy_mae": synergy,
                }
            )

        runs.append(
            {
                "seed": seed,
                "baseline_mae": baseline_mae,
                "single_delta_mae": singles,
                "top_positive_pairs": sorted(
                    pair_results,
                    key=lambda item: item["interaction_synergy_mae"],
                    reverse=True,
                )[:8],
            }
        )

    cell_summary = []
    for cell in range(model.config.num_cells):
        values = per_cell[cell]
        cell_summary.append(
            {
                "cell": cell,
                "mean_delta_mae": mean(values),
                "std_delta_mae": pstdev(values),
                "positive_fraction": sum(v > 0 for v in values) / len(values),
                "values": values,
            }
        )

    pair_summary = []
    all_pairs = set(per_pair)
    for pair in sorted(all_pairs):
        values = per_pair[pair]
        counts = per_pair_coactivation[pair]
        pair_summary.append(
            {
                "cells": list(pair),
                "replications": len(values),
                "mean_interaction_synergy_mae": mean(values),
                "std_interaction_synergy_mae": pstdev(values),
                "positive_fraction": sum(v > 0 for v in values) / len(values),
                "mean_coactivation_count": mean(counts),
                "values": values,
            }
        )

    # Highlight pairs that appeared in every replication; this is stricter than
    # merely being proposed once.
    stable_pairs = [
        item
        for item in pair_summary
        if item["replications"] == len(seeds)
    ]
    stable_pairs.sort(
        key=lambda item: item["mean_interaction_synergy_mae"],
        reverse=True,
    )

    output = {
        "schema": 1,
        "analysis": "fresh-data replication of cell lesions and pair interactions",
        "model": {
            "num_cells": model.config.num_cells,
            "active_cells": model.config.active_cells,
            "thought_steps": thought_steps,
        },
        "seeds": seeds,
        "examples_per_seed": args.batch_size * args.batches,
        "runs": runs,
        "cell_summary": sorted(
            cell_summary,
            key=lambda item: item["mean_delta_mae"],
            reverse=True,
        ),
        "pair_summary": sorted(
            pair_summary,
            key=lambda item: item["mean_interaction_synergy_mae"],
            reverse=True,
        ),
        "stable_pairs": stable_pairs,
    }

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2))

    print(
        json.dumps(
            {
                "top_cells": output["cell_summary"][:8],
                "top_stable_pairs": stable_pairs[:10],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
