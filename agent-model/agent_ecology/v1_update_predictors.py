from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from statistics import mean
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
from .v1_update_reversion import (
    _evaluate_family_stream,
    _evaluate_reversion,
    _private_snapshot,
    _random_cells,
    _rank,
    _train_post_model,
)


PREDICTORS = (
    "grad_norm",
    "usage_grad",
    "output_sensitivity",
    "old_loss_sensitivity",
    "gradient_conflict",
)


def _capture_private_grads(
    model: SparseRecurrentEcology,
) -> Dict[str, torch.Tensor]:
    result = {}
    for name, parameter in model.named_parameters():
        if name not in _PRIVATE_CELL_NAMES:
            continue
        if parameter.grad is None:
            result[name] = torch.zeros_like(parameter)
        else:
            result[name] = parameter.grad.detach().clone()
    return result


def _mean_objective_grads(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    families: Sequence[int],
    *,
    stream: int,
    examples: int,
    thought_steps: int,
    objective: str,
) -> Dict[str, torch.Tensor]:
    was_training = model.training
    model.eval()
    model.zero_grad(set_to_none=True)

    objectives = []
    for family in families:
        events, targets = world.batch(
            family,
            examples,
            stream=stream,
        )
        outputs, _, _ = model(
            events,
            force_steps=thought_steps,
            add_training_noise=False,
            return_trace=False,
        )
        if objective == "loss":
            objectives.append(F.smooth_l1_loss(outputs, targets))
        elif objective == "output_energy":
            objectives.append(outputs.square().mean())
        else:
            raise ValueError(objective)

    torch.stack(objectives).mean().backward()
    grads = _capture_private_grads(model)
    model.zero_grad(set_to_none=True)
    model.train(was_training)
    return grads


def _usage_on_stream(
    model: SparseRecurrentEcology,
    world: BlockedFamilyWorld,
    families: Sequence[int],
    *,
    stream: int,
    examples: int,
    thought_steps: int,
) -> List[float]:
    usage = torch.zeros(
        model.config.num_cells,
        dtype=torch.float64,
    )
    was_training = model.training
    model.eval()

    with torch.no_grad():
        for family in families:
            events, _targets = world.batch(
                family,
                examples,
                stream=stream,
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


def _cell_scores_from_grads(
    *,
    old_loss: Mapping[str, torch.Tensor],
    old_output: Mapping[str, torch.Tensor],
    new_grad: Mapping[str, torch.Tensor],
    usage: Sequence[float],
) -> Dict[str, List[float]]:
    num_cells = len(usage)
    result = {
        predictor: [0.0] * num_cells
        for predictor in PREDICTORS
    }

    for cell in range(num_cells):
        norm_sq = 0.0
        usage_risk = 0.0
        output_sensitivity = 0.0
        old_loss_sensitivity = 0.0
        dot = 0.0

        for name in _PRIVATE_CELL_NAMES:
            gn = new_grad[name][cell].double().reshape(-1)
            go = old_loss[name][cell].double().reshape(-1)
            gm = old_output[name][cell].double().reshape(-1)

            norm_sq += float(gn.square().sum())
            output_sensitivity += float(
                (gm.abs() * gn.abs()).sum()
            )
            old_loss_sensitivity += float(
                (go.abs() * gn.abs()).sum()
            )
            dot += float((go * gn).sum())

        grad_norm = math.sqrt(norm_sq)
        usage_risk = float(usage[cell]) * grad_norm

        result["grad_norm"][cell] = grad_norm
        result["usage_grad"][cell] = usage_risk
        result["output_sensitivity"][cell] = output_sensitivity
        result["old_loss_sensitivity"][cell] = old_loss_sensitivity
        result["gradient_conflict"][cell] = max(0.0, -dot)

    return result


def _average_ranks(values: Sequence[float]) -> List[float]:
    indexed = sorted(
        enumerate(float(v) for v in values),
        key=lambda item: item[1],
    )
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        end = index + 1
        value = indexed[index][1]
        while end < len(indexed) and indexed[end][1] == value:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        for pos in range(index, end):
            ranks[indexed[pos][0]] = average_rank
        index = end
    return ranks


def _pearson(
    left: Sequence[float],
    right: Sequence[float],
) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    ml = mean(left)
    mr = mean(right)
    dl = [value - ml for value in left]
    dr = [value - mr for value in right]
    denom = math.sqrt(
        sum(value * value for value in dl)
        * sum(value * value for value in dr)
    )
    if denom <= 1e-15:
        return None
    return float(
        sum(a * b for a, b in zip(dl, dr)) / denom
    )


def _spearman(
    left: Sequence[float],
    right: Sequence[float],
) -> float | None:
    return _pearson(
        _average_ranks(left),
        _average_ranks(right),
    )


def _ground_truth_damage(
    post_model: SparseRecurrentEcology,
    *,
    pre_snapshot: Mapping[str, torch.Tensor],
    post_snapshot: Mapping[str, torch.Tensor],
    world: BlockedFamilyWorld,
    anchors: Sequence[int],
    examples: int,
    thought_steps: int,
) -> List[float]:
    post = {
        family: _evaluate_family_stream(
            post_model,
            world,
            family,
            stream=4,
            eval_examples=examples,
            thought_steps=thought_steps,
        )
        for family in anchors
    }

    scores = []
    for cell in range(post_model.config.num_cells):
        reverted = _evaluate_reversion(
            post_model,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            cells=[cell],
            world=world,
            families=anchors,
            stream=4,
            eval_examples=examples,
            thought_steps=thought_steps,
        )
        scores.append(
            mean(
                post[family] - reverted[family]
                for family in anchors
            )
        )
    return scores


def _evaluate_selected_reversion(
    post_model: SparseRecurrentEcology,
    *,
    pre_snapshot: Mapping[str, torch.Tensor],
    post_snapshot: Mapping[str, torch.Tensor],
    cells: Sequence[int],
    world: BlockedFamilyWorld,
    anchors: Sequence[int],
    next_family: int,
    before_old: Mapping[int, float],
    post_new: float,
    examples: int,
    thought_steps: int,
    baseline_damage: float,
) -> Dict[str, float | List[int]]:
    reverted_old = _evaluate_reversion(
        post_model,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        cells=cells,
        world=world,
        families=anchors,
        stream=1,
        eval_examples=examples,
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
        eval_examples=examples,
        thought_steps=thought_steps,
    )[next_family]

    reverted_damage = mean(
        reverted_old[family] - before_old[family]
        for family in anchors
    )
    return {
        "cells": list(cells),
        "protection": baseline_damage - reverted_damage,
        "learning_cost": reverted_new - post_new,
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
    predictor_examples: int,
    ground_truth_examples: int,
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
    model = SparseRecurrentEcology(
        EcologyConfig(
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
    )
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

        old_loss_grad = _mean_objective_grads(
            model,
            world,
            anchors,
            stream=2,
            examples=predictor_examples,
            thought_steps=thought_steps,
            objective="loss",
        )
        old_output_grad = _mean_objective_grads(
            model,
            world,
            anchors,
            stream=2,
            examples=predictor_examples,
            thought_steps=thought_steps,
            objective="output_energy",
        )
        usage = _usage_on_stream(
            model,
            world,
            anchors,
            stream=2,
            examples=predictor_examples,
            thought_steps=thought_steps,
        )
        new_grad = _mean_objective_grads(
            model,
            world,
            [next_family],
            stream=3,
            examples=predictor_examples,
            thought_steps=thought_steps,
            objective="loss",
        )
        predictor_scores = _cell_scores_from_grads(
            old_loss=old_loss_grad,
            old_output=old_output_grad,
            new_grad=new_grad,
            usage=usage,
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

        event: Dict[str, object] = {
            "after_family": family_id,
            "next_family": next_family,
            "baseline_mean_old_damage": baseline_damage,
            "baseline_new_learning_gain": pre_new - post_new,
            "triggered": baseline_damage > 0.0,
            "predictors": {},
        }

        if baseline_damage > 0.0:
            truth = _ground_truth_damage(
                post_model,
                pre_snapshot=pre_snapshot,
                post_snapshot=post_snapshot,
                world=world,
                anchors=anchors,
                examples=ground_truth_examples,
                thought_steps=thought_steps,
            )
            truth_top = _rank(truth, min(4, num_cells), True)
            random4 = _random_cells(
                num_cells,
                min(4, num_cells),
                seed=(
                    1_000_003 * world_seed
                    + 9_973 * model_seed
                    + 173 * family_id
                ),
            )

            random_result = _evaluate_selected_reversion(
                post_model,
                pre_snapshot=pre_snapshot,
                post_snapshot=post_snapshot,
                cells=random4,
                world=world,
                anchors=anchors,
                next_family=next_family,
                before_old=before_old,
                post_new=post_new,
                examples=eval_examples,
                thought_steps=thought_steps,
                baseline_damage=baseline_damage,
            )
            truth_result = _evaluate_selected_reversion(
                post_model,
                pre_snapshot=pre_snapshot,
                post_snapshot=post_snapshot,
                cells=truth_top,
                world=world,
                anchors=anchors,
                next_family=next_family,
                before_old=before_old,
                post_new=post_new,
                examples=eval_examples,
                thought_steps=thought_steps,
                baseline_damage=baseline_damage,
            )

            predictor_rows = {}
            for predictor, scores in predictor_scores.items():
                selected = _rank(
                    scores,
                    min(4, num_cells),
                    True,
                )
                branch = _evaluate_selected_reversion(
                    post_model,
                    pre_snapshot=pre_snapshot,
                    post_snapshot=post_snapshot,
                    cells=selected,
                    world=world,
                    anchors=anchors,
                    next_family=next_family,
                    before_old=before_old,
                    post_new=post_new,
                    examples=eval_examples,
                    thought_steps=thought_steps,
                    baseline_damage=baseline_damage,
                )
                predictor_rows[predictor] = {
                    "scores": scores,
                    "spearman_with_damage": _spearman(scores, truth),
                    "top4_overlap_with_damage":
                        len(set(selected) & set(truth_top)),
                    **branch,
                }

            event.update(
                {
                    "ground_truth_damage": truth,
                    "ground_truth_top4": {
                        **truth_result,
                        "cells": truth_top,
                    },
                    "random4": random_result,
                    "predictors": predictor_rows,
                }
            )

        events.append(event)

    return {
        "control": control,
        "world_seed": world_seed,
        "model_seed": model_seed,
        "events": events,
    }


def summarize(runs: Iterable[Dict[str, object]]) -> Dict[str, object]:
    output = {}

    for control in CONTROLS:
        events = [
            event
            for run in runs
            if run["control"] == control
            for event in run["events"]
            if event["triggered"]
        ]

        predictors = {}
        for predictor in PREDICTORS:
            rows = [
                event["predictors"][predictor]
                for event in events
            ]
            random = [
                float(event["random4"]["protection"])
                for event in events
            ]
            protection = [
                float(row["protection"])
                for row in rows
            ]
            correlations = [
                float(row["spearman_with_damage"])
                for row in rows
                if row["spearman_with_damage"] is not None
            ]

            predictors[predictor] = {
                "observations": len(rows),
                "mean_spearman_with_damage":
                    mean(correlations) if correlations else None,
                "mean_top4_overlap_with_damage":
                    mean(
                        int(row["top4_overlap_with_damage"])
                        for row in rows
                    ) if rows else None,
                "mean_protection":
                    mean(protection) if protection else None,
                "mean_random4_protection":
                    mean(random) if random else None,
                "mean_protection_minus_random":
                    (
                        mean(a - b for a, b in zip(protection, random))
                        if rows else None
                    ),
                "beats_random_count":
                    sum(a > b for a, b in zip(protection, random)),
                "mean_learning_cost":
                    mean(
                        float(row["learning_cost"])
                        for row in rows
                    ) if rows else None,
            }

        truth = [
            float(event["ground_truth_top4"]["protection"])
            for event in events
        ]
        output[control] = {
            "triggered_events": len(events),
            "mean_ground_truth_top4_protection":
                mean(truth) if truth else None,
            "predictors": predictors,
        }

    return {"by_control": output}


def _parse_ints(value: str) -> List[int]:
    result = [
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    ]
    if not result:
        raise ValueError("empty integer list")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-count", type=int, default=64)
    parser.add_argument("--seeds", default="1701,1702,1703,1704,1705,1706")
    parser.add_argument("--model-seed-base", type=int, default=18000)
    parser.add_argument("--checkpoints-after", default="15,31,47,55")
    parser.add_argument("--train-examples", type=int, default=20)
    parser.add_argument("--eval-examples", type=int, default=16)
    parser.add_argument("--predictor-examples", type=int, default=8)
    parser.add_argument("--ground-truth-examples", type=int, default=8)
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
                    predictor_examples=args.predictor_examples,
                    ground_truth_examples=args.ground_truth_examples,
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
