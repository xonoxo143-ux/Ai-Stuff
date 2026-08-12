from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .vm_effects import ClearEffect, SetEffect, ShiftEffect
from .vm_ledger import atom
from .vm_transform import SemanticTransform


StateTuple = tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """Small immutable projected state for reasoning/simulation.

    EventLedger is durable history. StateSnapshot is the disposable value used inside
    search and counterfactual computation, so planning does not rebuild event histories
    for every candidate transition.
    """

    facts: StateTuple

    @classmethod
    def build(
        cls,
        facts: Iterable[tuple[str, str, str]] | Mapping[tuple[str, str], str],
    ) -> "StateSnapshot":
        if isinstance(facts, Mapping):
            items = (
                (atom(subject), atom(dimension), atom(value))
                for (subject, dimension), value in facts.items()
            )
        else:
            items = (
                (atom(subject), atom(dimension), atom(value))
                for subject, dimension, value in facts
            )
        keyed: dict[tuple[str, str], str] = {}
        for subject, dimension, value in items:
            key = (subject, dimension)
            previous = keyed.get(key)
            if previous is not None and previous != value:
                raise ValueError(f"state snapshot has conflicting values for {key}")
            keyed[key] = value
        return cls(tuple(sorted((s, d, v) for (s, d), v in keyed.items())))

    @classmethod
    def empty(cls) -> "StateSnapshot":
        return cls(())

    def as_dict(self) -> dict[tuple[str, str], str]:
        return {(subject, dimension): value for subject, dimension, value in self.facts}

    def get(self, subject: str, dimension: str) -> str | None:
        key = (atom(subject), atom(dimension))
        for s, d, value in self.facts:
            if (s, d) == key:
                return value
        return None

    def contains(self, subject: str, dimension: str, value: str) -> bool:
        return self.get(subject, dimension) == atom(value)

    def subjects(self, dimension: str | None = None) -> tuple[str, ...]:
        wanted = None if dimension is None else atom(dimension)
        return tuple(sorted({s for s, d, _ in self.facts if wanted is None or d == wanted}))

    def apply(self, transform: SemanticTransform) -> "StateSnapshot | None":
        """Purely apply a partial semantic transform, returning None outside its domain."""

        state = self.as_dict()
        for guard in transform.constraints:
            if state.get(guard.cell) != guard.value:
                return None

        for effect in transform.patch.effects:
            if isinstance(effect, ShiftEffect):
                if state.get(effect.cell) != effect.source:
                    return None
                state[effect.cell] = effect.destination
            elif isinstance(effect, SetEffect):
                state[effect.cell] = effect.value
            elif isinstance(effect, ClearEffect):
                state.pop(effect.cell, None)

        return StateSnapshot.build(state)


def snapshot_from_state(state: StateTuple | StateSnapshot) -> StateSnapshot:
    return state if isinstance(state, StateSnapshot) else StateSnapshot.build(state)
