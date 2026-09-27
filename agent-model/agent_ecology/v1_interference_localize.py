from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import torch
import torch.nn.functional as F

from .capacity_world import CapacityWorldConfig
from .interference_world import BlockedFamilyWorld
from .model import EcologyConfig, EcologyState, SparseRecurrentEcology


CONTROLS = ("fixed16", "sparse64")
INTERVENTIONS = (
    "baseline",
    "freeze_private",
    "freeze_router",
    "freeze_workspace",
    "freeze_shared",
)

_PRIVATE_CELL_NAMES = {
    "w_ih",
    "w_hh",
    "b_ih",
    "b_hh",
    "w_msg",
    "b_msg",
}


def _shape(control: str) -> Tuple[int, int]:
    if control == "fixed16":
        return 16, 4
    if control == "sparse64":
        return 64, 4
    raise ValueError(control)


def _parameter_category(name: str) -> str:
    root = name.split(".", 1)[0]
    if root in _PRIVATE_CELL_NAMES:
        return "private"
    if root in {"cell_signatures", "need_projection"}:
        return "router"
    if root in {
        "initial_workspace",
        "signature_read_query",
        "message_key",
        "message_value",
    }:
        return "workspace"
    return "shared"


def _copy_state(state: EcologyState) -> EcologyState:
    return EcologyState(
        workspace=state.workspace.detach().clone(),
        cell_states=state.cell_states.detach().clone(),
    )


def _evaluate_family(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    family_id: int,
    *,
    eval_examples: int,
    thought_steps: int,
) -> float:
    events, targets = world.batch(
        family_id,
        eval_examples,
        stream=1,
    )
    was_training = model.training
    model.eval()
    with torch.no_grad():
        outputs, _, _ = model(
            events,
            force_steps=thought_steps,
            add_training_noise=False,
            return_trace=False,
        )
        loss = F.smooth_l1_loss(outputs, targets)
    model.train(was_training)
    return float(loss.cpu())


def _train_family(
    model: SparseRecurrentEcology,
    optimizer: torch.optim.Optimizer,
    state: EcologyState,
    world: BlockedFamilyWorld,
    family_id: int,
    *,
    train_examples: int,
    thought_steps: int,
    balance_weight: float,
) -> EcologyState:
    model.train()
    for sample_index in range(train_examples):
        sample = world.sample(
            family_id,
            sample_index,
            stream=0,
        )
        outputs, new_state, traces = model(
            sample.events.unsqueeze(0),
            state,
            force_steps=thought_steps,
            add_training_noise=True,
            return_trace=True,
        )
        task_loss = F.smooth_l1_loss(
            outputs,
            sample.targets.unsqueeze(0),
        )

        router_scores = torch.cat(
            [
                trace["router_scores"].reshape(
                    -1,
                    model.config.num_cells,
                )
                for trace in traces
            ],
            dim=0,
        )
        loss = (
            task_loss
            + balance_weight * model.router_balance_loss(router_scores)
        )

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        state = new_state.detach()

    return state


def _freeze_for_intervention(
    model: SparseRecurrentEcology,
    intervention: str,
) -> None:
    if intervention == "baseline":
        return

    target = {
        "freeze_private": "private",
        "freeze_router": "router",
        "freeze_workspace": "workspace",
        "freeze_shared": "shared",
    }[intervention]

    for name, parameter in model.named_parameters():
        if _parameter_category(name) == target:
            parameter.requires_grad_(False)


def _anchor_families(after_family: int) -> List[int]:
    if after_family < 0:
        return []
    values = {
        0,
        after_family // 4,
        after_family // 2,
        (3 * after_family) // 4,
        after_family,
    }
    return sorted(values)


def _branch_intervention(
    *,
    model: SparseRecurrentEcology,
    optimizer: torch.optim.Optimizer,
    state: EcologyState,
    world: BlockedFamilyWorld,
    after_family: int,
    intervention: str,
    train_examples: int,
    eval_examples: int,
    thought_steps: int,
    learning_rate: float,
    balance_weight: float,
) -> Dict[str, object]:
    next_family = after_family + 1
    anchors = _anchor_families(after_family)

    before_old = {
        family: _evaluate_family(
            model,
            world,
            family,
            eval_examples=eval_examples,
            thought_steps=thought_steps,
        )
        for family in anchors
    }
    pre_new = _evaluate_family(
        model,
        world,
        next_family,
        eval_examples=eval_examples,
        thought_steps=thought_steps,
    )

    branch = copy.deepcopy(model)
    branch_state = _copy_state(state)
    _freeze_for_intervention(branch, intervention)

    branch_optimizer = torch.optim.AdamW(
        branch.parameters(),
        lr=learning_rate,
        weight_decay=1e-4,
    )
    branch_optimizer.load_state_dict(
        copy.deepcopy(optimizer.state_dict())
    )

    branch_state = _train_family(
        branch,
        branch_optimizer,
        branch_state,
        world,
        next_family,
        train_examples=train_examples,
        thought_steps=thought_steps,
        balance_weight=balance_weight,
    )

    after_old = {
        family: _evaluate_family(
            branch,
            world,
            family,
            eval_examples=eval_examples,
            thought_steps=thought_steps,
        )
        for family in anchors
    }
    post_new = _evaluate_family(
        branch,
        world,
        next_family,
        eval_examples=eval_examples,
        thought_steps=thought_steps,
    )

    old_damage = [
        after_old[family] - before_old[family]
        for family in anchors
    ]

    return {
        "intervention": intervention,
        "after_family": after_family,
        "next_family": next_family,
        "anchor_families": anchors,
        "before_old_loss": before_old,
        "after_old_loss": after_old,
        "mean_old_damage": mean(old_damage),
        "pre_new_loss": pre_new,
        "post_new_loss": post_new,
        "new_learning_gain": pre_new - post_new,
    }


def run_one(
    *,
    control: str,
    family_count: int,
    world_seed: int,
    model_seed: int,
    checkpoints_after: Sequence[int],
    train_examples: int,
    eval_examples: int,
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
        experiences_per_family=train_examples,
        sequence_length=sequence_length,
        seed=world_seed,
    )
    world = BlockedFamilyWorld(world_config)

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

    checkpoint_set = set(checkpoints_after)
    if any(
        index < 0 or index >= family_count - 1
        for index in checkpoint_set
    ):
        raise ValueError(
            "checkpoints must be in [0, family_count - 2]"
        )

    checkpoints: List[Dict[str, object]] = []

    for family_id in range(family_count):
        state = _train_family(
            model,
            optimizer,
            state,
            world,
            family_id,
            train_examples=train_examples,
            thought_steps=thought_steps,
            balance_weight=balance_weight,
        )

        if family_id in checkpoint_set:
            branches = [
                _branch_intervention(
                    model=model,
                    optimizer=optimizer,
                    state=state,
                    world=world,
                    after_family=family_id,
                    intervention=intervention,
                    train_examples=train_examples,
                    eval_examples=eval_examples,
                    thought_steps=thought_steps,
                    learning_rate=learning_rate,
                    balance_weight=balance_weight,
                )
                for intervention in INTERVENTIONS
            ]
            baseline = next(
                row for row in branches
                if row["intervention"] == "baseline"
            )

            comparisons = []
            for row in branches:
                comparisons.append(
                    {
                        **row,
                        "protection_vs_baseline":
                            float(baseline["mean_old_damage"])
                            - float(row["mean_old_damage"]),
                        "learning_cost_vs_baseline":
                            float(baseline["new_learning_gain"])
                            - float(row["new_learning_gain"]),
                    }
                )

            checkpoints.append(
                {
                    "after_family": family_id,
                    "next_family": family_id + 1,
                    "branches": comparisons,
                }
            )

    return {
        "control": control,
        "family_count": family_count,
        "world_seed": world_seed,
        "model_seed": model_seed,
        "checkpoints_after": list(checkpoints_after),
        "model_config": asdict(model_config),
        "checkpoints": checkpoints,
    }


def summarize(runs: Iterable[Dict[str, object]]) -> Dict[str, object]:
    grouped: Dict[str, List[Dict[str, object]]] = {
        control: [] for control in CONTROLS
    }
    for run in runs:
        grouped[str(run["control"])].append(run)

    result: Dict[str, object] = {}
    for control, control_runs in grouped.items():
        intervention_rows: Dict[str, Dict[str, List[float]]] = {
            intervention: {
                "damage": [],
                "learning_gain": [],
                "protection": [],
                "learning_cost": [],
            }
            for intervention in INTERVENTIONS
        }

        by_checkpoint: Dict[str, Dict[str, List[float]]] = {}

        for run in control_runs:
            for checkpoint in run["checkpoints"]:
                checkpoint_key = str(checkpoint["after_family"])
                by_checkpoint.setdefault(
                    checkpoint_key,
                    {
                        intervention: []
                        for intervention in INTERVENTIONS
                    },
                )
                for row in checkpoint["branches"]:
                    name = str(row["intervention"])
                    intervention_rows[name]["damage"].append(
                        float(row["mean_old_damage"])
                    )
                    intervention_rows[name]["learning_gain"].append(
                        float(row["new_learning_gain"])
                    )
                    intervention_rows[name]["protection"].append(
                        float(row["protection_vs_baseline"])
                    )
                    intervention_rows[name]["learning_cost"].append(
                        float(row["learning_cost_vs_baseline"])
                    )
                    by_checkpoint[checkpoint_key][name].append(
                        float(row["protection_vs_baseline"])
                    )

        aggregate = {}
        for intervention, values in intervention_rows.items():
            aggregate[intervention] = {
                "mean_old_damage": mean(values["damage"]),
                "mean_new_learning_gain":
                    mean(values["learning_gain"]),
                "mean_protection_vs_baseline":
                    mean(values["protection"]),
                "mean_learning_cost_vs_baseline":
                    mean(values["learning_cost"]),
                "protection_positive_count":
                    sum(value > 0 for value in values["protection"]),
                "observations": len(values["damage"]),
            }

        checkpoint_summary = {
            checkpoint: {
                intervention: mean(values)
                for intervention, values in interventions.items()
            }
            for checkpoint, interventions in by_checkpoint.items()
        }

        result[control] = {
            "runs": len(control_runs),
            "aggregate": aggregate,
            "mean_protection_by_checkpoint": checkpoint_summary,
        }

    return {"by_control": result}


def _parse_ints(value: str) -> List[int]:
    values = [
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    ]
    if not values:
        raise ValueError("empty integer list")
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-count", type=int, default=64)
    parser.add_argument("--seeds", default="1101,1102,1103")
    parser.add_argument("--model-seed-base", type=int, default=12000)
    parser.add_argument("--checkpoints-after", default="7,15,31,47")
    parser.add_argument("--train-examples", type=int, default=20)
    parser.add_argument("--eval-examples", type=int, default=16)
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

    seeds = _parse_ints(args.seeds)
    checkpoints = _parse_ints(args.checkpoints_after)
    runs: List[Dict[str, object]] = []

    for pair_index, world_seed in enumerate(seeds):
        model_seed = args.model_seed_base + pair_index
        for control in CONTROLS:
            runs.append(
                run_one(
                    control=control,
                    family_count=args.family_count,
                    world_seed=world_seed,
                    model_seed=model_seed,
                    checkpoints_after=checkpoints,
                    train_examples=args.train_examples,
                    eval_examples=args.eval_examples,
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
        "family_count": args.family_count,
        "seeds": seeds,
        "checkpoints_after": checkpoints,
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
