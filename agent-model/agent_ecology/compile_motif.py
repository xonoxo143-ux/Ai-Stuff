from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import torch
from torch import Tensor, nn
import torch.nn.functional as F

from .curriculum import (
    held_out_bigrams,
    sample_forced_bigram_batch,
    sample_program_batch,
)
from .export_onnx import load_checkpoint
from .model import SparseRecurrentEcology


class PairComposite(nn.Module):
    """
    Distilled implementation for a recurring two-cell interaction motif.

    It predicts both source cells' state deltas plus their two weighted public
    messages from exactly the information available at the source-cell boundary.
    """

    def __init__(
        self,
        input_dim: int,
        target_dim: int,
        hidden_dim: int,
        x_mean: Tensor,
        x_std: Tensor,
        y_mean: Tensor,
        y_std: Tensor,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.register_buffer("x_mean", x_mean)
        self.register_buffer("x_std", x_std)
        self.register_buffer("y_mean", y_mean)
        self.register_buffer("y_std", y_std)
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, target_dim),
        )

    def forward(self, x: Tensor) -> Tensor:
        normalized = (x - self.x_mean) / self.x_std
        predicted = self.net(normalized)
        return predicted * self.y_std + self.y_mean

    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


def selected_details(
    model: SparseRecurrentEcology,
    event: Tensor,
    workspace: Tensor,
    cell_states: Tensor,
):
    c = model.config
    h = c.state_dim

    event_embedding = model.event_encoder(event)
    selected, route_weights, scores, _ = model._route(
        event_embedding,
        workspace,
        add_training_noise=False,
    )

    selected_signatures = model._gather_cell_tensor(
        model.cell_signatures, selected
    )
    read_queries = model.signature_read_query(selected_signatures)
    read_logits = torch.einsum(
        "bkh,bsh->bks", read_queries, workspace
    ) / (h ** 0.5)
    read_weights = torch.softmax(read_logits, dim=-1)
    workspace_reads = torch.einsum(
        "bks,bsh->bkh", read_weights, workspace
    )

    selected_states = torch.gather(
        cell_states,
        dim=1,
        index=selected.unsqueeze(-1).expand(-1, -1, h),
    )

    new_cell_states, messages = model._selected_cell_update(
        event_embedding,
        workspace,
        cell_states,
        selected,
        route_weights,
    )
    new_selected_states = torch.gather(
        new_cell_states,
        dim=1,
        index=selected.unsqueeze(-1).expand(-1, -1, h),
    )

    return {
        "event_embedding": event_embedding,
        "selected": selected,
        "route_weights": route_weights,
        "scores": scores,
        "workspace_reads": workspace_reads,
        "selected_states": selected_states,
        "new_cell_states": new_cell_states,
        "new_selected_states": new_selected_states,
        "messages": messages,
    }


def pair_rows(
    selected: Tensor,
    left: int,
    right: int,
) -> Tuple[Tensor, Tensor, Tensor]:
    has_left = selected == left
    has_right = selected == right
    mask = has_left.any(dim=1) & has_right.any(dim=1)
    rows = torch.nonzero(mask, as_tuple=False).flatten()
    if rows.numel() == 0:
        empty = torch.empty(0, dtype=torch.long, device=selected.device)
        return rows, empty, empty
    left_pos = torch.argmax(has_left[rows].long(), dim=1)
    right_pos = torch.argmax(has_right[rows].long(), dim=1)
    return rows, left_pos, right_pos


def make_pair_input_target(
    details,
    left: int,
    right: int,
) -> Tuple[Tensor, Tensor]:
    rows, left_pos, right_pos = pair_rows(
        details["selected"], left, right
    )
    if rows.numel() == 0:
        return (
            torch.empty(0, 0, device=details["selected"].device),
            torch.empty(0, 0, device=details["selected"].device),
        )

    def at(tensor: Tensor, positions: Tensor) -> Tensor:
        return tensor[rows, positions]

    left_read = at(details["workspace_reads"], left_pos)
    right_read = at(details["workspace_reads"], right_pos)
    event = details["event_embedding"][rows]
    left_state = at(details["selected_states"], left_pos)
    right_state = at(details["selected_states"], right_pos)
    left_weight = at(
        details["route_weights"].unsqueeze(-1), left_pos
    )
    right_weight = at(
        details["route_weights"].unsqueeze(-1), right_pos
    )

    left_new = at(details["new_selected_states"], left_pos)
    right_new = at(details["new_selected_states"], right_pos)
    left_message = at(details["messages"], left_pos)
    right_message = at(details["messages"], right_pos)

    x = torch.cat(
        [
            left_read,
            right_read,
            event,
            left_state,
            right_state,
            left_weight,
            right_weight,
        ],
        dim=-1,
    )
    y = torch.cat(
        [
            left_new - left_state,
            right_new - right_state,
            left_message,
            right_message,
        ],
        dim=-1,
    )
    return x, y


def collect_teacher_samples(
    model: SparseRecurrentEcology,
    *,
    left: int,
    right: int,
    batches: int,
    batch_size: int,
    sequence_length: int,
    seed: int,
) -> Tuple[Tensor, Tensor, Dict[str, int]]:
    torch.manual_seed(seed)
    xs: List[Tensor] = []
    ys: List[Tensor] = []
    thought_rows = 0
    pair_rows_count = 0

    with torch.no_grad():
        for _ in range(batches):
            events, _, _ = sample_program_batch(
                batch_size,
                sequence_length,
                forbidden_bigrams=held_out_bigrams(),
            )
            state = model.initial_state(batch_size)
            workspace = state.workspace
            cell_states = state.cell_states

            for t in range(sequence_length):
                for _thought in range(model.config.max_thought_steps):
                    details = selected_details(
                        model,
                        events[:, t],
                        workspace,
                        cell_states,
                    )
                    thought_rows += batch_size
                    x, y = make_pair_input_target(
                        details, left, right
                    )
                    if x.numel() > 0:
                        xs.append(x.cpu())
                        ys.append(y.cpu())
                        pair_rows_count += x.shape[0]

                    workspace = model._workspace_write(
                        workspace,
                        details["messages"],
                    )
                    cell_states = details["new_cell_states"]

    if not xs:
        raise RuntimeError("No motif training samples were collected")

    return (
        torch.cat(xs, dim=0),
        torch.cat(ys, dim=0),
        {
            "thought_rows": thought_rows,
            "pair_rows": pair_rows_count,
        },
    )


def train_composite(
    x: Tensor,
    y: Tensor,
    *,
    hidden_dim: int,
    steps: int,
    batch_size: int,
    learning_rate: float,
    seed: int,
) -> Tuple[PairComposite, Dict[str, float]]:
    torch.manual_seed(seed)

    permutation = torch.randperm(x.shape[0])
    split = max(1, int(x.shape[0] * 0.9))
    train_idx = permutation[:split]
    val_idx = permutation[split:]

    x_train = x[train_idx]
    y_train = y[train_idx]
    x_val = x[val_idx]
    y_val = y[val_idx]

    x_mean = x_train.mean(dim=0)
    x_std = x_train.std(dim=0).clamp_min(1e-4)
    y_mean = y_train.mean(dim=0)
    y_std = y_train.std(dim=0).clamp_min(1e-4)

    composite = PairComposite(
        x.shape[1],
        y.shape[1],
        hidden_dim,
        x_mean,
        x_std,
        y_mean,
        y_std,
    )
    optimizer = torch.optim.AdamW(
        composite.parameters(),
        lr=learning_rate,
        weight_decay=1e-5,
    )

    composite.train()
    for _ in range(steps):
        indices = torch.randint(
            0, x_train.shape[0], (batch_size,)
        )
        pred = composite(x_train[indices])
        # Train in normalized target coordinates so state/message dimensions
        # receive comparable pressure.
        loss = F.mse_loss(
            (pred - y_mean) / y_std,
            (y_train[indices] - y_mean) / y_std,
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(composite.parameters(), 1.0)
        optimizer.step()

    composite.eval()
    with torch.no_grad():
        train_pred = composite(x_train)
        val_pred = composite(x_val) if x_val.numel() else train_pred[:1]
        train_mse = F.mse_loss(train_pred, y_train)
        val_mse = (
            F.mse_loss(val_pred, y_val)
            if x_val.numel()
            else train_mse
        )

    return composite, {
        "train_mse": float(train_mse),
        "val_mse": float(val_mse),
    }


def compiled_thought_step(
    model: SparseRecurrentEcology,
    composite: PairComposite,
    event: Tensor,
    workspace: Tensor,
    cell_states: Tensor,
    *,
    left: int,
    right: int,
):
    c = model.config
    h = c.state_dim
    m = c.message_dim

    details = selected_details(
        model,
        event,
        workspace,
        cell_states,
    )
    selected = details["selected"]
    new_cell_states = details["new_cell_states"].clone()
    messages = details["messages"].clone()

    rows, left_pos, right_pos = pair_rows(selected, left, right)
    motif_uses = int(rows.numel())

    if motif_uses:
        x, _ = make_pair_input_target(details, left, right)
        pred = composite(x)

        cursor = 0
        left_delta = pred[:, cursor : cursor + h]
        cursor += h
        right_delta = pred[:, cursor : cursor + h]
        cursor += h
        left_message = pred[:, cursor : cursor + m]
        cursor += m
        right_message = pred[:, cursor : cursor + m]

        left_old = details["selected_states"][rows, left_pos]
        right_old = details["selected_states"][rows, right_pos]

        left_new = left_old + left_delta
        right_new = right_old + right_delta

        new_cell_states[rows, left] = left_new
        new_cell_states[rows, right] = right_new
        messages[rows, left_pos] = left_message
        messages[rows, right_pos] = right_message

    new_workspace = model._workspace_write(workspace, messages)
    output = model.output_head(new_workspace.mean(dim=1))
    return output, new_workspace, new_cell_states, motif_uses


def evaluate_compiled(
    model: SparseRecurrentEcology,
    composite: PairComposite | None,
    *,
    left: int,
    right: int,
    batches: int,
    batch_size: int,
    sequence_length: int,
    seed: int,
):
    torch.manual_seed(seed)
    task_abs = 0.0
    teacher_compiled_abs = 0.0
    values = 0
    motif_uses = 0
    thought_rows = 0

    with torch.no_grad():
        for _ in range(batches):
            events, targets, _ = sample_forced_bigram_batch(
                batch_size,
                sequence_length,
                bigrams=held_out_bigrams(),
            )

            teacher_state = model.initial_state(batch_size)
            compiled_state = model.initial_state(batch_size)

            teacher_outputs = []
            compiled_outputs = []

            for t in range(sequence_length):
                teacher_out = None
                compiled_out = None

                for _thought in range(model.config.max_thought_steps):
                    (
                        teacher_out,
                        teacher_workspace,
                        teacher_cells,
                        *_,
                    ) = model.thought_step(
                        events[:, t],
                        teacher_state.workspace,
                        teacher_state.cell_states,
                        add_training_noise=False,
                    )
                    teacher_state.workspace = teacher_workspace
                    teacher_state.cell_states = teacher_cells

                    if composite is None:
                        (
                            compiled_out,
                            compiled_workspace,
                            compiled_cells,
                            *_,
                        ) = model.thought_step(
                            events[:, t],
                            compiled_state.workspace,
                            compiled_state.cell_states,
                            add_training_noise=False,
                        )
                        uses = 0
                    else:
                        (
                            compiled_out,
                            compiled_workspace,
                            compiled_cells,
                            uses,
                        ) = compiled_thought_step(
                            model,
                            composite,
                            events[:, t],
                            compiled_state.workspace,
                            compiled_state.cell_states,
                            left=left,
                            right=right,
                        )
                    compiled_state.workspace = compiled_workspace
                    compiled_state.cell_states = compiled_cells
                    motif_uses += uses
                    thought_rows += batch_size

                assert teacher_out is not None
                assert compiled_out is not None
                teacher_outputs.append(teacher_out)
                compiled_outputs.append(compiled_out)

            teacher_outputs_t = torch.stack(teacher_outputs, dim=1)
            compiled_outputs_t = torch.stack(compiled_outputs, dim=1)

            task_abs += float(
                (compiled_outputs_t - targets).abs().sum()
            )
            teacher_compiled_abs += float(
                (compiled_outputs_t - teacher_outputs_t).abs().sum()
            )
            values += targets.numel()

    return {
        "task_mae": task_abs / values,
        "mean_abs_output_delta_vs_teacher": (
            teacher_compiled_abs / values
        ),
        "motif_use_fraction_of_thought_rows": (
            motif_uses / max(1, thought_rows)
        ),
        "motif_uses": motif_uses,
        "thought_rows": thought_rows,
    }


def pair_private_multiply_estimate(
    model: SparseRecurrentEcology,
) -> int:
    h = model.config.state_dim
    m = model.config.message_dim
    # Per cell: input gates 3h*2h + hidden gates 3h*h + message m*h.
    return 2 * (6 * h * h + 3 * h * h + m * h)


def composite_multiply_estimate(
    input_dim: int,
    target_dim: int,
    hidden_dim: int,
) -> int:
    return input_dim * hidden_dim + hidden_dim * target_dim


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("checkpoint")
    p.add_argument("--left", type=int, default=1)
    p.add_argument("--right", type=int, default=10)
    p.add_argument("--collect-batches", type=int, default=80)
    p.add_argument("--collect-batch-size", type=int, default=128)
    p.add_argument("--sequence-length", type=int, default=6)
    p.add_argument("--hidden-dims", default="64,96,128")
    p.add_argument("--train-steps", type=int, default=1600)
    p.add_argument("--train-batch-size", type=int, default=512)
    p.add_argument("--learning-rate", type=float, default=8e-4)
    p.add_argument("--eval-batches", type=int, default=4)
    p.add_argument("--eval-batch-size", type=int, default=128)
    p.add_argument("--output", default="artifacts/motif-compilation.json")
    args = p.parse_args()

    model = load_checkpoint(Path(args.checkpoint)).eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)

    x, y, collection = collect_teacher_samples(
        model,
        left=args.left,
        right=args.right,
        batches=args.collect_batches,
        batch_size=args.collect_batch_size,
        sequence_length=args.sequence_length,
        seed=211,
    )

    source_multiplies = pair_private_multiply_estimate(model)
    variants = []

    baseline = evaluate_compiled(
        model,
        None,
        left=args.left,
        right=args.right,
        batches=args.eval_batches,
        batch_size=args.eval_batch_size,
        sequence_length=args.sequence_length,
        seed=307,
    )

    for hidden_dim in [
        int(value) for value in args.hidden_dims.split(",")
    ]:
        composite, train_metrics = train_composite(
            x,
            y,
            hidden_dim=hidden_dim,
            steps=args.train_steps,
            batch_size=args.train_batch_size,
            learning_rate=args.learning_rate,
            seed=hidden_dim + 1000,
        )

        evaluation = evaluate_compiled(
            model,
            composite,
            left=args.left,
            right=args.right,
            batches=args.eval_batches,
            batch_size=args.eval_batch_size,
            sequence_length=args.sequence_length,
            seed=307,
        )

        student_multiplies = composite_multiply_estimate(
            x.shape[1],
            y.shape[1],
            hidden_dim,
        )
        variants.append(
            {
                "hidden_dim": hidden_dim,
                "parameters": composite.parameter_count(),
                "private_multiply_estimate": student_multiplies,
                "pair_compute_ratio_vs_sources": (
                    student_multiplies / source_multiplies
                ),
                "train": train_metrics,
                "evaluation": evaluation,
                "task_mae_delta_vs_teacher": (
                    evaluation["task_mae"] - baseline["task_mae"]
                ),
            }
        )

    output = {
        "schema": 1,
        "motif": [args.left, args.right],
        "teacher": {
            "source_pair_private_multiply_estimate": source_multiplies,
            "baseline_evaluation": baseline,
        },
        "collection": {
            **collection,
            "samples": x.shape[0],
            "input_dim": x.shape[1],
            "target_dim": y.shape[1],
        },
        "variants": variants,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
