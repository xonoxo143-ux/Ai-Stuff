from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import torch
from torch import Tensor

from .curriculum import OPS, held_out_bigrams, sample_forced_bigram_batch
from .export_onnx import load_checkpoint
from .model import SparseRecurrentEcology


def gather_selected(states: Tensor, selected: Tensor) -> Tensor:
    width = states.shape[-1]
    return torch.gather(
        states,
        dim=1,
        index=selected.unsqueeze(-1).expand(-1, -1, width),
    )


def thought_step_with_execution_lesion(
    model: SparseRecurrentEcology,
    event: Tensor,
    workspace: Tensor,
    cell_states: Tensor,
    lesion_cells: Set[int],
):
    """
    Preserve routing decisions, but prevent lesioned selected cells from
    updating private state or emitting public messages.

    This asks whether a cell's executed computation causally matters without
    letting the router compensate by selecting a different cell.
    """
    event_embedding = model.event_encoder(event)

    selected, route_weights, scores, _ = model._route(
        event_embedding,
        workspace,
        add_training_noise=False,
    )

    new_cell_states, messages = model._selected_cell_update(
        event_embedding,
        workspace,
        cell_states,
        selected,
        route_weights,
    )

    if lesion_cells:
        mask = torch.zeros_like(selected, dtype=torch.bool)
        for cell_id in lesion_cells:
            mask |= selected == cell_id

        original_selected = gather_selected(cell_states, selected)
        updated_selected = gather_selected(new_cell_states, selected)
        committed_selected = torch.where(
            mask.unsqueeze(-1),
            original_selected,
            updated_selected,
        )
        new_cell_states = new_cell_states.scatter(
            dim=1,
            index=selected.unsqueeze(-1).expand(
                -1, -1, model.config.state_dim
            ),
            src=committed_selected,
        )
        messages = torch.where(
            mask.unsqueeze(-1),
            torch.zeros_like(messages),
            messages,
        )

    new_workspace = model._workspace_write(workspace, messages)
    pooled = new_workspace.mean(dim=1)
    output = model.output_head(pooled)

    return output, new_workspace, new_cell_states, selected


def run_sequence(
    model: SparseRecurrentEcology,
    events: Tensor,
    *,
    lesion_cells: Set[int],
    thought_steps: int,
    collect_routing: bool = False,
):
    batch, time, _ = events.shape
    state = model.initial_state(
        batch,
        device=events.device,
        dtype=events.dtype,
    )

    outputs: List[Tensor] = []
    selected_history: List[Tensor] = []

    workspace = state.workspace
    cell_states = state.cell_states

    for t in range(time):
        output = None
        for _ in range(thought_steps):
            output, workspace, cell_states, selected = (
                thought_step_with_execution_lesion(
                    model,
                    events[:, t],
                    workspace,
                    cell_states,
                    lesion_cells,
                )
            )
            if collect_routing:
                selected_history.append(
                    torch.stack(
                        [
                            torch.full_like(selected, t),
                            selected,
                        ],
                        dim=-1,
                    )
                )
        assert output is not None
        outputs.append(output)

    return (
        torch.stack(outputs, dim=1),
        selected_history if collect_routing else None,
    )


def mae_by_operation(
    outputs: Tensor,
    targets: Tensor,
    op_ids: Tensor,
) -> Dict[str, float]:
    absolute = (outputs - targets).abs().squeeze(-1)
    result: Dict[str, float] = {}
    for op_index, op_name in enumerate(OPS):
        mask = op_ids == op_index
        if bool(mask.any()):
            result[op_name] = float(absolute[mask].mean().cpu())
    return result


def evaluate(
    model: SparseRecurrentEcology,
    dataset,
    *,
    lesion_cells: Set[int],
    thought_steps: int,
    collect_routing: bool = False,
):
    total_abs = 0.0
    total_values = 0
    op_abs = {name: 0.0 for name in OPS}
    op_count = {name: 0 for name in OPS}
    pair_counts: Counter[Tuple[int, int]] = Counter()
    cell_op_counts = {
        cell: {name: 0 for name in OPS}
        for cell in range(model.config.num_cells)
    }

    with torch.no_grad():
        for events, targets, op_ids in dataset:
            outputs, selected_history = run_sequence(
                model,
                events,
                lesion_cells=lesion_cells,
                thought_steps=thought_steps,
                collect_routing=collect_routing,
            )

            absolute = (outputs - targets).abs().squeeze(-1)
            total_abs += float(absolute.sum().cpu())
            total_values += absolute.numel()

            for op_index, op_name in enumerate(OPS):
                mask = op_ids == op_index
                if bool(mask.any()):
                    op_abs[op_name] += float(absolute[mask].sum().cpu())
                    op_count[op_name] += int(mask.sum().cpu())

            if collect_routing and selected_history is not None:
                # selected_history stores one entry per internal thought. Each
                # entry is [B,K,2] = (external event index, selected cell id).
                for record in selected_history:
                    event_indices = record[:, :, 0]
                    selected = record[:, :, 1]
                    for row in range(selected.shape[0]):
                        cells = sorted(set(selected[row].tolist()))
                        for pair in itertools.combinations(cells, 2):
                            pair_counts[pair] += 1

                        event_index = int(event_indices[row, 0])
                        op_name = OPS[int(op_ids[row, event_index])]
                        for cell in cells:
                            cell_op_counts[cell][op_name] += 1

    result = {
        "mae": total_abs / max(1, total_values),
        "mae_by_op": {
            name: op_abs[name] / op_count[name]
            for name in OPS
            if op_count[name] > 0
        },
    }
    if collect_routing:
        result["pair_counts"] = {
            f"{a},{b}": count
            for (a, b), count in pair_counts.items()
        }
        result["cell_op_counts"] = cell_op_counts
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument("--output", default="artifacts/specialization-analysis.json")
    p.add_argument("--seed", type=int, default=29)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--batches", type=int, default=4)
    p.add_argument("--sequence-length", type=int, default=6)
    p.add_argument("--pair-candidates", type=int, default=24)
    args = p.parse_args()

    torch.manual_seed(args.seed)
    model = load_checkpoint(Path(args.checkpoint)).eval()
    thought_steps = model.config.max_thought_steps

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

    singles = []
    for cell in range(model.config.num_cells):
        result = evaluate(
            model,
            dataset,
            lesion_cells={cell},
            thought_steps=thought_steps,
        )
        singles.append(
            {
                "cell": cell,
                "mae": result["mae"],
                "delta_mae": result["mae"] - baseline_mae,
                "mae_by_op": result["mae_by_op"],
                "delta_mae_by_op": {
                    op: result["mae_by_op"].get(op, 0.0)
                    - baseline["mae_by_op"].get(op, 0.0)
                    for op in baseline["mae_by_op"]
                },
            }
        )

    single_delta = {
        item["cell"]: item["delta_mae"]
        for item in singles
    }

    pair_counts = []
    for key, count in baseline["pair_counts"].items():
        left, right = map(int, key.split(","))
        pair_counts.append((count, left, right))
    pair_counts.sort(reverse=True)

    pairs = []
    for count, left, right in pair_counts[: args.pair_candidates]:
        result = evaluate(
            model,
            dataset,
            lesion_cells={left, right},
            thought_steps=thought_steps,
        )
        pair_delta = result["mae"] - baseline_mae
        additive_expected = (
            single_delta[left] + single_delta[right]
        )
        pairs.append(
            {
                "cells": [left, right],
                "baseline_coactivation_count": count,
                "mae": result["mae"],
                "delta_mae": pair_delta,
                "sum_single_delta_mae": additive_expected,
                "interaction_synergy_mae": (
                    pair_delta - additive_expected
                ),
            }
        )

    singles_by_effect = sorted(
        singles,
        key=lambda item: item["delta_mae"],
        reverse=True,
    )
    pairs_by_synergy = sorted(
        pairs,
        key=lambda item: item["interaction_synergy_mae"],
        reverse=True,
    )
    pairs_by_damage = sorted(
        pairs,
        key=lambda item: item["delta_mae"],
        reverse=True,
    )

    output = {
        "schema": 1,
        "analysis": "execution-lesion specialization and pair interaction screen",
        "model": {
            "num_cells": model.config.num_cells,
            "active_cells": model.config.active_cells,
            "thought_steps": thought_steps,
        },
        "dataset": {
            "seed": args.seed,
            "batch_size": args.batch_size,
            "batches": args.batches,
            "sequence_length": args.sequence_length,
            "examples": args.batch_size * args.batches,
            "forced_bigrams": list(held_out_bigrams()),
        },
        "baseline": baseline,
        "single_cell_lesions": singles,
        "top_cells_by_causal_damage": singles_by_effect[:8],
        "pair_screen": {
            "proposal_rule": "top baseline coactivation frequency",
            "candidate_count": len(pairs),
            "pairs": pairs,
            "top_pairs_by_interaction_synergy": pairs_by_synergy[:10],
            "top_pairs_by_causal_damage": pairs_by_damage[:10],
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))

    summary = {
        "baseline_mae": baseline_mae,
        "top_cells_by_causal_damage": [
            {
                "cell": item["cell"],
                "delta_mae": item["delta_mae"],
                "strongest_op_deltas": sorted(
                    item["delta_mae_by_op"].items(),
                    key=lambda pair: pair[1],
                    reverse=True,
                )[:3],
            }
            for item in singles_by_effect[:8]
        ],
        "top_pairs_by_interaction_synergy": pairs_by_synergy[:8],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
