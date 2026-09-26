from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import Dict, Tuple

import torch
import torch.nn.functional as F

from .lifetime_world import LifetimeWorld, LifetimeWorldConfig
from .model import EcologyConfig, SparseRecurrentEcology


def control_shape(name: str) -> Tuple[int, int]:
    if name == "fixed16":
        return 16, 4
    if name == "sparse64":
        return 64, 4
    if name == "dense64":
        return 64, 64
    raise ValueError(f"unknown control: {name}")


def run_control(args: argparse.Namespace) -> Dict[str, object]:
    torch.manual_seed(args.model_seed)
    device = torch.device(args.device)

    world_config = LifetimeWorldConfig(
        total_experiences=args.world_size,
        sequence_length=args.sequence_length,
        seed=args.world_seed,
    )
    world = LifetimeWorld(world_config)

    num_cells, active_cells = control_shape(args.control)
    config = EcologyConfig(
        event_dim=world_config.event_dim,
        output_dim=1,
        num_cells=num_cells,
        active_cells=active_cells,
        state_dim=args.state_dim,
        workspace_slots=args.workspace_slots,
        signature_dim=args.signature_dim,
        message_dim=args.message_dim,
        max_thought_steps=args.thought_steps,
        min_thought_steps=args.thought_steps,
        routing_noise_std=args.routing_noise_std,
        dense_training_compute=True,
    )

    model = SparseRecurrentEcology(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    state = model.initial_state(1, device=device)
    usage = torch.zeros(num_cells, dtype=torch.long)
    regime_loss_sum = defaultdict(float)
    regime_count = defaultdict(int)
    loss_history = []
    total_task_loss = 0.0
    total_train_ms = 0.0

    stop = min(
        world_config.total_experiences,
        args.start + args.experiences,
    )

    model.train()
    for experience in world.iter_from(args.start, stop):
        events = experience.events.unsqueeze(0).to(device)
        targets = experience.targets.unsqueeze(0).to(device)

        start_ns = time.perf_counter_ns()
        outputs, new_state, traces = model(
            events,
            state,
            force_steps=args.thought_steps,
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
            balance_loss = model.router_balance_loss(router_scores)
        else:
            balance_loss = task_loss.new_zeros(())

        loss = task_loss + args.balance_weight * balance_loss

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1e6
        total_train_ms += elapsed_ms

        # Preserve the agent's persistent numerical state across experiences
        # while cutting the autograd graph at the experience boundary.
        state = new_state.detach()

        selected = torch.cat(
            [
                trace["selected_cells"].reshape(-1)
                for trace in traces
            ],
            dim=0,
        ).detach().cpu()
        usage += torch.bincount(
            selected,
            minlength=num_cells,
        )

        task_value = float(task_loss.detach().cpu())
        total_task_loss += task_value
        regime_loss_sum[experience.hidden_regime] += task_value
        regime_count[experience.hidden_regime] += 1

        completed = experience.index - args.start + 1
        if (
            completed == 1
            or completed % args.log_every == 0
            or experience.index + 1 == stop
        ):
            loss_history.append(
                {
                    "experience": experience.index,
                    "hidden_regime": experience.hidden_regime,
                    "task_loss": task_value,
                    "balance_loss": float(
                        balance_loss.detach().cpu()
                    ),
                }
            )

    count = max(1, stop - args.start)
    usage_total = int(usage.sum())
    usage_fraction = (
        usage.float() / max(1, usage_total)
    ).tolist()

    per_regime = {
        name: {
            "count": regime_count[name],
            "mean_task_loss":
                regime_loss_sum[name] / regime_count[name],
        }
        for name in sorted(regime_count)
    }

    summary: Dict[str, object] = {
        "control": args.control,
        "world_seed": args.world_seed,
        "model_seed": args.model_seed,
        "start": args.start,
        "stop": stop,
        "experiences": stop - args.start,
        "model_config": asdict(config),
        "parameter_count": model.parameter_count(),
        "mean_task_loss": total_task_loss / count,
        "per_regime": per_regime,
        "cell_usage_fraction": usage_fraction,
        "training_wall_ms_total": total_train_ms,
        "training_wall_ms_per_experience":
            total_train_ms / count,
        "loss_history": loss_history,
    }

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run fixed Agent v1-A1 lifetime controls."
    )
    p.add_argument(
        "--control",
        choices=("fixed16", "sparse64", "dense64"),
        required=True,
    )
    p.add_argument("--world-size", type=int, default=100_000)
    p.add_argument("--experiences", type=int, default=2_000)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--sequence-length", type=int, default=6)
    p.add_argument("--world-seed", type=int, default=20260926)
    p.add_argument("--model-seed", type=int, default=7)
    p.add_argument("--state-dim", type=int, default=96)
    p.add_argument("--workspace-slots", type=int, default=4)
    p.add_argument("--signature-dim", type=int, default=32)
    p.add_argument("--message-dim", type=int, default=32)
    p.add_argument("--thought-steps", type=int, default=3)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--balance-weight", type=float, default=0.01)
    p.add_argument("--routing-noise-std", type=float, default=0.10)
    p.add_argument("--log-every", type=int, default=100)
    p.add_argument("--device", default="cpu")
    p.add_argument("--output", type=Path)
    return p


def main() -> None:
    args = parser().parse_args()
    summary = run_control(args)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
