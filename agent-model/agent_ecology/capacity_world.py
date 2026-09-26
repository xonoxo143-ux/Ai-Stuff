from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterator, Optional, Tuple

import torch
from torch import Tensor

from .curriculum import OPS, OP_TO_ID, ProgramCurriculumConfig


@dataclass(frozen=True)
class CapacityWorldConfig:
    num_families: int
    experiences_per_family: int = 20
    sequence_length: int = 4
    seed: int = 3001
    code_dim: int = 8
    latent_dim: int = 6
    value_low: float = -2.0
    value_high: float = 2.0

    @property
    def total_experiences(self) -> int:
        return self.num_families * self.experiences_per_family

    @property
    def base_event_dim(self) -> int:
        return ProgramCurriculumConfig().event_dim

    @property
    def event_dim(self) -> int:
        return self.base_event_dim + self.code_dim

    def validate(self) -> None:
        if self.num_families < 4:
            raise ValueError("num_families must be >= 4")
        if self.experiences_per_family <= 0:
            raise ValueError("experiences_per_family must be positive")
        if self.sequence_length < 2:
            raise ValueError("sequence_length must be >= 2")
        if self.code_dim <= 0 or self.latent_dim <= 0:
            raise ValueError("code_dim and latent_dim must be positive")
        if self.value_low >= self.value_high:
            raise ValueError("invalid value range")


@dataclass(frozen=True)
class CapacityExperience:
    index: int
    events: Tensor
    targets: Tensor
    family_id: int
    phase: str


@dataclass(frozen=True)
class FamilyDynamics:
    code: Tensor
    a: Tensor
    b: Tensor
    bias: Tensor
    readout: Tensor


_ARGUMENT_OPS = frozenset(
    OP_TO_ID[name] for name in ("SET", "ADD", "SUB", "MUL")
)


def _splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & mask
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & mask
    return value ^ (value >> 31)


def _seed(base: int, salt: int) -> int:
    mixed = _splitmix64(
        (int(base) & ((1 << 64) - 1))
        ^ _splitmix64(int(salt) + 0xD1B54A32D192ED03)
    )
    return int(mixed & ((1 << 63) - 1))


class CapacityWorld:
    """
    Controlled capacity-pressure world.

    A family is identified to the agent only by a fixed-width continuous public
    code. Behind that code is a deterministic family-specific recurrent target
    system. The target matrices are generated independently from the public
    code, so the agent cannot recover the dynamics from a simple known formula.

    The family count can scale without changing the event interface width.
    """

    def __init__(self, config: CapacityWorldConfig):
        config.validate()
        self.config = config
        self._families: Dict[int, FamilyDynamics] = {
            family_id: self._build_family(family_id)
            for family_id in range(config.num_families)
        }

    def _build_family(self, family_id: int) -> FamilyDynamics:
        c = self.config

        code_generator = torch.Generator(device="cpu")
        code_generator.manual_seed(
            _seed(c.seed ^ 0x13579BDF, family_id)
        )
        code = torch.randn(c.code_dim, generator=code_generator)
        code = code / code.norm().clamp_min(1e-8)

        dyn_generator = torch.Generator(device="cpu")
        dyn_generator.manual_seed(
            _seed(c.seed ^ 0x2468ACE0, family_id)
        )

        a = torch.randn(
            c.latent_dim,
            c.latent_dim,
            generator=dyn_generator,
        )
        # Keep the hidden dynamics stable but recurrent.
        a = 0.62 * a / math.sqrt(c.latent_dim)

        input_dim = len(OPS) + 1
        b = torch.randn(
            c.latent_dim,
            input_dim,
            generator=dyn_generator,
        ) / math.sqrt(input_dim)

        bias = 0.15 * torch.randn(
            c.latent_dim,
            generator=dyn_generator,
        )
        readout = torch.randn(
            c.latent_dim,
            generator=dyn_generator,
        )
        readout = readout / readout.norm().clamp_min(1e-8)

        return FamilyDynamics(
            code=code,
            a=a,
            b=b,
            bias=bias,
            readout=readout,
        )

    def family(self, family_id: int) -> FamilyDynamics:
        return self._families[family_id]

    def phase_for(self, index: int) -> str:
        if not 0 <= index < self.config.total_experiences:
            raise IndexError("experience index outside world")
        progress = (index + 0.5) / self.config.total_experiences
        if progress < 0.25:
            return "foundation"
        if progress < 0.50:
            return "expansion"
        if progress < 0.75:
            return "novel_only"
        return "mixed_return"

    def _family_pool(self, phase: str) -> Tuple[int, ...]:
        n = self.config.num_families
        quarter = max(1, n // 4)
        half = max(2, n // 2)

        if phase == "foundation":
            return tuple(range(quarter))
        if phase == "expansion":
            return tuple(range(half))
        if phase == "novel_only":
            return tuple(range(half, n))
        if phase == "mixed_return":
            return tuple(range(n))
        raise ValueError(f"unknown phase: {phase}")

    def _experience_generator(self, index: int) -> torch.Generator:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(_seed(self.config.seed, 100_000 + index))
        return generator

    def experience(self, index: int) -> CapacityExperience:
        c = self.config
        phase = self.phase_for(index)
        pool = self._family_pool(phase)
        generator = self._experience_generator(index)

        pool_index = int(
            torch.randint(
                0,
                len(pool),
                (1,),
                generator=generator,
            ).item()
        )
        family_id = pool[pool_index]
        dynamics = self.family(family_id)

        op_ids = torch.empty(c.sequence_length, dtype=torch.long)
        op_ids[:] = torch.randint(
            0,
            len(OPS),
            (c.sequence_length,),
            generator=generator,
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

        return CapacityExperience(
            index=index,
            events=events,
            targets=targets,
            family_id=family_id,
            phase=phase,
        )

    def iter_all(self) -> Iterator[CapacityExperience]:
        for index in range(self.config.total_experiences):
            yield self.experience(index)
