from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from .capacity_world import CapacityWorld, CapacityWorldConfig
from .curriculum import OPS, OP_TO_ID


_ARGUMENT_OPS = frozenset(
    OP_TO_ID[name] for name in ("SET", "ADD", "SUB", "MUL")
)


def _splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & mask
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & mask
    return value ^ (value >> 31)


def _sample_seed(
    world_seed: int,
    family_id: int,
    sample_index: int,
    stream: int,
) -> int:
    mixed = _splitmix64(
        int(world_seed)
        ^ _splitmix64(0xC6BC279692B5CC83 + int(family_id))
        ^ _splitmix64(0x9E3779B97F4A7C15 + int(sample_index))
        ^ _splitmix64(0xD1B54A32D192ED03 + int(stream))
    )
    return int(mixed & ((1 << 63) - 1))


@dataclass(frozen=True)
class FamilySample:
    family_id: int
    sample_index: int
    stream: int
    events: Tensor
    targets: Tensor


class BlockedFamilyWorld:
    """
    Explicit-family view of CapacityWorld.

    Family dynamics and public family codes come from CapacityWorld. This
    wrapper changes only the presentation schedule so continual-learning
    forgetting can be measured directly.
    """

    def __init__(self, config: CapacityWorldConfig):
        self.config = config
        self.base = CapacityWorld(config)

    def sample(
        self,
        family_id: int,
        sample_index: int,
        *,
        stream: int,
    ) -> FamilySample:
        c = self.config
        if not 0 <= family_id < c.num_families:
            raise IndexError("family_id outside configured world")
        if sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        if stream < 0:
            raise ValueError("stream must be non-negative")

        dynamics = self.base.family(family_id)
        generator = torch.Generator(device="cpu")
        generator.manual_seed(
            _sample_seed(
                c.seed,
                family_id,
                sample_index,
                stream,
            )
        )

        op_ids = torch.randint(
            0,
            len(OPS),
            (c.sequence_length,),
            generator=generator,
            dtype=torch.long,
        )

        arguments = torch.empty(c.sequence_length).uniform_(
            c.value_low,
            c.value_high,
            generator=generator,
        )
        needs_argument = torch.tensor(
            [int(op_id) in _ARGUMENT_OPS for op_id in op_ids],
            dtype=torch.bool,
        )
        arguments = torch.where(
            needs_argument,
            arguments,
            torch.zeros_like(arguments),
        )

        events = torch.zeros(
            c.sequence_length,
            c.event_dim,
            dtype=torch.float32,
        )
        events.scatter_(1, op_ids.unsqueeze(-1), 1.0)
        arg_column = len(OPS)
        events[:, arg_column] = arguments
        events[:, arg_column + 1] = needs_argument.float()
        events[:, arg_column + 2] = 1.0
        events[:, c.base_event_dim:] = dynamics.code.unsqueeze(0)

        latent = torch.zeros(c.latent_dim)
        targets = torch.empty(c.sequence_length, 1)

        for t in range(c.sequence_length):
            public_input = torch.zeros(len(OPS) + 1)
            public_input[int(op_ids[t])] = 1.0
            public_input[-1] = float(arguments[t])

            latent = torch.tanh(
                dynamics.a @ latent
                + dynamics.b @ public_input
                + dynamics.bias
            )
            targets[t, 0] = 4.0 * torch.tanh(
                torch.dot(dynamics.readout, latent)
            )

        return FamilySample(
            family_id=family_id,
            sample_index=sample_index,
            stream=stream,
            events=events,
            targets=targets,
        )

    def batch(
        self,
        family_id: int,
        count: int,
        *,
        stream: int,
        start: int = 0,
    ) -> tuple[Tensor, Tensor]:
        if count <= 0:
            raise ValueError("count must be positive")
        samples = [
            self.sample(
                family_id,
                start + index,
                stream=stream,
            )
            for index in range(count)
        ]
        return (
            torch.stack([sample.events for sample in samples], dim=0),
            torch.stack([sample.targets for sample in samples], dim=0),
        )
