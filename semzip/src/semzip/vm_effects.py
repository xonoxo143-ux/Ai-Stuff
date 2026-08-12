from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from .vm_ledger import atom


@dataclass(frozen=True, slots=True)
class ShiftEffect:
    """Atomic partial state transformation: subject.dimension : source -> destination."""

    subject: str
    dimension: str
    source: str
    destination: str

    @classmethod
    def build(
        cls,
        subject: str,
        dimension: str,
        source: str,
        destination: str,
    ) -> "ShiftEffect":
        return cls(atom(subject), atom(dimension), atom(source), atom(destination))

    @property
    def cell(self) -> tuple[str, str]:
        return (self.subject, self.dimension)

    def key(self) -> tuple[str, str, str, str]:
        return (self.subject, self.dimension, self.source, self.destination)

    def inverse(self) -> "ShiftEffect":
        return ShiftEffect(self.subject, self.dimension, self.destination, self.source)


@dataclass(frozen=True, slots=True)
class SetEffect:
    """Atomic assignment: subject.dimension := value."""

    subject: str
    dimension: str
    value: str

    @classmethod
    def build(cls, subject: str, dimension: str, value: str) -> "SetEffect":
        return cls(atom(subject), atom(dimension), atom(value))

    @property
    def cell(self) -> tuple[str, str]:
        return (self.subject, self.dimension)

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.dimension, self.value)


@dataclass(frozen=True, slots=True)
class ClearEffect:
    """Atomic removal: remove subject.dimension from accepted state."""

    subject: str
    dimension: str

    @classmethod
    def build(cls, subject: str, dimension: str) -> "ClearEffect":
        return cls(atom(subject), atom(dimension))

    @property
    def cell(self) -> tuple[str, str]:
        return (self.subject, self.dimension)

    def key(self) -> tuple[str, str]:
        return (self.subject, self.dimension)


SemanticEffect: TypeAlias = ShiftEffect | SetEffect | ClearEffect


def effect_key(effect: SemanticEffect) -> tuple[str, str, str, str, str]:
    """Fixed-width canonical record used for sorting/fingerprints, not object identity."""
    if isinstance(effect, ShiftEffect):
        return ("shift", effect.dimension, effect.subject, effect.source, effect.destination)
    if isinstance(effect, SetEffect):
        return ("set", effect.dimension, effect.subject, effect.value, "")
    if isinstance(effect, ClearEffect):
        return ("clear", effect.dimension, effect.subject, "", "")
    raise TypeError(f"unknown semantic effect {type(effect)!r}")
