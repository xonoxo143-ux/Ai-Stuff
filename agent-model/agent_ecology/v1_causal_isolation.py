from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median
from typing import Dict, Iterable, List, Sequence, Tuple

import torch
import torch.nn.functional as F

from .analyze_specialization import run_sequence
from .capacity_world import CapacityWorldConfig
from .interference_world import BlockedFamilyWorld
from .model import EcologyConfig, SparseRecurrentEcology
from .v1_selective_isolation import (
    CONTROLS,
    _anchor_families,
    _branch,
    _copy_state,
    _evaluate_family,
    _shape,
    _train_family,
    _usage_on_families,
)


INTERVENTIONS = (
    "freeze_all_private",
    "freeze_causal_top4",
    "freeze_usage_top4",
    "freeze_random4",
    "freeze_causal_bottom4",
)


def _evaluate_family_with_lesion(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    family_id: int,
    *,
    lesion_cells: set[int],
    eval_examples: int,
    thought_steps: int,
) -> float:
    events, targets = world.batch(
        family_id,
        eval_examples,
        stream=2,
    )
    was_training = model.training
    model.eval()
    with torch.no_grad():
        outputs, _ = run_sequence(
            model,
            events,
            lesion_cells=lesion_cells,
            thought_steps=thought_steps,
            collect_routing=False,
        )
        loss = F.smooth_l1_loss(outputs, targets)
    model.train(was_training)
    return float(loss.cpu())


def causal_cell_scores(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    families: Sequence[int],
    *,
    eval_examples: int,
    thought_steps: int,
) -> List[float]:
    baseline = {
        family: _evaluate_family_with_lesion(
            model,
            world,
            family,
            lesion_cells=set(),
            eval_examples=eval_examples,
            thought_steps=thought_steps,
        )
        for family in families
    }

    scores = []
    for cell in range(model.config.num_cells):
        deltas = []
        for family in families:
            lesioned = _evaluate_family_with_lesion(
                model,
                world,
                family,
                lesion_cells={cell},
                eval_examples=eval_examples,
                thought_steps=thought_steps,
            )
            deltas.append(lesioned - baseline[family])
        scores.append(mean(deltas))

    return scores


def _rank_cells(
    values: Sequence[float],
    *,
    descending: bool,
    width: int,
) -> List[int]:
    tensor = torch.tensor(values, dtype=torch.float64)
    order = torch.argsort(
        tensor,
        descending=descending,
        stable=True,
    )
    return order[: min(width, len(values))].tolist()


def _random_cells(
    *,
    num_cells: int,
    exclude: Sequence[int],
    width: int,
    seed: int,
) -> List[int]:
    excluded = set(exclude)
    candidates = [
        index
        for index in range(num_cells)
        if index not in excluded
    ]
    if len(candidates) < width:
        candidates = list(range(num_cells))

    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    order = torch.randperm(
        len(candidates),
        generator=generator,
    )[:width].tolist()
    return [candidates[index] for index in order]


def _build_cell_sets(
    *,
    causal_scores: Sequence[float],
    usage: Sequence[float],
    random_seed: int,
    width: int = 4,
) -> Dict[str, List[int]]:
    num_cells = len(causal_scores)
    causal_top = _rank_cells(
        causal_scores,
        descending=True,
        width=width,
    )
    causal_bottom = _rank_cells(
        causal_scores,
        descending=False,
        width=width,
    )
    usage_top = _rank_cells(
        usage,
        descending=True,
        width=width,
    )
    random_cells = _random_cells(
        num_cells=num_cells,
        exclude=causal_top,
        width=width,
        seed=random_seed,
    )

    return {
        "freeze_all_private": list(range(num_cells)),
        "freeze_causal_top4": causal_top,
        "freeze_usage_top4": usage_top,
        "freeze_random4": random_cells,
        "freeze_causal_bottom4": causal_bottom,
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
    lesion_eval_examples: int,
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

        triggered = bool(
            float(baseline["mean_old_damage"]) > 0.0
        )
        event: Dict[str, object] = {
            "after_family": family_id,
            "next_family": next_family,
            "anchor_families": anchors,
            "before_old_loss": before_old,
            "pre_new_loss": pre_new,
            "baseline": baseline,
            "triggered": triggered,
            "causal_scores": None,
            "old_usage_fraction": None,
            "cell_sets": None,
            "causal_usage_top4_overlap": None,
            "interventions": [],
        }

        if triggered:
            usage = _usage_on_families(
                model,
                world,
                anchors,
                eval_examples=lesion_eval_examples,
                thought_steps=thought_steps,
            )
            scores = causal_cell_scores(
                model,
                world,
                anchors,
                eval_examples=lesion_eval_examples,
                thought_steps=thought_steps,
            )
            cell_sets = _build_cell_sets(
                causal_scores=scores,
                usage=usage,
                random_seed=(
                    1_000_003 * world_seed
                    + 9_973 * model_seed
                    + family_id
                ),
                width=4,
            )

            causal_top = set(cell_sets["freeze_causal_top4"])
            usage_top = set(cell_sets["freeze_usage_top4"])

            rows = []
            for intervention in INTERVENTIONS:
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

            event.update(
                {
                    "causal_scores": scores,
                    "old_usage_fraction": usage,
                    "cell_sets": cell_sets,
                    "causal_usage_top4_overlap":
                        len(causal_top & usage_top),
                    "interventions": rows,
                }
            )

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

        by_name: Dict[str, Dict[str, List[float]]] = {
            name: {"protection": [], "cost": []}
            for name in INTERVENTIONS
        }
        overlaps = []

        for event in triggered:
            overlaps.append(
                int(event["causal_usage_top4_overlap"])
            )
            for row in event["interventions"]:
                name = str(row["intervention"])
                by_name[name]["protection"].append(
                    float(row["protection_vs_baseline"])
                )
                by_name[name]["cost"].append(
                    float(row["learning_cost_vs_baseline"])
                )

        aggregate = {}
        for name, values in by_name.items():
            p = values["protection"]
            c = values["cost"]
            aggregate[name] = {
                "observations": len(p),
                "mean_protection": mean(p) if p else None,
                "median_protection": median(p) if p else None,
                "positive_protection_count":
                    sum(value > 0 for value in p),
                "mean_learning_cost": mean(c) if c else None,
            }

        causal = by_name["freeze_causal_top4"]
        usage = by_name["freeze_usage_top4"]
        random = by_name["freeze_random4"]
        bottom = by_name["freeze_causal_bottom4"]
        all_private = by_name["freeze_all_private"]

        def paired_mean(
            left: List[float],
            right: List[float],
        ) -> float | None:
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
            "mean_causal_usage_top4_overlap":
                mean(overlaps) if overlaps else None,
            "aggregate": aggregate,
            "mean_causal_protection_minus_random":
                paired_mean(
                    causal["protection"],
                    random["protection"],
                ),
            "mean_causal_protection_minus_usage":
                paired_mean(
                    causal["protection"],
                    usage["protection"],
                ),
            "mean_causal_protection_minus_bottom":
                paired_mean(
                    causal["protection"],
                    bottom["protection"],
                ),
            "mean_causal_learning_cost_minus_all_private":
                paired_mean(
                    causal["cost"],
                    all_private["cost"],
                ),
            "causal_beats_random_count": sum(
                a > b
                for a, b in zip(
                    causal["protection"],
                    random["protection"],
                )
            ),
            "causal_beats_usage_count": sum(
                a > b
                for a, b in zip(
                    causal["protection"],
                    usage["protection"],
                )
            ),
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
    parser.add_argument("--seeds", default="1501,1502,1503")
    parser.add_argument("--model-seed-base", type=int, default=16000)
    parser.add_argument(
        "--checkpoints-after",
        default="15,31,47,55",
    )
    parser.add_argument("--train-examples", type=int, default=20)
    parser.add_argument("--eval-examples", type=int, default=16)
    parser.add_argument("--lesion-eval-examples", type=int, default=8)
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
                    lesion_eval_examples=args.lesion_eval_examples,
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
