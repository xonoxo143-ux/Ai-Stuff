from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional, Sequence, Tuple

import torch
from torch import Tensor

from .curriculum import OPS, OP_TO_ID, ProgramCurriculumConfig


RuleSet = Tuple[str, ...]
Bigram = Tuple[str, str]


@dataclass(frozen=True)
class RegimePhase:
    name: str
    start_fraction: float
    end_fraction: float
    rules: RuleSet = ()
    forced_bigram: Optional[Bigram] = None
    forced_probability: float = 0.0
    decoy_bigram: Optional[Bigram] = None
    decoy_probability: float = 0.0

    def validate(self) -> None:
        if not 0.0 <= self.start_fraction < self.end_fraction <= 1.0:
            raise ValueError("invalid regime fraction interval")
        for probability in (self.forced_probability, self.decoy_probability):
            if not 0.0 <= probability <= 1.0:
                raise ValueError("pattern probabilities must be in [0, 1]")
        for pair in (self.forced_bigram, self.decoy_bigram):
            if pair is not None and any(op not in OP_TO_ID for op in pair):
                raise ValueError(f"unknown operation in bigram: {pair}")


def default_regime_schedule() -> Tuple[RegimePhase, ...]:
    return (
        RegimePhase("base", 0.00, 0.10),
        RegimePhase(
            "gain_add",
            0.10,
            0.25,
            rules=("gain_add",),
        ),
        RegimePhase(
            "mul_neg_interaction",
            0.25,
            0.40,
            rules=("mul_neg_interaction",),
            forced_bigram=("MUL", "NEG"),
            forced_probability=0.35,
        ),
        RegimePhase(
            "gain_plus_mul_neg",
            0.40,
            0.55,
            rules=("gain_add", "mul_neg_interaction"),
            forced_bigram=("MUL", "NEG"),
            forced_probability=0.35,
        ),
        RegimePhase(
            "base_with_decoy",
            0.55,
            0.70,
            decoy_bigram=("ABS", "HALF"),
            decoy_probability=0.55,
        ),
        RegimePhase(
            "square_half_interaction",
            0.70,
            0.85,
            rules=("square_half_interaction",),
            forced_bigram=("SQUARE", "HALF"),
            forced_probability=0.35,
        ),
        RegimePhase(
            "gain_plus_square_half",
            0.85,
            1.00,
            rules=("gain_add", "square_half_interaction"),
            forced_bigram=("SQUARE", "HALF"),
            forced_probability=0.35,
        ),
    )


@dataclass(frozen=True)
class LifetimeWorldConfig:
    total_experiences: int = 100_000
    sequence_length: int = 6
    seed: int = 20260926
    value_low: float = -2.0
    value_high: float = 2.0
    phases: Tuple[RegimePhase, ...] = field(
        default_factory=default_regime_schedule
    )

    @property
    def event_dim(self) -> int:
        return ProgramCurriculumConfig().event_dim

    def validate(self) -> None:
        if self.total_experiences <= 0:
            raise ValueError("total_experiences must be positive")
        if self.sequence_length < 3:
            raise ValueError("sequence_length must be at least 3")
        if self.value_low >= self.value_high:
            raise ValueError("value_low must be below value_high")
        if not self.phases:
            raise ValueError("at least one regime phase is required")

        expected_start = 0.0
        for phase in self.phases:
            phase.validate()
            if abs(phase.start_fraction - expected_start) > 1e-9:
                raise ValueError("regime phases must be contiguous")
            expected_start = phase.end_fraction
        if abs(expected_start - 1.0) > 1e-9:
            raise ValueError("regime phases must cover the full lifetime")


@dataclass(frozen=True)
class LifetimeExperience:
    index: int
    events: Tensor
    targets: Tensor
    op_ids: Tensor

    # Evaluator-only metadata. These fields must never be concatenated onto the
    # event tensor or fed to the model.
    hidden_regime: str
    hidden_rules: RuleSet
    forced_pattern_applied: bool
    decoy_pattern_applied: bool

    def training_view(self) -> Tuple[Tensor, Tensor]:
        return self.events, self.targets


_ARGUMENT_OPS = frozenset(
    OP_TO_ID[name] for name in ("SET", "ADD", "SUB", "MUL")
)


def _splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9 & mask
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB & mask
    return value ^ (value >> 31)


def _experience_seed(world_seed: int, index: int) -> int:
    mixed = _splitmix64(
        (int(world_seed) & ((1 << 64) - 1))
        ^ _splitmix64(index + 0xA0761D6478BD642F)
    )
    return int(mixed & ((1 << 63) - 1))


def _clamp(value: float) -> float:
    return max(-8.0, min(8.0, value))


def _apply_hidden_step(
    register: float,
    op_id: int,
    argument: float,
    previous_op_id: Optional[int],
    rules: Sequence[str],
) -> float:
    op = OPS[op_id]
    rule_set = set(rules)

    if "gain_add" in rule_set and op in ("ADD", "SUB"):
        argument *= 1.5

    if (
        "square_half_interaction" in rule_set
        and previous_op_id == OP_TO_ID["SQUARE"]
        and op_id == OP_TO_ID["HALF"]
    ):
        result = register * 0.25
    elif op == "SET":
        result = argument
    elif op == "ADD":
        result = register + argument
    elif op == "SUB":
        result = register - argument
    elif op == "MUL":
        result = register * argument
    elif op == "NEG":
        result = -register
    elif op == "ABS":
        result = abs(register)
    elif op == "HALF":
        result = register * 0.5
    elif op == "SQUARE":
        result = register * register
    else:
        raise ValueError(f"unsupported operation id: {op_id}")

    if (
        "mul_neg_interaction" in rule_set
        and previous_op_id == OP_TO_ID["MUL"]
        and op_id == OP_TO_ID["NEG"]
    ):
        result += 0.75

    return _clamp(result)


def targets_for_program(
    op_ids: Tensor,
    arguments: Tensor,
    *,
    rules: Sequence[str] = (),
) -> Tensor:
    if op_ids.ndim != 1 or arguments.ndim != 1:
        raise ValueError("op_ids and arguments must be rank-1")
    if op_ids.shape[0] != arguments.shape[0]:
        raise ValueError("op_ids and arguments must have equal length")

    register = 0.0
    previous: Optional[int] = None
    values = []
    for position in range(op_ids.shape[0]):
        current = int(op_ids[position])
        register = _apply_hidden_step(
            register,
            current,
            float(arguments[position]),
            previous,
            rules,
        )
        values.append(register)
        previous = current

    return torch.tensor(values, dtype=torch.float32).unsqueeze(-1)


class LifetimeWorld:
    """
    Deterministic nonstationary procedural world for Agent v1-A.

    Every experience is a pure function of (world seed, experience index).
    Random-access replay is therefore exact and checkpointing only needs the
    next experience index plus a configuration fingerprint.
    """

    def __init__(self, config: LifetimeWorldConfig):
        config.validate()
        self.config = config

    def regime_for(self, index: int) -> RegimePhase:
        if not 0 <= index < self.config.total_experiences:
            raise IndexError("experience index outside configured lifetime")
        progress = (index + 0.5) / self.config.total_experiences
        for phase in self.config.phases:
            if phase.start_fraction <= progress < phase.end_fraction:
                return phase
        return self.config.phases[-1]

    def _generator(self, index: int) -> torch.Generator:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(_experience_seed(self.config.seed, index))
        return generator

    @staticmethod
    def _draw_probability(
        generator: torch.Generator,
        probability: float,
    ) -> bool:
        if probability <= 0.0:
            return False
        return bool(
            torch.rand((), generator=generator).item() < probability
        )

    def _insert_bigram(
        self,
        op_ids: Tensor,
        pair: Bigram,
        generator: torch.Generator,
    ) -> None:
        # Position zero remains SET. With sequence_length >= 3 there is always
        # at least one legal two-operation insertion window.
        start = int(
            torch.randint(
                1,
                self.config.sequence_length - 1,
                (1,),
                generator=generator,
            ).item()
        )
        op_ids[start] = OP_TO_ID[pair[0]]
        op_ids[start + 1] = OP_TO_ID[pair[1]]

    def experience(self, index: int) -> LifetimeExperience:
        phase = self.regime_for(index)
        generator = self._generator(index)
        length = self.config.sequence_length

        op_ids = torch.empty(length, dtype=torch.long)
        op_ids[0] = OP_TO_ID["SET"]
        op_ids[1:] = torch.randint(
            1,
            len(OPS),
            (length - 1,),
            generator=generator,
        )

        forced_applied = False
        if (
            phase.forced_bigram is not None
            and self._draw_probability(
                generator, phase.forced_probability
            )
        ):
            self._insert_bigram(
                op_ids,
                phase.forced_bigram,
                generator,
            )
            forced_applied = True

        decoy_applied = False
        if (
            phase.decoy_bigram is not None
            and self._draw_probability(
                generator, phase.decoy_probability
            )
        ):
            self._insert_bigram(
                op_ids,
                phase.decoy_bigram,
                generator,
            )
            decoy_applied = True

        arguments = torch.empty(length).uniform_(
            self.config.value_low,
            self.config.value_high,
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
            length,
            self.config.event_dim,
            dtype=torch.float32,
        )
        events.scatter_(1, op_ids.unsqueeze(-1), 1.0)
        arg_column = len(OPS)
        events[:, arg_column] = arguments
        events[:, arg_column + 1] = needs_argument.float()
        events[:, arg_column + 2] = 1.0

        targets = targets_for_program(
            op_ids,
            arguments,
            rules=phase.rules,
        )

        return LifetimeExperience(
            index=index,
            events=events,
            targets=targets,
            op_ids=op_ids,
            hidden_regime=phase.name,
            hidden_rules=phase.rules,
            forced_pattern_applied=forced_applied,
            decoy_pattern_applied=decoy_applied,
        )

    def iter_from(
        self,
        start: int = 0,
        stop: Optional[int] = None,
    ) -> Iterator[LifetimeExperience]:
        if stop is None:
            stop = self.config.total_experiences
        if not 0 <= start <= stop <= self.config.total_experiences:
            raise ValueError("invalid lifetime iteration range")
        for index in range(start, stop):
            yield self.experience(index)
