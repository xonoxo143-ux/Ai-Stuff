from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Tuple

import torch
import torch.nn.functional as F

from .capacity_world import CapacityWorldConfig
from .interference_world import BlockedFamilyWorld
from .model import EcologyConfig, SparseRecurrentEcology


CONTROLS = ("fixed16", "sparse64")

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
        return "private_cell_compute"
    if root in {"cell_signatures", "need_projection"}:
        return "router"
    if root in {
        "initial_workspace",
        "signature_read_query",
        "message_key",
        "message_value",
    }:
        return "workspace"
    return "shared_io"


def _snapshot_parameters(
    model: SparseRecurrentEcology,
) -> Dict[str, torch.Tensor]:
    return {
        name: parameter.detach().cpu().clone()
        for name, parameter in model.named_parameters()
    }


def _block_update_diagnostics(
    model: SparseRecurrentEcology,
    before: Mapping[str, torch.Tensor],
) -> Tuple[List[float], Dict[str, float]]:
    num_cells = model.config.num_cells
    per_cell_sq = torch.zeros(num_cells, dtype=torch.float64)
    category_sq: Dict[str, float] = {
        "private_cell_compute": 0.0,
        "router": 0.0,
        "workspace": 0.0,
        "shared_io": 0.0,
    }

    for name, parameter in model.named_parameters():
        after = parameter.detach().cpu()
        delta = after - before[name]
        category = _parameter_category(name)
        category_sq[category] += float(delta.double().square().sum())

        if name in _PRIVATE_CELL_NAMES:
            flat = delta.double().reshape(num_cells, -1)
            per_cell_sq += flat.square().sum(dim=1)

    return (
        torch.sqrt(per_cell_sq).tolist(),
        {
            category: math.sqrt(value)
            for category, value in category_sq.items()
        },
    )


def _mass_overlap(left: List[float], right: List[float]) -> float:
    return float(sum(min(a, b) for a, b in zip(left, right)))


def _normalize_nonnegative(values: List[float]) -> List[float]:
    total = float(sum(values))
    if total <= 0.0:
        return [0.0 for _ in values]
    return [float(value / total) for value in values]


def _dot(left: List[float], right: List[float]) -> float:
    return float(sum(a * b for a, b in zip(left, right)))


def _pearson(xs: List[float], ys: List[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx = mean(xs)
    my = mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(
        sum(x * x for x in dx) * sum(y * y for y in dy)
    )
    if denom <= 1e-12:
        return None
    return float(sum(x * y for x, y in zip(dx, dy)) / denom)


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


def run_one(
    *,
    control: str,
    family_count: int,
    world_seed: int,
    model_seed: int,
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

    loss_matrix: List[List[float | None]] = [
        [None for _ in range(family_count)]
        for _ in range(family_count)
    ]
    prelearn_loss: List[float] = []
    usage_by_family: List[List[float]] = []
    update_norm_by_family: List[List[float]] = []
    category_update_norm_by_family: List[Dict[str, float]] = []

    model.train()
    for family_id in range(family_count):
        prelearn_loss.append(
            _evaluate_family(
                model,
                world,
                family_id,
                eval_examples=eval_examples,
                thought_steps=thought_steps,
            )
        )

        before = _snapshot_parameters(model)
        usage = torch.zeros(num_cells, dtype=torch.long)

        for sample_index in range(train_examples):
            sample = world.sample(
                family_id,
                sample_index,
                stream=0,
            )
            events = sample.events.unsqueeze(0)
            targets = sample.targets.unsqueeze(0)

            outputs, new_state, traces = model(
                events,
                state,
                force_steps=thought_steps,
                add_training_noise=True,
                return_trace=True,
            )
            task_loss = F.smooth_l1_loss(outputs, targets)

            router_scores = torch.cat(
                [
                    trace["router_scores"].reshape(-1, num_cells)
                    for trace in traces
                ],
                dim=0,
            )
            balance_loss = model.router_balance_loss(router_scores)
            loss = task_loss + balance_weight * balance_loss

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            state = new_state.detach()

            selected = torch.cat(
                [
                    trace["selected_cells"].reshape(-1)
                    for trace in traces
                ],
                dim=0,
            ).detach().cpu()
            usage += torch.bincount(selected, minlength=num_cells)

        usage_fraction = (
            usage.float() / usage.sum().clamp_min(1)
        ).tolist()
        usage_by_family.append(usage_fraction)

        per_cell_update, category_update = _block_update_diagnostics(
            model,
            before,
        )
        update_norm_by_family.append(per_cell_update)
        category_update_norm_by_family.append(category_update)

        for probe_family in range(family_id + 1):
            loss_matrix[family_id][probe_family] = _evaluate_family(
                model,
                world,
                probe_family,
                eval_examples=eval_examples,
                thought_steps=thought_steps,
            )

    per_family: List[Dict[str, object]] = []
    forgetting_values = []
    retention_values = []
    learning_gains = []
    collision_values = []
    exposure_values = []

    for family_id in range(family_count):
        postlearn = float(loss_matrix[family_id][family_id])
        later = [
            float(loss_matrix[checkpoint][family_id])
            for checkpoint in range(family_id, family_count)
        ]
        final = later[-1]
        best = min(later)
        forgetting = final - best
        retention_delta = final - postlearn
        learning_gain = prelearn_loss[family_id] - postlearn

        future_collisions = [
            _mass_overlap(
                usage_by_family[family_id],
                usage_by_family[later_family],
            )
            for later_family in range(family_id + 1, family_count)
        ]

        usage_anchor = usage_by_family[family_id]
        future_exposure = []
        for later_family in range(family_id + 1, family_count):
            normalized_update = _normalize_nonnegative(
                update_norm_by_family[later_family]
            )
            future_exposure.append(
                _dot(usage_anchor, normalized_update)
            )

        collision = (
            mean(future_collisions)
            if future_collisions
            else 0.0
        )
        exposure = (
            mean(future_exposure)
            if future_exposure
            else 0.0
        )

        per_family.append(
            {
                "family_id": family_id,
                "prelearn_loss": prelearn_loss[family_id],
                "postlearn_loss": postlearn,
                "best_after_learning_loss": best,
                "final_loss": final,
                "forgetting": forgetting,
                "retention_delta": retention_delta,
                "learning_gain": learning_gain,
                "future_usage_collision": collision,
                "future_private_update_exposure": exposure,
            }
        )

        if family_id < family_count - 1:
            forgetting_values.append(forgetting)
            retention_values.append(retention_delta)
            collision_values.append(collision)
            exposure_values.append(exposure)
        learning_gains.append(learning_gain)

    loss_bwt = -mean(retention_values) if retention_values else 0.0

    return {
        "control": control,
        "family_count": family_count,
        "world_seed": world_seed,
        "model_seed": model_seed,
        "model_config": asdict(model_config),
        "train_examples_per_family": train_examples,
        "eval_examples_per_family": eval_examples,
        "mean_average_forgetting":
            mean(forgetting_values) if forgetting_values else 0.0,
        "mean_retention_delta":
            mean(retention_values) if retention_values else 0.0,
        "loss_backward_transfer": loss_bwt,
        "mean_learning_gain": mean(learning_gains),
        "mean_final_loss": mean(
            float(loss_matrix[-1][family_id])
            for family_id in range(family_count)
        ),
        "forgetting_collision_pearson":
            _pearson(forgetting_values, collision_values),
        "forgetting_update_exposure_pearson":
            _pearson(forgetting_values, exposure_values),
        "loss_matrix": loss_matrix,
        "prelearn_loss": prelearn_loss,
        "usage_by_family": usage_by_family,
        "private_cell_update_norm_by_family": update_norm_by_family,
        "category_update_norm_by_family":
            category_update_norm_by_family,
        "per_family": per_family,
    }


def summarize(runs: Iterable[Dict[str, object]]) -> Dict[str, object]:
    grouped: Dict[int, Dict[int, Dict[str, Dict[str, object]]]] = {}
    for run in runs:
        families = int(run["family_count"])
        seed = int(run["world_seed"])
        grouped.setdefault(families, {}).setdefault(seed, {})[
            str(run["control"])
        ] = run

    result: Dict[str, object] = {}
    for families, seeds in sorted(grouped.items()):
        forgetting_delta = []
        bwt_delta = []
        final_delta = []
        learning_gain_delta = []

        for seed, controls in sorted(seeds.items()):
            if set(controls) != set(CONTROLS):
                raise ValueError(
                    f"incomplete controls for families={families}, seed={seed}"
                )
            fixed = controls["fixed16"]
            sparse = controls["sparse64"]

            forgetting_delta.append(
                float(sparse["mean_average_forgetting"])
                - float(fixed["mean_average_forgetting"])
            )
            bwt_delta.append(
                float(sparse["loss_backward_transfer"])
                - float(fixed["loss_backward_transfer"])
            )
            final_delta.append(
                float(sparse["mean_final_loss"])
                - float(fixed["mean_final_loss"])
            )
            learning_gain_delta.append(
                float(sparse["mean_learning_gain"])
                - float(fixed["mean_learning_gain"])
            )

        result[str(families)] = {
            "pairs": len(seeds),
            "mean_forgetting64_minus_16": mean(forgetting_delta),
            "sparse64_forgets_less_wins":
                sum(delta < 0 for delta in forgetting_delta),
            "mean_loss_bwt64_minus_16": mean(bwt_delta),
            "mean_final_loss64_minus_16": mean(final_delta),
            "sparse64_final_loss_wins":
                sum(delta < 0 for delta in final_delta),
            "mean_learning_gain64_minus_16":
                mean(learning_gain_delta),
            "paired_forgetting64_minus_16": forgetting_delta,
            "paired_final_loss64_minus_16": final_delta,
        }

    return {"by_family_count": result}


def _parse_ints(value: str) -> List[int]:
    parsed = [
        int(item.strip())
        for item in value.split(",")
        if item.strip()
    ]
    if not parsed:
        raise ValueError("empty integer list")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family-counts", default="16,32,64")
    parser.add_argument("--seeds", default="901,902,903")
    parser.add_argument("--model-seed-base", type=int, default=10000)
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
        "family_counts": family_counts,
        "seeds": seeds,
        "train_examples": args.train_examples,
        "eval_examples": args.eval_examples,
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
