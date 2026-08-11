from __future__ import annotations

from dataclasses import dataclass

from .vm_ledger import EventLedger, atom


@dataclass(frozen=True, slots=True)
class BeliefAnswer:
    value: str | None
    represented: bool
    agrees_with_reality: bool | None


class MindSpace:
    """Agent-specific world projections implemented as ledger branches."""

    def __init__(self, ledger: EventLedger) -> None:
        self.ledger = ledger
        self._branches: dict[str, str] = {}

    def register(self, holder: str, *, at: int | None = None) -> str:
        holder = atom(holder)
        if holder in self._branches:
            return self._branches[holder]
        branch = f"mind:{holder}"
        self.ledger.fork(branch, parent="main", at=at)
        self._branches[holder] = branch
        return branch

    def set_belief(
        self,
        holder: str,
        subject: str,
        relation: str,
        value: str,
        *,
        provenance: str = "belief_update",
    ) -> None:
        holder = atom(holder)
        branch = self._branches.get(holder) or self.register(holder)
        self.ledger.append_state(
            subject, relation, value, branch=branch, provenance=provenance
        )

    def belief(self, holder: str, subject: str, relation: str) -> BeliefAnswer:
        holder = atom(holder)
        branch = self._branches.get(holder)
        if branch is None:
            return BeliefAnswer(None, False, None)
        believed = self.ledger.current(subject, relation, branch=branch)
        if believed is None:
            return BeliefAnswer(None, False, None)
        actual = self.ledger.current(subject, relation, branch="main")
        agrees = None if actual is None else believed == actual
        return BeliefAnswer(believed, True, agrees)
