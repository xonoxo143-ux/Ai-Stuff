from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from statistics import mean, median
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import torch
import torch.nn.functional as F

from .capacity_world import CapacityWorldConfig
from .interference_world import BlockedFamilyWorld
from .model import EcologyConfig, SparseRecurrentEcology
from .v1_selective_isolation import (
    CONTROLS,
    _PRIVATE_CELL_NAMES,
    _anchor_families,
    _copy_state,
    _shape,
    _train_family,
)


def _evaluate_family_stream(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    family_id: int,
    *,
    stream: int,
    eval_examples: int,
    thought_steps: int,
) -> float:
    events, targets = world.batch(
        family_id,
        eval_examples,
        stream=stream,
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


def _private_snapshot(
    model: SparseRecurrentEcology,
) -> Dict[str, torch.Tensor]:
    named = dict(model.named_parameters())
    return {
        name: named[name].detach().clone()
        for name in _PRIVATE_CELL_NAMES
    }


def _set_private_rows(
    model: SparseRecurrentEcology,
    cells: Sequence[int],
    snapshot: Mapping[str, torch.Tensor],
) -> None:
    if not cells:
        return
    index = torch.tensor(list(cells), dtype=torch.long)
    named = dict(model.named_parameters())
    with torch.no_grad():
        for name in _PRIVATE_CELL_NAMES:
            named[name].index_copy_(
                0,
                index,
                snapshot[name].index_select(0, index),
            )


def _evaluate_reversion(
    model: SparseRecurrentEcology,
    *,
    pre_snapshot: Mapping[str, torch.Tensor],
    post_snapshot: Mapping[str, torch.Tensor],
    cells: Sequence[int],
    world: BlockedFamilyWorld,
    families: Sequence[int],
    stream: int,
    eval_examples: int,
    thought_steps: int,
) -> Dict[int, float]:
    _set_private_rows(model, cells, pre_snapshot)
    try:
        return {
            family: _evaluate_family_stream(
                model,
                world,
                family,
                stream=stream,
                eval_examples=eval_examples,
                thought_steps=thought_steps,
            )
            for family in families
        }
    finally:
        _set_private_rows(model, cells, post_snapshot)


def _train_post_model(
    model: SparseRecurrentEcology,
    optimizer: torch.optim.Optimizer,
    state,
    world: BlockedFamilyWorld,
    next_family: int,
    *,
    train_examples: int,
    thought_steps: int,
    learning_rate: float,
    balance_weight: float,
):
    post_model = copy.deepcopy(model)
    post_state = _copy_state(state)
    post_optimizer = torch.optim.AdamW(
        post_model.parameters(),
        lr=learning_rate,
        weight_decay=1e-4,
    )
    post_optimizer.load_state_dict(
        copy.deepcopy(optimizer.state_dict())
    )
    post_state = _train_family(
        post_model,
        post_optimizer,
        post_state,
        world,
        next_family,
        train_examples=train_examples,
        thought_steps=thought_steps,
        balance_weight=balance_weight,
    )
    return post_model, post_state, post_optimizer


def _random_cells(
    num_cells: int,
    width: int,
    seed: int,
) -> List[int]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    return torch.randperm(
        num_cells,
        generator=generator,
    )[:width].tolist()


def _rank(
    scores: Sequence[float],
    width: int,
    descending: bool,
) -> List[int]:
    values = torch.tensor(scores, dtype=torch.float64)
    return torch.argsort(
        values,
        descending=descending,
        stable=True,
    )[:width].tolist()


def run_one(
    *,
    control: str,
    family_count: int,
    world_seed: int,
    model_seed: int,
    checkpoints_after: Sequence[int],
    widths: Sequence[int],
    train_examples: int,
    eval_examples: int,
    diagnostic_examples: int,
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
            family: _evaluate_family_stream(
                model,
                world,
                family,
                stream=1,
                eval_examples=eval_examples,
                thought_steps=thought_steps,
            )
            for family in anchors
        }
        pre_new = _evaluate_family_stream(
            model,
            world,
            next_family,
            stream=1,
            eval_examples=eval_examples,
            thought_steps=thought_steps,
        )

        pre_snapshot = _private_snapshot(model)
        post_model, _post_state, _post_optimizer = _train_post_model(
            model,
            optimizer,
            state,
            world,
            next_family,
            train_examples=train_examples,
            thought_steps=thought_steps,
            learning_rate=learning_rate,
            balance_weight=balance_weight,
        )
        post_snapshot = _private_snapshot(post_model)

        post_old = {
            family: _evaluate_family_stream(
                post_model,
                world,
                family,
                stream=1,
                eval_examples=eval_examples,
                thought_steps=thought_steps,
            )
            for family in anchors
        }
        post_new = _evaluate_family_stream(
            post_model,
            world,
            next_family,
            stream=1,
            eval_examples=eval_examples,
            thought_steps=thought_steps,
        )

        baseline_damage = mean(
            post_old[family] - before_old[family]
            for family in anchors
        )
        baseline_learning_gain = pre_new - post_new
        triggered = baseline_damage > 0.0

        event: Dict[str, object] = {
            "after_family": family_id,
            "next_family": next_family,
            "anchor_families": anchors,
            "baseline_mean_old_damage": baseline_damage,
            "baseline_new_learning_gain": baseline_learning_gain,
            "triggered": triggered,
            "update_damage_scores": None,
            "positive_score_mass": None,
            "widths": [],
        }

        if triggered:
            diagnostic_post = {
                family: _evaluate_family_stream(
                    post_model,
                    world,
                    family,
                    stream=2,
                    eval_examples=diagnostic_examples,
                    thought_steps=thought_steps,
                )
                for family in anchors
            }

            scores = []
            for cell in range(num_cells):
                reverted = _evaluate_reversion(
                    post_model,
                    pre_snapshot=pre_snapshot,
                    post_snapshot=post_snapshot,
                    cells=[cell],
                    world=world,
                    families=anchors,
                    stream=2,
                    eval_examples=diagnostic_examples,
                    thought_steps=thought_steps,
                )
                scores.append(
                    mean(
                        diagnostic_post[family] - reverted[family]
                        for family in anchors
                    )
                )

            positive_mass = sum(max(score, 0.0) for score in scores)
            width_rows = []

            for requested_width in widths:
                width = min(int(requested_width), num_cells)
                if width <= 0:
                    continue

                top = _rank(scores, width, True)
                bottom = _rank(scores, width, False)
                random_cells = _random_cells(
                    num_cells,
                    width,
                    seed=(
                        1_000_003 * world_seed
                        + 9_973 * model_seed
                        + 131 * family_id
                        + width
                    ),
                )

                sets = {
                    "top": top,
                    "random": random_cells,
                    "bottom": bottom,
                }
                branches = {}

                for name, cells in sets.items():
                    reverted_old = _evaluate_reversion(
                        post_model,
                        pre_snapshot=pre_snapshot,
                        post_snapshot=post_snapshot,
                        cells=cells,
                        world=world,
                        families=anchors,
                        stream=1,
                        eval_examples=eval_examples,
                        thought_steps=thought_steps,
                    )
                    reverted_new = _evaluate_reversion(
                        post_model,
                        pre_snapshot=pre_snapshot,
                        post_snapshot=post_snapshot,
                        cells=cells,
                        world=world,
                        families=[next_family],
                        stream=1,
                        eval_examples=eval_examples,
                        thought_steps=thought_steps,
                    )[next_family]

                    reverted_damage = mean(
                        reverted_old[family] - before_old[family]
                        for family in anchors
                    )

                    branches[name] = {
                        "cells": cells,
                        "protection":
                            baseline_damage - reverted_damage,
                        "learning_cost":
                            reverted_new - post_new,
                    }

                top_positive = sum(
                    max(scores[cell], 0.0)
                    for cell in top
                )

                width_rows.append(
                    {
                        "width": width,
                        "top_positive_score_share":
                            (
                                top_positive / positive_mass
                                if positive_mass > 0.0
                                else None
                            ),
                        "top_random_overlap":
                            len(set(top) & set(random_cells)),
                        "branches": branches,
                    }
                )

            event.update(
                {
                    "update_damage_scores": scores,
                    "positive_score_mass": positive_mass,
                    "widths": width_rows,
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
    output: Dict[str, object] = {}

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

        widths = sorted(
            {
                int(row["width"])
                for event in triggered
                for row in event["widths"]
            }
        )
        by_width = {}

        for width in widths:
            rows = [
                row
                for event in triggered
                for row in event["widths"]
                if int(row["width"]) == width
            ]

            top_p = [
                float(row["branches"]["top"]["protection"])
                for row in rows
            ]
            random_p = [
                float(row["branches"]["random"]["protection"])
                for row in rows
            ]
            bottom_p = [
                float(row["branches"]["bottom"]["protection"])
                for row in rows
            ]
            top_cost = [
                float(row["branches"]["top"]["learning_cost"])
                for row in rows
            ]
            shares = [
                float(row["top_positive_score_share"])
                for row in rows
                if row["top_positive_score_share"] is not None
            ]

            by_width[str(width)] = {
                "observations": len(rows),
                "mean_top_protection":
                    mean(top_p) if top_p else None,
                "median_top_protection":
                    median(top_p) if top_p else None,
                "mean_random_protection":
                    mean(random_p) if random_p else None,
                "mean_bottom_protection":
                    mean(bottom_p) if bottom_p else None,
                "mean_top_minus_random_protection":
                    (
                        mean(a - b for a, b in zip(top_p, random_p))
                        if top_p
                        else None
                    ),
                "top_beats_random_count":
                    sum(a > b for a, b in zip(top_p, random_p)),
                "mean_top_learning_cost":
                    mean(top_cost) if top_cost else None,
                "mean_top_positive_score_share":
                    mean(shares) if shares else None,
            }

        output[control] = {
            "runs": len(control_runs),
            "screened_events": sum(
                len(run["events"])
                for run in control_runs
            ),
            "triggered_events": len(triggered),
            "by_width": by_width,
        }

    return {"by_control": output}


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
    parser.add_argument(
        "--widths",
        default="1,2,4,8,16,32",
    )
    parser.add_argument("--train-examples", type=int, default=20)
    parser.add_argument("--eval-examples", type=int, default=16)
    parser.add_argument("--diagnostic-examples", type=int, default=8)
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
    widths = _parse_ints(args.widths)
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
                    widths=widths,
                    train_examples=args.train_examples,
                    eval_examples=args.eval_examples,
                    diagnostic_examples=args.diagnostic_examples,
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
        "widths": widths,
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
