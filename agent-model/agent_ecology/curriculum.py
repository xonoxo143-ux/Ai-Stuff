from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import torch
from torch import Tensor


OPS: Tuple[str, ...] = (
    "SET",
    "ADD",
    "SUB",
    "MUL",
    "NEG",
    "ABS",
    "HALF",
    "SQUARE",
)

OP_TO_ID: Dict[str, int] = {name: index for index, name in enumerate(OPS)}


@dataclass(frozen=True)
class ProgramCurriculumConfig:
    min_length: int = 2
    max_length: int = 6
    value_low: float = -2.0
    value_high: float = 2.0

    @property
    def event_dim(self) -> int:
        # op one-hot + argument + "argument present" flag + bias/context flag
        return len(OPS) + 3


def apply_op(register: Tensor, op_id: Tensor, argument: Tensor) -> Tensor:
    result = register.clone()

    masks = [op_id == index for index in range(len(OPS))]

    result = torch.where(masks[OP_TO_ID["SET"]], argument, result)
    result = torch.where(masks[OP_TO_ID["ADD"]], register + argument, result)
    result = torch.where(masks[OP_TO_ID["SUB"]], register - argument, result)
    result = torch.where(masks[OP_TO_ID["MUL"]], register * argument, result)
    result = torch.where(masks[OP_TO_ID["NEG"]], -register, result)
    result = torch.where(masks[OP_TO_ID["ABS"]], register.abs(), result)
    result = torch.where(masks[OP_TO_ID["HALF"]], register * 0.5, result)
    result = torch.where(masks[OP_TO_ID["SQUARE"]], register.square(), result)

    # Keep the toy curriculum numerically bounded so training tests cognition,
    # not exploding target scale.
    return result.clamp(-8.0, 8.0)


def _op_needs_argument(op_id: Tensor) -> Tensor:
    return (
        (op_id == OP_TO_ID["SET"])
        | (op_id == OP_TO_ID["ADD"])
        | (op_id == OP_TO_ID["SUB"])
        | (op_id == OP_TO_ID["MUL"])
    )


def sample_program_batch(
    batch_size: int,
    sequence_length: int,
    *,
    device: torch.device | str = "cpu",
    value_low: float = -2.0,
    value_high: float = 2.0,
    forbidden_bigrams: Sequence[Tuple[str, str]] = (),
) -> Tuple[Tensor, Tensor, Tensor]:
    """
    Generate a compositional register-machine curriculum.

    Returns:
      events  [B, T, event_dim]
      targets [B, T, 1]
      op_ids  [B, T]

    Some operation bigrams may be withheld during training and used later for
    recombination tests.
    """
    if sequence_length < 1:
        raise ValueError("sequence_length must be positive")

    device = torch.device(device)
    forbidden_ids = {
        (OP_TO_ID[a], OP_TO_ID[b]) for a, b in forbidden_bigrams
    }

    op_ids = torch.empty(
        batch_size, sequence_length, dtype=torch.long, device=device
    )

    # Always begin with SET so the desired state is fully specified.
    op_ids[:, 0] = OP_TO_ID["SET"]

    for t in range(1, sequence_length):
        proposal = torch.randint(
            1, len(OPS), (batch_size,), device=device
        )
        if forbidden_ids:
            previous = op_ids[:, t - 1]
            for _ in range(16):
                invalid = torch.zeros(
                    batch_size, dtype=torch.bool, device=device
                )
                for left, right in forbidden_ids:
                    invalid |= (previous == left) & (proposal == right)
                if not bool(invalid.any()):
                    break
                proposal = torch.where(
                    invalid,
                    torch.randint(1, len(OPS), (batch_size,), device=device),
                    proposal,
                )
        op_ids[:, t] = proposal

    arguments = torch.empty(
        batch_size, sequence_length, device=device
    ).uniform_(value_low, value_high)

    needs_argument = _op_needs_argument(op_ids)
    arguments = torch.where(
        needs_argument,
        arguments,
        torch.zeros_like(arguments),
    )

    event_dim = len(OPS) + 3
    events = torch.zeros(
        batch_size, sequence_length, event_dim, device=device
    )
    events.scatter_(2, op_ids.unsqueeze(-1), 1.0)
    events[:, :, len(OPS)] = arguments
    events[:, :, len(OPS) + 1] = needs_argument.float()
    events[:, :, len(OPS) + 2] = 1.0

    register = torch.zeros(batch_size, device=device)
    targets = torch.empty(
        batch_size, sequence_length, 1, device=device
    )
    for t in range(sequence_length):
        register = apply_op(
            register,
            op_ids[:, t],
            arguments[:, t],
        )
        targets[:, t, 0] = register

    return events, targets, op_ids


def held_out_bigrams() -> Tuple[Tuple[str, str], ...]:
    return (
        ("MUL", "NEG"),
        ("SQUARE", "HALF"),
        ("ABS", "SUB"),
        ("ADD", "SQUARE"),
    )
