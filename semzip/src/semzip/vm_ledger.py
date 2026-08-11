from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping
import sys


def atom(value: str) -> str:
    value = "_".join(value.strip().casefold().split())
    if not value:
        raise ValueError("semantic atom cannot be empty")
    return sys.intern(value)


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    seq: int
    kind: str
    subject: str
    relation: str
    before: str | None
    after: str | None
    actor: str | None = None
    confidence: float = 1.0
    provenance: str = "asserted"
    branch: str = "main"
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class Branch:
    name: str
    parent: str | None
    fork_seq: int


class EventLedger:
    """Append-only semantic event ledger with branch-aware projections."""

    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._branches: dict[str, Branch] = {"main": Branch("main", None, 0)}
        self._heads: dict[str, dict[tuple[str, str], str]] = {"main": {}}
        self._seq = 0

    @property
    def events(self) -> tuple[LedgerEvent, ...]:
        return tuple(self._events)

    @property
    def branches(self) -> tuple[str, ...]:
        return tuple(sorted(self._branches))

    @property
    def clock(self) -> int:
        return self._seq

    def fork(self, name: str, *, parent: str = "main", at: int | None = None) -> None:
        name, parent = atom(name), atom(parent)
        if name in self._branches:
            raise ValueError(f"branch {name!r} already exists")
        if parent not in self._branches:
            raise ValueError(f"unknown parent branch {parent!r}")
        if at is None:
            at = self._seq
        if at < 0 or at > self._seq:
            raise ValueError("fork point is outside ledger history")
        self._branches[name] = Branch(name, parent, at)
        self._heads[name] = self.project(branch=parent, at=at)

    def append_state(
        self,
        subject: str,
        relation: str,
        value: str,
        *,
        branch: str = "main",
        actor: str | None = None,
        confidence: float = 1.0,
        provenance: str = "asserted",
        metadata: Mapping[str, str] | None = None,
    ) -> LedgerEvent:
        subject, relation, value, branch = map(atom, (subject, relation, value, branch))
        self._ensure_branch(branch)
        before = self.current(subject, relation, branch=branch)
        return self._append(
            "state", subject, relation, before, value,
            branch=branch, actor=actor, confidence=confidence,
            provenance=provenance, metadata=metadata,
        )

    def transition(
        self,
        subject: str,
        relation: str,
        before: str | None,
        after: str,
        *,
        branch: str = "main",
        actor: str | None = None,
        confidence: float = 1.0,
        provenance: str = "executed",
        metadata: Mapping[str, str] | None = None,
    ) -> LedgerEvent:
        subject, relation, after, branch = map(atom, (subject, relation, after, branch))
        before = atom(before) if before is not None else None
        self._ensure_branch(branch)
        current = self.current(subject, relation, branch=branch)
        if before is not None and current != before:
            raise ValueError(
                f"transition expected {subject}.{relation}={before!r}, found {current!r}"
            )
        return self._append(
            "transition", subject, relation, current, after,
            branch=branch, actor=actor, confidence=confidence,
            provenance=provenance, metadata=metadata,
        )

    def retract(
        self,
        subject: str,
        relation: str,
        *,
        branch: str = "main",
        actor: str | None = None,
        provenance: str = "executed",
    ) -> LedgerEvent:
        subject, relation, branch = map(atom, (subject, relation, branch))
        current = self.current(subject, relation, branch=branch)
        return self._append(
            "retract", subject, relation, current, None,
            branch=branch, actor=actor, provenance=provenance,
        )

    def observe(
        self,
        subject: str,
        relation: str,
        value: str,
        *,
        branch: str = "main",
        confidence: float = 1.0,
        provenance: str = "perception",
        metadata: Mapping[str, str] | None = None,
    ) -> LedgerEvent:
        """Record evidence without promoting it into accepted world state."""
        subject, relation, value, branch = map(atom, (subject, relation, value, branch))
        self._ensure_branch(branch)
        return self._append(
            "observation", subject, relation,
            self.current(subject, relation, branch=branch), value,
            branch=branch, confidence=confidence,
            provenance=provenance, metadata=metadata,
        )

    def observations(
        self, subject: str, relation: str, *, branch: str = "main"
    ) -> tuple[LedgerEvent, ...]:
        subject, relation, branch = atom(subject), atom(relation), atom(branch)
        visible = self._visible_events(branch, None)
        return tuple(
            e for e in visible
            if e.kind == "observation" and e.subject == subject and e.relation == relation
        )

    def best_observation(
        self, subject: str, relation: str, *, branch: str = "main"
    ) -> LedgerEvent | None:
        evidence = self.observations(subject, relation, branch=branch)
        if not evidence:
            return None
        return max(evidence, key=lambda e: (e.confidence, e.seq))

    def accept_observation(self, event: LedgerEvent, *, branch: str | None = None) -> LedgerEvent:
        if event.kind != "observation" or event.after is None:
            raise ValueError("only concrete observation events can be accepted")
        target_branch = atom(branch or event.branch)
        return self.append_state(
            event.subject, event.relation, event.after,
            branch=target_branch, confidence=event.confidence,
            provenance=f"accepted:{event.provenance}",
            metadata={"source_event": str(event.seq)},
        )

    def current(self, subject: str, relation: str, *, branch: str = "main") -> str | None:
        branch = atom(branch)
        self._ensure_branch(branch)
        return self._heads[branch].get((atom(subject), atom(relation)))

    def current_at(
        self, subject: str, relation: str, at: int, *, branch: str = "main"
    ) -> str | None:
        return self.project(branch=branch, at=at).get((atom(subject), atom(relation)))

    def project(self, *, branch: str = "main", at: int | None = None) -> dict[tuple[str, str], str]:
        branch = atom(branch)
        self._ensure_branch(branch)
        if at is None:
            return dict(self._heads[branch])
        visible = self._visible_events(branch, at)
        state: dict[tuple[str, str], str] = {}
        for event in visible:
            if event.kind == "observation":
                continue
            key = (event.subject, event.relation)
            if event.after is None:
                state.pop(key, None)
            else:
                state[key] = event.after
        return state

    def clone(self) -> "EventLedger":
        other = EventLedger()
        other._events = list(self._events)
        other._branches = dict(self._branches)
        other._heads = {name: dict(state) for name, state in self._heads.items()}
        other._seq = self._seq
        return other

    def replace_with(self, other: "EventLedger") -> None:
        self._events = list(other._events)
        self._branches = dict(other._branches)
        self._heads = {name: dict(state) for name, state in other._heads.items()}
        self._seq = other._seq

    def _append(
        self,
        kind: str,
        subject: str,
        relation: str,
        before: str | None,
        after: str | None,
        *,
        branch: str,
        actor: str | None = None,
        confidence: float = 1.0,
        provenance: str = "asserted",
        metadata: Mapping[str, str] | None = None,
    ) -> LedgerEvent:
        self._seq += 1
        event = LedgerEvent(
            seq=self._seq,
            kind=atom(kind),
            subject=atom(subject),
            relation=atom(relation),
            before=atom(before) if before is not None else None,
            after=atom(after) if after is not None else None,
            actor=atom(actor) if actor is not None else None,
            confidence=float(confidence),
            provenance=atom(provenance),
            branch=atom(branch),
            metadata=tuple(sorted((atom(k), atom(v)) for k, v in (metadata or {}).items())),
        )
        self._events.append(event)
        if event.kind != "observation":
            key = (event.subject, event.relation)
            if event.after is None:
                self._heads[event.branch].pop(key, None)
            else:
                self._heads[event.branch][key] = event.after
        return event

    def _ensure_branch(self, branch: str) -> None:
        if branch not in self._branches:
            raise ValueError(f"unknown branch {branch!r}")

    def _visible_events(self, branch: str, at: int | None) -> list[LedgerEvent]:
        if at is None:
            at = self._seq
        if at < 0:
            raise ValueError("projection time cannot be negative")
        chain: list[tuple[str, int]] = []
        current = self._branches[branch]
        cutoff = at
        while True:
            chain.append((current.name, cutoff))
            if current.parent is None:
                break
            cutoff = min(cutoff, current.fork_seq)
            current = self._branches[current.parent]
        chain.reverse()
        visible: list[LedgerEvent] = []
        for branch_name, cutoff in chain:
            visible.extend(
                e for e in self._events if e.branch == branch_name and e.seq <= cutoff
            )
        visible.sort(key=lambda e: e.seq)
        return visible
