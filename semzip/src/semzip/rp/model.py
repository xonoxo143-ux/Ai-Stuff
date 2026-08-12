from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


FactKey = tuple[str, str]


def atom(value: str) -> str:
    return "_".join(value.strip().casefold().split())


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    kind: str
    actor: str
    target: str | None = None
    object_id: str | None = None
    location: str | None = None
    succeeded: bool = True
    reason: str | None = None
    data: tuple[tuple[str, str], ...] = ()

    @classmethod
    def build(
        cls,
        seq: int,
        kind: str,
        actor: str,
        *,
        target: str | None = None,
        object_id: str | None = None,
        location: str | None = None,
        succeeded: bool = True,
        reason: str | None = None,
        data: Mapping[str, str] | None = None,
    ) -> "Event":
        return cls(
            seq=seq,
            kind=atom(kind),
            actor=atom(actor),
            target=atom(target) if target else None,
            object_id=atom(object_id) if object_id else None,
            location=atom(location) if location else None,
            succeeded=succeeded,
            reason=reason,
            data=tuple(sorted((atom(k), str(v)) for k, v in (data or {}).items())),
        )

    def datum(self, key: str) -> str | None:
        return dict(self.data).get(atom(key))


@dataclass(frozen=True, slots=True)
class Memory:
    event_seq: int
    summary: str
    salience: float = 0.5
    private: bool = False
    kind: str = "event"


@dataclass(frozen=True, slots=True)
class Belief:
    subject: str
    dimension: str
    value: str | None
    confidence: float = 1.0
    source_event: int | None = None

    @property
    def key(self) -> FactKey:
        return atom(self.subject), atom(self.dimension)


@dataclass(frozen=True, slots=True)
class Goal:
    name: str
    weight: float
    target: str | None = None


@dataclass(slots=True)
class CharacterMind:
    name: str
    traits: dict[str, float] = field(default_factory=dict)
    beliefs: dict[FactKey, Belief] = field(default_factory=dict)
    memories: list[Memory] = field(default_factory=list)
    goals: list[Goal] = field(default_factory=list)
    secrets: set[FactKey] = field(default_factory=set)
    relationships: dict[str, dict[str, float]] = field(default_factory=dict)

    def believe(
        self,
        subject: str,
        dimension: str,
        value: str | None,
        *,
        confidence: float = 1.0,
        source_event: int | None = None,
    ) -> None:
        belief = Belief(subject, dimension, value, confidence, source_event)
        self.beliefs[belief.key] = belief

    def belief(self, subject: str, dimension: str) -> Belief | None:
        return self.beliefs.get((atom(subject), atom(dimension)))

    def knows(self, subject: str, dimension: str, value: str | None = None) -> bool:
        found = self.belief(subject, dimension)
        if found is None or found.confidence < 0.999:
            return False
        if value is None:
            return found.value is not None
        return atom(found.value or "") == atom(value)

    def remember(
        self, event: Event, summary: str, *, salience: float = 0.5, private: bool = False, kind: str = "event"
    ) -> None:
        self.memories.append(Memory(event.seq, summary, salience, private, atom(kind)))

    def relation(self, other: str, dimension: str, default: float = 0.0) -> float:
        return self.relationships.get(atom(other), {}).get(atom(dimension), default)

    def adjust_relation(self, other: str, dimension: str, delta: float) -> float:
        bucket = self.relationships.setdefault(atom(other), {})
        key = atom(dimension)
        bucket[key] = max(-1.0, min(1.0, bucket.get(key, 0.0) + delta))
        return bucket[key]


@dataclass(frozen=True, slots=True)
class ResponsePlan:
    speaker: str
    speech_act: str
    intent: str
    content: tuple[tuple[str, str], ...] = ()
    emotion: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    style: tuple[str, ...] = ()
    confidence: float = 1.0

    @classmethod
    def build(
        cls,
        speaker: str,
        speech_act: str,
        intent: str,
        *,
        content: Mapping[str, str] | None = None,
        emotion: tuple[str, ...] = (),
        actions: tuple[str, ...] = (),
        style: tuple[str, ...] = (),
        confidence: float = 1.0,
    ) -> "ResponsePlan":
        return cls(
            atom(speaker),
            atom(speech_act),
            atom(intent),
            tuple(sorted((atom(k), str(v)) for k, v in (content or {}).items())),
            tuple(atom(x) for x in emotion),
            actions,
            tuple(atom(x) for x in style),
            confidence,
        )

    def value(self, key: str) -> str | None:
        return dict(self.content).get(atom(key))
