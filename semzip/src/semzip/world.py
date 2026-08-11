from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .meaning import Meaning
from .schema import validate_meaning


@dataclass(frozen=True, slots=True)
class Fact:
    subject: str
    dimension: str
    value: str
    asserted_at: int
    provenance: str = "asserted"


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    subject: str
    dimension: str
    before: str | None
    after: str
    at: int
    actor: str | None = None


@dataclass(frozen=True, slots=True)
class BeliefRecord:
    holder: str
    content: Meaning
    at: int


@dataclass(slots=True)
class Ontology:
    parents: dict[str, set[str]] = field(default_factory=dict)

    def add_is_a(self, child: str, parent: str) -> None:
        child, parent = _atom(child), _atom(parent)
        self.parents.setdefault(child, set()).add(parent)

    def is_a(self, child: str, ancestor: str) -> bool:
        child, ancestor = _atom(child), _atom(ancestor)
        if child == ancestor:
            return True
        seen: set[str] = set()
        stack = list(self.parents.get(child, ()))
        while stack:
            node = stack.pop()
            if node == ancestor:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(self.parents.get(node, ()))
        return False


class WorldModel:
    """Tiny deterministic world state derived from semantic meanings."""

    def __init__(self) -> None:
        self._clock = 0
        self._facts: dict[tuple[str, str], Fact] = {}
        self._fact_timeline: dict[tuple[str, str], list[Fact]] = {}
        self._history: list[ChangeRecord] = []
        self._beliefs: dict[str, list[BeliefRecord]] = {}
        self._modal: list[tuple[int, Meaning]] = []
        self._relations: list[tuple[int, Meaning]] = []
        # Missing key = no epistemic claim represented.
        # Present with None = explicitly represented ignorance.
        self._knowledge: dict[tuple[str, str, str], str | None] = {}
        self.ontology = Ontology()

    @property
    def clock(self) -> int:
        return self._clock

    @property
    def history(self) -> tuple[ChangeRecord, ...]:
        return tuple(self._history)

    def fact(self, subject: str, dimension: str) -> str | None:
        found = self._facts.get((_atom(subject), _atom(dimension)))
        return found.value if found else None

    def previous(self, subject: str, dimension: str) -> str | None:
        subject, dimension = _atom(subject), _atom(dimension)
        for change in reversed(self._history):
            if change.subject == subject and change.dimension == dimension:
                return change.before
        return None

    def fact_at(self, subject: str, dimension: str, at: int) -> str | None:
        key = (_atom(subject), _atom(dimension))
        value: str | None = None
        for fact in self._fact_timeline.get(key, ()):
            if fact.asserted_at > at:
                break
            value = fact.value
        return value

    @property
    def modal_statements(self) -> tuple[Meaning, ...]:
        return tuple(meaning for _, meaning in self._modal)

    @property
    def causal_relations(self) -> tuple[Meaning, ...]:
        return tuple(meaning for _, meaning in self._relations)

    def apply(self, meaning: Meaning) -> None:
        validate_meaning(meaning)
        self._clock += 1
        self._apply(meaning)

    def apply_many(self, meanings: Iterable[Meaning]) -> None:
        for meaning in meanings:
            self.apply(meaning)

    def _apply(self, meaning: Meaning) -> None:
        op = meaning.operator
        if op == "STATE":
            self._set(
                meaning.atom("SUBJECT"),
                meaning.atom("DIMENSION"),
                meaning.atom("VALUE"),
            )
            return

        if op == "CHANGE":
            subject = meaning.atom("SUBJECT")
            dimension = meaning.atom("DIMENSION")
            after = meaning.atom("AFTER")
            before = meaning.optional_atom("BEFORE")
            actor = meaning.optional_atom("ACTOR")
            current = self.fact(subject, dimension)
            if before is not None and current is not None and current != before:
                raise ValueError(
                    f"CHANGE expected {subject}.{dimension}={before!r}, found {current!r}"
                )
            before_value = current if current is not None else before
            self._history.append(
                ChangeRecord(subject, dimension, before_value, after, self._clock, actor)
            )
            self._set(subject, dimension, after)
            return

        if op == "BELIEVE":
            holder = meaning.atom("HOLDER")
            content = meaning.expression("CONTENT")
            self._beliefs.setdefault(holder, []).append(
                BeliefRecord(holder, content, self._clock)
            )
            return

        if op == "KNOW_VALUE":
            holder = meaning.atom("HOLDER")
            subject = meaning.atom("SUBJECT")
            dimension = meaning.atom("DIMENSION")
            value = meaning.optional_atom("VALUE")
            if value is None:
                value = self.fact(subject, dimension)
            self._knowledge[(holder, subject, dimension)] = value
            return

        if op == "NOT":
            content = meaning.expression("CONTENT")
            if content.operator == "KNOW_VALUE":
                key = (
                    content.atom("HOLDER"),
                    content.atom("SUBJECT"),
                    content.atom("DIMENSION"),
                )
                self._knowledge[key] = None
                return
            raise ValueError(f"world update for NOT({content.operator}) is not defined")

        if op == "IS_A":
            self.ontology.add_is_a(
                meaning.atom("CHILD"),
                meaning.atom("PARENT"),
            )
            return

        if op == "EXCHANGE":
            goods = meaning.expression("GOODS_TRANSFER")
            payment = meaning.expression("PAYMENT_TRANSFER")
            self._preflight_change(goods)
            self._preflight_change(payment)
            self._apply(goods)
            self._apply(payment)
            return

        if op == "LOAN":
            transfer = meaning.expression("TRANSFER")
            obligation = meaning.expression("RETURN_OBLIGATION")
            self._preflight_change(transfer)
            self._apply(transfer)
            self._modal.append((self._clock, obligation))
            return

        if op == "OBLIGATION":
            self._modal.append((self._clock, meaning))
            return

        if op in {
            "POSSIBLE", "PROBABLE", "NECESSARY", "INTENDED",
            "ATTEMPTED", "COUNTERFACTUAL", "CONDITIONAL",
        }:
            self._modal.append((self._clock, meaning))
            return

        if op in {"CAUSE", "ENABLE", "PREVENT", "CORRELATE", "PRECEDE"}:
            self._relations.append((self._clock, meaning))
            return

        raise ValueError(f"world update for {op!r} is not defined")

    def _preflight_change(self, meaning: Meaning) -> None:
        if meaning.operator != "CHANGE":
            raise ValueError(f"expected CHANGE, got {meaning.operator!r}")
        subject = meaning.atom("SUBJECT")
        dimension = meaning.atom("DIMENSION")
        before = meaning.optional_atom("BEFORE")
        current = self.fact(subject, dimension)
        if before is not None and current is not None and current != before:
            raise ValueError(
                f"CHANGE expected {subject}.{dimension}={before!r}, found {current!r}"
            )

    def _set(self, subject: str, dimension: str, value: str) -> None:
        subject, dimension, value = _atom(subject), _atom(dimension), _atom(value)
        fact = Fact(subject, dimension, value, self._clock)
        key = (subject, dimension)
        self._facts[key] = fact
        self._fact_timeline.setdefault(key, []).append(fact)

    def entities_of_type(self, type_name: str) -> tuple[str, ...]:
        target = _atom(type_name)
        entities = [
            subject
            for (subject, dimension), fact in self._facts.items()
            if dimension == "type" and fact.value == target
        ]
        return tuple(sorted(entities))

    def entity_is_a(self, subject: str, ancestor: str) -> bool | None:
        entity_type = self.fact(subject, "type")
        if entity_type is None:
            return None
        return self.ontology.is_a(entity_type, ancestor)

    def beliefs(self, holder: str) -> tuple[Meaning, ...]:
        records = self._beliefs.get(_atom(holder), ())
        return tuple(record.content for record in records)

    def latest_belief(self, holder: str, subject: str, dimension: str) -> str | None:
        holder, subject, dimension = _atom(holder), _atom(subject), _atom(dimension)
        for record in reversed(self._beliefs.get(holder, ())):
            content = record.content
            if (
                content.operator == "STATE"
                and content.atom("SUBJECT") == subject
                and content.atom("DIMENSION") == dimension
            ):
                return content.atom("VALUE")
        return None

    def belief_is_true(self, holder: str, subject: str, dimension: str) -> bool | None:
        believed = self.latest_belief(holder, subject, dimension)
        actual = self.fact(subject, dimension)
        if believed is None or actual is None:
            return None
        return believed == actual

    def knows_value(self, holder: str, subject: str, dimension: str) -> bool | None:
        key = (_atom(holder), _atom(subject), _atom(dimension))
        if key not in self._knowledge:
            return None
        stored = self._knowledge[key]
        if stored is None:
            return False
        return stored == self.fact(subject, dimension)


def _atom(value: str) -> str:
    return "_".join(value.strip().casefold().split())
