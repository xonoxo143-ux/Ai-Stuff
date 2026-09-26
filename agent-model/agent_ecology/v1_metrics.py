from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Optional, TextIO


@dataclass(frozen=True)
class LifetimeMetric:
    experience_index: int
    hidden_regime: str
    loss: Optional[float] = None
    wall_ms: Optional[float] = None
    active_cells: Optional[int] = None
    thought_steps: Optional[int] = None
    mature_cells: Optional[int] = None
    structural_cost_ms: float = 0.0
    structure_version: int = 0


class JsonlMetricWriter:
    """Simple append-only evaluator log; never used as agent input."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._handle: Optional[TextIO] = None

    def __enter__(self) -> "JsonlMetricWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        return self

    def write(self, metric: LifetimeMetric) -> None:
        if self._handle is None:
            raise RuntimeError("metric writer is not open")
        self._handle.write(
            json.dumps(asdict(metric), sort_keys=True) + "\n"
        )
        self._handle.flush()

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
