from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
from statistics import mean
import time
from typing import Dict, List, Tuple

import torch
import torch.nn.functional as F

from .capacity_world import CapacityWorld, CapacityWorldConfig
from .model import EcologyConfig, SparseRecurrentEcology


CONTROLS = ("fixed16", "sparse64", "dense64")


def _shape(control: str) -> Tuple[int, int]:
    if control == "fixed16":
        return 16, 4
    if control == "sparse64":
        return 64, 4
    if control == "dense64":
        return 64, 64
    raise ValueError(control)


def run_one(
    *,
    control: str,
    family_count: int,
    world_seed: int,
    model_seed: int,
    experiences_per_family: int,
    sequence_length: int,
    state_dim: int,
    workspace_slots: int,
    signature_dim: int,
    message_dim: int,
    thought_steps: int,
    learning_rate: float,
    balance_weight: float,
) -> Dict[str, object]:
    torch.manual_seed(model_seed)

    world_config = CapacityWorldConfig(
        num_families=family_count,
        experiences_per_family=experiences_per_family,
        sequence_length=sequence_length,
        seed=world_seed,
    )
    world = CapacityWorld(world_config)

    num_cells, active_cells = _shape(control)
    model_config = EcologyConfig(
        event_dim=world_config.event_dim,
        output_dim=1,
        num_cells=num_cells,
        active_cells=active_cells,
        state_dim=state_dim,
        workspace_slots=workspace_slots,
        signature_dim=signature_dim,
        message_dim=message_dim,
        max_thought_steps=thought_steps,
        min_thought_steps=thought_steps,
        routing_noise_std=0.0,
        dense_training_compute=True,
    )
    model = SparseRecurrentEcology(model_config)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=1e-4,
    )
    state = model.initial_state(1)

    phase_loss_sum = defaultdict(float)
    phase_count = defaultdict(int)
    family_loss_sum = defaultdict(float)
    family_count_seen = defaultdict(int)
    total_loss = 0.0
    wall_ms = 0.0

    model.train()
    for experience in world.iter_all():
        events = experience.events.unsqueeze(0)
        targets = experience.targets.unsqueeze(0)

        start_ns = time.perf_counter_ns()
        outputs, new_state, traces = model(
            events,
            state,
            force_steps=thought_steps,
            add_training_noise=True,
            return_trace=True,
        )
        task_loss = F.smooth_l1_loss(outputs, targets)

        if active_cells < num_cells:
            router_scores = torch.cat(
                [
                    trace["router_scores"].reshape(-1, num_cells)
                    for trace in traces
                ],
                dim=0,
            )
            routing_loss = model.router_balance_loss(router_scores)
        else:
            routing_loss = task_loss.new_zeros(())

        loss = task_loss + balance_weight * routing_loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        wall_ms += (time.perf_counter_ns() - start_ns) / 1e6

        state = new_state.detach()

        value = float(task_loss.detach())
        total_loss += value
        phase_loss_sum[experience.phase] += value
        phase_count[experience.phase] += 1
        family_loss_sum[experience.family_id] += value
        family_count_seen[experience.family_id] += 1

    total = world_config.total_experiences
    phase_means = {
        phase: phase_loss_sum[phase] / phase_count[phase]
        for phase in sorted(phase_count)
    }
    family_means = {
        str(family_id):
            family_loss_sum[family_id] / family_count_seen[family_id]
        for family_id in sorted(family_count_seen)
    }

    return {
        "control": control,
        "family_count": family_count,
        "world_seed": world_seed,
        "model_seed": model_seed,
        "total_experiences": total,
        "model_config": asdict(model_config),
        "parameter_count": model.parameter_count(),
        "mean_task_loss": total_loss / total,
        "late_mixed_loss": phase_means["mixed_return"],
        "phase_mean_loss": phase_means,
        "family_mean_loss": family_means,
        "training_wall_ms_total": wall_ms,
        "training_wall_ms_per_experience": wall_ms / total,
    }


def _parse_ints(value: str) -> List[int]:
    result = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not result:
        raise ValueError("empty integer list")
    return result


def summarize(runs: List[Dict[str, object]]) -> Dict[str, object]:
    grouped: Dict[int, Dict[int, Dict[str, Dict[str, object]]]] = {}
    for run in runs:
        family_count = int(run["family_count"])
        seed = int(run["world_seed"])
        grouped.setdefault(family_count, {}).setdefault(seed, {})[
            str(run["control"])
        ] = run

    by_family_count = {}
    for family_count, seed_groups in sorted(grouped.items()):
        sparse_minus_fixed = []
        dense_minus_fixed = []
        late_sparse_minus_fixed = []

        for seed, controls in sorted(seed_groups.items()):
            if set(controls) != set(CONTROLS):
                raise ValueError(
                    f"incomplete control set for families={family_count}, seed={seed}"
                )
            fixed = controls["fixed16"]
            sparse = controls["sparse64"]
            dense = controls["dense64"]

            sparse_minus_fixed.append(
                float(sparse["mean_task_loss"])
                - float(fixed["mean_task_loss"])
            )
            dense_minus_fixed.append(
                float(dense["mean_task_loss"])
                - float(fixed["mean_task_loss"])
            )
            late_sparse_minus_fixed.append(
                float(sparse["late_mixed_loss"])
                - float(fixed["late_mixed_loss"])
            )

        by_family_count[str(family_count)] = {
            "pairs": len(seed_groups),
            "sparse64_wins_overall": sum(
                delta < 0 for delta in sparse_minus_fixed
            ),
            "dense64_wins_overall": sum(
                delta < 0 for delta in dense_minus_fixed
            ),
            "sparse64_wins_late": sum(
                delta < 0 for delta in late_sparse_minus_fixed
            ),
            "mean_sparse64_minus_fixed16":
                mean(sparse_minus_fixed),
            "mean_dense64_minus_fixed16":
                mean(dense_minus_fixed),
            "mean_late_sparse64_minus_fixed16":
                mean(late_sparse_minus_fixed),
        }

    return {"by_family_count": by_family_count}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-counts", default="8,16,32,64")
    parser.add_argument("--seeds", default="301,302,303")
    parser.add_argument("--model-seed-base", type=int, default=4100)
    parser.add_argument("--experiences-per-family", type=int, default=20)
    parser.add_argument("--sequence-length", type=int, default=4)
    parser.add_argument("--state-dim", type=int, default=24)
    parser.add_argument("--workspace-slots", type=int, default=3)
    parser.add_argument("--signature-dim", type=int, default=12)
    parser.add_argument("--message-dim", type=int, default=12)
    parser.add_argument("--thought-steps", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--balance-weight", type=float, default=0.01)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    family_counts = _parse_ints(args.family_counts)
    seeds = _parse_ints(args.seeds)
    runs: List[Dict[str, object]] = []

    for family_count in family_counts:
        for pair_index, world_seed in enumerate(seeds):
            model_seed = (
                args.model_seed_base
                + pair_index
                + 100 * family_count
            )
            for control in CONTROLS:
                run = run_one(
                    control=control,
                    family_count=family_count,
                    world_seed=world_seed,
                    model_seed=model_seed,
                    experiences_per_family=args.experiences_per_family,
                    sequence_length=args.sequence_length,
                    state_dim=args.state_dim,
                    workspace_slots=args.workspace_slots,
                    signature_dim=args.signature_dim,
                    message_dim=args.message_dim,
                    thought_steps=args.thought_steps,
                    learning_rate=args.learning_rate,
                    balance_weight=args.balance_weight,
                )
                runs.append(run)

    summary = summarize(runs)
    payload = {
        "family_counts": family_counts,
        "seeds": seeds,
        "experiences_per_family": args.experiences_per_family,
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
