from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import torch
import torch.nn.functional as F

from .curriculum import (
    held_out_bigrams,
    sample_forced_bigram_batch,
    sample_program_batch,
)
from .model import EcologyConfig, SparseRecurrentEcology


def train(args: argparse.Namespace) -> None:
    torch.manual_seed(args.seed)
    device = torch.device(args.device)

    config = EcologyConfig(
        event_dim=11,
        output_dim=1,
        num_cells=args.num_cells,
        active_cells=args.active_cells,
        state_dim=args.state_dim,
        workspace_slots=args.workspace_slots,
        signature_dim=args.signature_dim,
        message_dim=args.message_dim,
        max_thought_steps=args.thought_steps,
        min_thought_steps=min(2, args.thought_steps),
    )
    model = SparseRecurrentEcology(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    history = []
    forbidden = held_out_bigrams()

    model.train()
    for step in range(1, args.steps + 1):
        length = int(
            torch.randint(
                low=args.min_sequence,
                high=args.max_sequence + 1,
                size=(1,),
            ).item()
        )
        events, targets, _ = sample_program_batch(
            args.batch_size,
            length,
            device=device,
            forbidden_bigrams=forbidden,
        )

        outputs, _, traces = model(
            events,
            force_steps=args.thought_steps,
            add_training_noise=True,
            return_trace=True,
        )

        task_loss = F.smooth_l1_loss(outputs, targets)

        router_scores = torch.cat(
            [
                trace["router_scores"].reshape(
                    -1, config.num_cells
                )
                for trace in traces
            ],
            dim=0,
        )
        balance_loss = model.router_balance_loss(router_scores)

        loss = task_loss + args.balance_weight * balance_loss

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        if step == 1 or step % args.log_every == 0 or step == args.steps:
            record = {
                "step": step,
                "loss": float(loss.detach().cpu()),
                "task_loss": float(task_loss.detach().cpu()),
                "balance_loss": float(balance_loss.detach().cpu()),
            }
            history.append(record)
            print(json.dumps(record), flush=True)

    model.eval()
    with torch.no_grad():
        seen_events, seen_targets, _ = sample_program_batch(
            args.eval_batch_size,
            args.max_sequence,
            device=device,
            forbidden_bigrams=forbidden,
        )
        seen_outputs, _, seen_traces = model(
            seen_events,
            force_steps=args.thought_steps,
            add_training_noise=False,
            return_trace=True,
        )
        seen_mae = F.l1_loss(seen_outputs, seen_targets)

        # Every evaluation program contains a composition explicitly withheld
        # from the training generator.
        recombined_events, recombined_targets, _ = sample_forced_bigram_batch(
            args.eval_batch_size,
            max(3, args.max_sequence),
            bigrams=forbidden,
            device=device,
        )
        recombined_outputs, _, recombined_traces = model(
            recombined_events,
            force_steps=args.thought_steps,
            add_training_noise=False,
            return_trace=True,
        )
        recombined_mae = F.l1_loss(
            recombined_outputs, recombined_targets
        )

        selected = torch.cat(
            [
                trace["selected_cells"].reshape(
                    -1, config.active_cells
                )
                for trace in seen_traces
            ],
            dim=0,
        )
        usage = torch.bincount(
            selected.reshape(-1),
            minlength=config.num_cells,
        ).float()
        usage /= usage.sum().clamp_min(1.0)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / "agent-ecology-v0.pt"
    torch.save(
        {
            "config": asdict(config),
            "state_dict": model.state_dict(),
            "training_args": vars(args),
        },
        checkpoint,
    )

    metrics = {
        "parameter_count": model.parameter_count(),
        "seen_mae": float(seen_mae.cpu()),
        "recombined_mae": float(recombined_mae.cpu()),
        "cell_usage": usage.cpu().tolist(),
        "history": history,
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2)
    )

    print(json.dumps(metrics, indent=2), flush=True)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=1500)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--eval-batch-size", type=int, default=256)
    p.add_argument("--min-sequence", type=int, default=2)
    p.add_argument("--max-sequence", type=int, default=6)
    p.add_argument("--num-cells", type=int, default=32)
    p.add_argument("--active-cells", type=int, default=4)
    p.add_argument("--state-dim", type=int, default=192)
    p.add_argument("--workspace-slots", type=int, default=6)
    p.add_argument("--signature-dim", type=int, default=64)
    p.add_argument("--message-dim", type=int, default=64)
    p.add_argument("--thought-steps", type=int, default=4)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--balance-weight", type=float, default=0.01)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--device", default="cpu")
    p.add_argument("--log-every", type=int, default=50)
    p.add_argument("--output-dir", default="artifacts")
    return p


if __name__ == "__main__":
    train(parser().parse_args())
