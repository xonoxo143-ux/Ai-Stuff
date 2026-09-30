from __future__ import annotations

from dataclasses import dataclass
import math

import torch

from .data import ByteBatchStream


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    end_step: int
    weights: dict[str, float]


def allocate_counts(weights: dict[str, float], batch_size: int) -> dict[str, int]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    positive = {k: float(v) for k, v in weights.items() if float(v) > 0}
    total = sum(positive.values())
    if not positive or abs(total - 1.0) > 1e-6:
        raise ValueError(f"phase weights must sum to 1, got {total}")

    raw = {k: v * batch_size for k, v in positive.items()}
    counts = {k: int(math.floor(v)) for k, v in raw.items()}
    remaining = batch_size - sum(counts.values())
    order = sorted(
        positive,
        key=lambda k: (-(raw[k] - counts[k]), k),
    )
    for key in order[:remaining]:
        counts[key] += 1
    return counts


def parse_phases(rows: list[dict], streams: set[str], total_steps: int) -> list[PhaseSpec]:
    phases: list[PhaseSpec] = []
    previous = 0
    for row in rows:
        name = str(row["name"])
        end = int(row["end_step"])
        if end <= previous:
            raise ValueError("curriculum end_step values must increase")
        weights = {str(k): float(v) for k, v in row["weights"].items()}
        unknown = set(weights) - streams
        if unknown:
            raise ValueError(f"unknown curriculum streams: {sorted(unknown)}")
        allocate_counts(weights, 64)
        phases.append(PhaseSpec(name, end, weights))
        previous = end
    if not phases or phases[-1].end_step != total_steps:
        raise ValueError("last curriculum phase must end at total steps")
    return phases


class CurriculumBatcher:
    def __init__(
        self,
        data: dict[str, bytes],
        *,
        seed: int,
        phases: list[PhaseSpec],
    ) -> None:
        self.streams = {
            name: ByteBatchStream(payload, seed=seed + 1009 * (i + 1))
            for i, (name, payload) in enumerate(sorted(data.items()))
        }
        self.phases = phases

    def phase_for_step(self, step: int) -> PhaseSpec:
        if step <= 0:
            raise ValueError("step is 1-indexed")
        for phase in self.phases:
            if step <= phase.end_step:
                return phase
        raise ValueError(f"step {step} exceeds curriculum")

    def batch(
        self,
        step: int,
        *,
        batch_size: int,
        sequence_length: int,
    ) -> tuple[torch.Tensor, torch.Tensor, PhaseSpec, dict[str, int]]:
        phase = self.phase_for_step(step)
        counts = allocate_counts(phase.weights, batch_size)
        xs: list[torch.Tensor] = []
        ys: list[torch.Tensor] = []
        for name in sorted(counts):
            count = counts[name]
            if count <= 0:
                continue
            x, y = self.streams[name].batch(count, sequence_length)
            xs.append(x)
            ys.append(y)
        return torch.cat(xs, dim=0), torch.cat(ys, dim=0), phase, counts

    def rng_states(self) -> dict[str, object]:
        return {
            name: stream.rng.getstate()
            for name, stream in self.streams.items()
        }

    def set_rng_states(self, states: dict[str, object]) -> None:
        if set(states) != set(self.streams):
            raise ValueError("curriculum stream RNG state mismatch")
        for name, state in states.items():
            self.streams[name].rng.setstate(state)
