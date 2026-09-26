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


CONTROLS = (
    "learned16",
    "learned64",
    "oracle16",
    "oracle64",
)


def _shape(control: str) -> Tuple[int, int]:
    if control in ("learned16", "oracle16"):
        return 16, 4
    if control in ("learned64", "oracle64"):
        return 64, 4
    raise ValueError(control)


def oracle_coalition(
    family_id: int,
    *,
    num_cells: int,
    active_cells: int,
) -> torch.Tensor:
    """
    Deterministic evaluator-only routing ceiling.

    Each family is assigned to one disjoint top-k coalition until all coalitions
    are used, then assignments wrap. With top-4 activation this means:

      16 cells -> 4 coalitions
      64 cells -> 16 coalitions

    As family diversity grows, the smaller bank is forced to share each
    coalition across more unrelated hidden dynamics. This intentionally removes
    learned routing quality from the question "is additional stored capacity
    useful if it can be allocated correctly?"
    """
    if num_cells % active_cells != 0:
        raise ValueError("num_cells must be divisible by active_cells")
    groups = num_cells // active_cells
    group = family_id % groups
    start = group * active_cells
    return torch.arange(start, start + active_cells, dtype=torch.long)


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
    oracle = control.startswith("oracle")

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
    total_loss = 0.0
    wall_ms = 0.0
    usage = torch.zeros(num_cells, dtype=torch.long)

    model.train()
    for experience in world.iter_all():
        events = experience.events.unsqueeze(0)
        targets = experience.targets.unsqueeze(0)

        forced = None
        if oracle:
            forced = oracle_coalition(
                experience.family_id,
                num_cells=num_cells,
                active_cells=active_cells,
            ).unsqueeze(0)

        start_ns = time.perf_counter_ns()
        outputs, new_state, traces = model(
            events,
            state,
            force_steps=thought_steps,
            add_training_noise=not oracle,
            return_trace=True,
            forced_selected=forced,
        )
        task_loss = F.smooth_l1_loss(outputs, targets)

        if oracle:
            routing_loss = task_loss.new_zeros(())
        else:
            router_scores = torch.cat(
                [
                    trace["router_scores"].reshape(-1, num_cells)
                    for trace in traces
                ],
                dim=0,
            )
            routing_loss = model.router_balance_loss(router_scores)

        loss = task_loss + balance_weight * routing_loss
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        wall_ms += (time.perf_counter_ns() - start_ns) / 1e6

        state = new_state.detach()

        selected = torch.cat(
            [
                trace["selected_cells"].reshape(-1)
                for trace in traces
            ],
            dim=0,
        ).detach().cpu()
        usage += torch.bincount(selected, minlength=num_cells)

        value = float(task_loss.detach())
        total_loss += value
        phase_loss_sum[experience.phase] += value
        phase_count[experience.phase] += 1

    total = world_config.total_experiences
    phase_means = {
        phase: phase_loss_sum[phase] / phase_count[phase]
        for phase in sorted(phase_count)
    }
    usage_fraction = (
        usage.float() / usage.sum().clamp_min(1)
    ).tolist()

    return {
        "control": control,
        "routing": "oracle" if oracle else "learned",
        "family_count": family_count,
        "world_seed": world_seed,
        "model_seed": model_seed,
        "total_experiences": total,
        "model_config": asdict(model_config),
        "parameter_count": model.parameter_count(),
        "mean_task_loss": total_loss / total,
        "late_mixed_loss": phase_means["mixed_return"],
        "phase_mean_loss": phase_means,
        "cell_usage_fraction": usage_fraction,
        "training_wall_ms_total": wall_ms,
        "training_wall_ms_per_experience": wall_ms / total,
    }


def summarize(runs: List[Dict[str, object]]) -> Dict[str, object]:
    grouped: Dict[int, Dict[int, Dict[str, Dict[str, object]]]] = {}
    for run in runs:
        families = int(run["family_count"])
        seed = int(run["world_seed"])
        grouped.setdefault(families, {}).setdefault(seed, {})[
            str(run["control"])
        ] = run

    result = {}
    for families, seed_groups in sorted(grouped.items()):
        learned_delta = []
        oracle_delta = []
        routing_gap16 = []
        routing_gap64 = []
        late_oracle_delta = []

        for seed, controls in sorted(seed_groups.items()):
            if set(controls) != set(CONTROLS):
                raise ValueError(
                    f"incomplete controls for families={families}, seed={seed}"
                )

            l16 = controls["learned16"]
            l64 = controls["learned64"]
            o16 = controls["oracle16"]
            o64 = controls["oracle64"]

            learned_delta.append(
                float(l64["mean_task_loss"])
                - float(l16["mean_task_loss"])
            )
            oracle_delta.append(
                float(o64["mean_task_loss"])
                - float(o16["mean_task_loss"])
            )
            routing_gap16.append(
                float(l16["mean_task_loss"])
                - float(o16["mean_task_loss"])
            )
            routing_gap64.append(
                float(l64["mean_task_loss"])
                - float(o64["mean_task_loss"])
            )
            late_oracle_delta.append(
                float(o64["late_mixed_loss"])
                - float(o16["late_mixed_loss"])
            )

        result[str(families)] = {
            "pairs": len(seed_groups),
            "mean_learned64_minus_learned16": mean(learned_delta),
            "learned64_wins": sum(x < 0 for x in learned_delta),
            "mean_oracle64_minus_oracle16": mean(oracle_delta),
            "oracle64_wins": sum(x < 0 for x in oracle_delta),
            "mean_learned_minus_oracle_16": mean(routing_gap16),
            "mean_learned_minus_oracle_64": mean(routing_gap64),
            "mean_late_oracle64_minus_oracle16":
                mean(late_oracle_delta),
        }

    return {"by_family_count": result}


def _parse_ints(value: str) -> List[int]:
    return [
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-counts", default="8,16,32,64")
    parser.add_argument("--seeds", default="501,502,503")
    parser.add_argument("--model-seed-base", type=int, default=6100)
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
                runs.append(
                    run_one(
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
                )

    payload = {
        "family_counts": family_counts,
        "seeds": seeds,
        "experiences_per_family": args.experiences_per_family,
        "summary": summarize(runs),
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
