from __future__ import annotations

import argparse
import copy
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
    "freeze_all_private",
    "freeze_old_top4",
    "freeze_random4",
    "freeze_old_bottom4",
)

_PRIVATE_CELL_NAMES = (
    "w_ih",
    "w_hh",
    "b_ih",
    "b_hh",
    "w_msg",
    "b_msg",
)


def _shape(control: str) -> Tuple[int, int]:
    if control == "fixed16":
        return 16, 4
    if control == "sparse64":
        return 64, 4
    raise ValueError(control)


def _copy_state(state: EcologyState) -> EcologyState:
    return EcologyState(
        workspace=state.workspace.detach().clone(),
        cell_states=state.cell_states.detach().clone(),
    )


def _anchor_families(after_family: int) -> List[int]:
    values = {
        0,
        after_family // 4,
        after_family // 2,
        (3 * after_family) // 4,
        after_family,
    }
    return sorted(values)


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


def _usage_on_families(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    families: Sequence[int],
    *,
    eval_examples: int,
    thought_steps: int,
) -> List[float]:
    usage = torch.zeros(
        model.config.num_cells,
        dtype=torch.float64,
    )
    was_training = model.training
    model.eval()

    with torch.no_grad():
        for family_id in families:
            events, _targets = world.batch(
                family_id,
                eval_examples,
                stream=1,
            )
            _outputs, _state, traces = model(
                events,
                force_steps=thought_steps,
                add_training_noise=False,
                return_trace=True,
            )
            selected = torch.cat(
                [
                    trace["selected_cells"].reshape(-1)
                    for trace in traces
                ],
                dim=0,
            ).cpu()
            usage += torch.bincount(
                selected,
                minlength=model.config.num_cells,
            ).double()

    model.train(was_training)
    usage /= usage.sum().clamp_min(1.0)
    return usage.tolist()


def _select_cell_sets(
    usage: Sequence[float],
    *,
    random_seed: int,
    width: int = 4,
) -> Dict[str, List[int]]:
    values = torch.tensor(usage, dtype=torch.float64)
    num_cells = values.numel()
    width = min(width, num_cells)

    top = torch.argsort(
        values,
        descending=True,
        stable=True,
    )[:width].tolist()
    bottom = torch.argsort(
        values,
        descending=False,
        stable=True,
    )[:width].tolist()

    top_set = set(top)
    candidates = [
        index
        for index in range(num_cells)
        if index not in top_set
    ]
    if len(candidates) < width:
        candidates = list(range(num_cells))

    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(random_seed))
    order = torch.randperm(
        len(candidates),
        generator=generator,
    )[:width].tolist()
    random_cells = [candidates[index] for index in order]

    return {
        "freeze_all_private": list(range(num_cells)),
        "freeze_old_top4": top,
        "freeze_random4": random_cells,
        "freeze_old_bottom4": bottom,
    }


def _private_row_snapshot(
    model: SparseRecurrentEcology,
    frozen_cells: Sequence[int],
) -> Dict[str, torch.Tensor]:
    if not frozen_cells:
        return {}
    index = torch.tensor(
        list(frozen_cells),
        dtype=torch.long,
    )
    named = dict(model.named_parameters())
    return {
        name: named[name].detach().index_select(0, index).clone()
        for name in _PRIVATE_CELL_NAMES
    }


def _restore_private_rows(
    model: SparseRecurrentEcology,
    frozen_cells: Sequence[int],
    snapshot: Mapping[str, torch.Tensor],
) -> None:
    if not frozen_cells:
        return
    index = torch.tensor(
        list(frozen_cells),
        dtype=torch.long,
    )
    named = dict(model.named_parameters())
    with torch.no_grad():
        for name in _PRIVATE_CELL_NAMES:
            named[name].index_copy_(0, index, snapshot[name])


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
    frozen_private_cells: Sequence[int] = (),
) -> EcologyState:
    frozen_snapshot = _private_row_snapshot(
        model,
        frozen_private_cells,
    )

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

        _restore_private_rows(
            model,
            frozen_private_cells,
            frozen_snapshot,
        )
        state = new_state.detach()

    return state


def _branch(
    *,
    model: SparseRecurrentEcology,
    optimizer: torch.optim.Optimizer,
    state: EcologyState,
    world: BlockedFamilyWorld,
    next_family: int,
    anchors: Sequence[int],
    before_old: Mapping[int, float],
    pre_new: float,
    frozen_cells: Sequence[int],
    train_examples: int,
    eval_examples: int,
    thought_steps: int,
    learning_rate: float,
    balance_weight: float,
) -> Dict[str, object]:
    branch = copy.deepcopy(model)
    branch_state = _copy_state(state)

    branch_optimizer = torch.optim.AdamW(
        branch.parameters(),
        lr=learning_rate,
        weight_decay=1e-4,
    )
    branch_optimizer.load_state_dict(
        copy.deepcopy(optimizer.state_dict())
    )

    _train_family(
        branch,
        branch_optimizer,
        branch_state,
        world,
        next_family,
        train_examples=train_examples,
        thought_steps=thought_steps,
        balance_weight=balance_weight,
        frozen_private_cells=frozen_cells,
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

    damage_by_family = {
        family: after_old[family] - before_old[family]
        for family in anchors
    }

    return {
        "frozen_cells": list(frozen_cells),
        "after_old_loss": after_old,
        "damage_by_family": damage_by_family,
        "mean_old_damage": mean(damage_by_family.values()),
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
    events: List[Dict[str, object]] = []

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

        if family_id not in checkpoint_set:
            continue

        next_family = family_id + 1
        if next_family >= family_count:
            continue

        anchors = _anchor_families(family_id)
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
        usage = _usage_on_families(
            model,
            world,
            anchors,
            eval_examples=eval_examples,
            thought_steps=thought_steps,
        )

        cell_sets = _select_cell_sets(
            usage,
            random_seed=(
                1_000_003 * world_seed
                + 9_973 * model_seed
                + family_id
            ),
            width=4,
        )

        baseline = _branch(
            model=model,
            optimizer=optimizer,
            state=state,
            world=world,
            next_family=next_family,
            anchors=anchors,
            before_old=before_old,
            pre_new=pre_new,
            frozen_cells=(),
            train_examples=train_examples,
            eval_examples=eval_examples,
            thought_steps=thought_steps,
            learning_rate=learning_rate,
            balance_weight=balance_weight,
        )

        event: Dict[str, object] = {
            "after_family": family_id,
            "next_family": next_family,
            "anchor_families": anchors,
            "old_usage_fraction": usage,
            "before_old_loss": before_old,
            "pre_new_loss": pre_new,
            "baseline": baseline,
            "triggered": bool(
                float(baseline["mean_old_damage"]) > 0.0
            ),
            "cell_sets": cell_sets,
            "interventions": [],
        }

        if event["triggered"]:
            rows = []
            for intervention in INTERVENTIONS[1:]:
                branch_result = _branch(
                    model=model,
                    optimizer=optimizer,
                    state=state,
                    world=world,
                    next_family=next_family,
                    anchors=anchors,
                    before_old=before_old,
                    pre_new=pre_new,
                    frozen_cells=cell_sets[intervention],
                    train_examples=train_examples,
                    eval_examples=eval_examples,
                    thought_steps=thought_steps,
                    learning_rate=learning_rate,
                    balance_weight=balance_weight,
                )
                rows.append(
                    {
                        "intervention": intervention,
                        **branch_result,
                        "protection_vs_baseline":
                            float(baseline["mean_old_damage"])
                            - float(branch_result["mean_old_damage"]),
                        "learning_cost_vs_baseline":
                            float(baseline["new_learning_gain"])
                            - float(branch_result["new_learning_gain"]),
                    }
                )
            event["interventions"] = rows

        events.append(event)

    return {
        "control": control,
        "family_count": family_count,
        "world_seed": world_seed,
        "model_seed": model_seed,
        "events": events,
    }


def summarize(runs: Iterable[Dict[str, object]]) -> Dict[str, object]:
    result: Dict[str, object] = {}

    for control in CONTROLS:
        control_runs = [
            run for run in runs
            if run["control"] == control
        ]
        triggered = [
            event
            for run in control_runs
            for event in run["events"]
            if event["triggered"]
        ]

        by_intervention: Dict[str, Dict[str, List[float]]] = {
            name: {"protection": [], "cost": []}
            for name in INTERVENTIONS[1:]
        }

        for event in triggered:
            for row in event["interventions"]:
                name = str(row["intervention"])
                by_intervention[name]["protection"].append(
                    float(row["protection_vs_baseline"])
                )
                by_intervention[name]["cost"].append(
                    float(row["learning_cost_vs_baseline"])
                )

        aggregate = {}
        for name, values in by_intervention.items():
            protection = values["protection"]
            cost = values["cost"]
            if protection:
                aggregate[name] = {
                    "mean_protection": mean(protection),
                    "median_protection": sorted(protection)[
                        len(protection) // 2
                    ],
                    "positive_protection_count":
                        sum(value > 0 for value in protection),
                    "mean_learning_cost": mean(cost),
                    "observations": len(protection),
                }
            else:
                aggregate[name] = {
                    "mean_protection": None,
                    "median_protection": None,
                    "positive_protection_count": 0,
                    "mean_learning_cost": None,
                    "observations": 0,
                }

        top = by_intervention["freeze_old_top4"]
        random = by_intervention["freeze_random4"]
        bottom = by_intervention["freeze_old_bottom4"]
        all_private = by_intervention["freeze_all_private"]

        def paired_mean(left: List[float], right: List[float]):
            if not left:
                return None
            return mean(a - b for a, b in zip(left, right))

        result[control] = {
            "runs": len(control_runs),
            "screened_events": sum(
                len(run["events"])
                for run in control_runs
            ),
            "triggered_events": len(triggered),
            "aggregate": aggregate,
            "mean_top4_protection_minus_random":
                paired_mean(top["protection"], random["protection"]),
            "mean_top4_protection_minus_bottom":
                paired_mean(top["protection"], bottom["protection"]),
            "mean_top4_learning_cost_minus_all_private":
                paired_mean(top["cost"], all_private["cost"]),
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
    parser.add_argument("--seeds", default="1301,1302,1303")
    parser.add_argument("--model-seed-base", type=int, default=14000)
    parser.add_argument(
        "--checkpoints-after",
        default="7,15,23,31,39,47,55",
    )
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
    runs = []

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
