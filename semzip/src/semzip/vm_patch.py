from __future__ import annotations

from dataclasses import dataclass

from .vm_delta import RelationDelta
from .vm_kernel import Instruction, Program, K_CLEAR, K_REQUIRE, K_SET, K_SHIFT
from .vm_ledger import atom


@dataclass(frozen=True, slots=True)
class StateAssignment:
    """Assign one semantic state dimension without asserting its previous value."""

    subject: str
    dimension: str
    value: str

    @classmethod
    def build(cls, subject: str, dimension: str, value: str) -> "StateAssignment":
        return cls(atom(subject), atom(dimension), atom(value))

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.dimension, self.value)


@dataclass(frozen=True, slots=True)
class StateClear:
    """Remove one semantic state dimension from accepted state."""

    subject: str
    dimension: str

    @classmethod
    def build(cls, subject: str, dimension: str) -> "StateClear":
        return cls(atom(subject), atom(dimension))

    def key(self) -> tuple[str, str]:
        return (self.subject, self.dimension)


@dataclass(frozen=True, slots=True)
class ReturnObligation:
    """Compatibility semantic-library effect for the early loan experiments.

    This is deliberately not a VM opcode. It lowers to ordinary SET state when a
    patch is compiled and can later be replaced by a fully generic obligation schema.
    """

    subject: str
    holder: str
    return_to: str

    @classmethod
    def build(cls, subject: str, holder: str, return_to: str) -> "ReturnObligation":
        return cls(atom(subject), atom(holder), atom(return_to))

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.holder, self.return_to)


@dataclass(frozen=True, slots=True)
class SemanticPatch:
    """Order-independent collection of grounded semantic state effects.

    `RelationDelta` remains a compatibility/compact view for one or more dimensions
    sharing a source/destination. Static assignments and clears are first-class patch
    effects as well. Storage order is never semantic.
    """

    deltas: tuple[RelationDelta, ...] = ()
    assignments: tuple[StateAssignment, ...] = ()
    clears: tuple[StateClear, ...] = ()
    return_obligations: tuple[ReturnObligation, ...] = ()

    @classmethod
    def build(
        cls,
        deltas=(),
        *,
        assignments=(),
        clears=(),
        return_obligations=(),
    ) -> "SemanticPatch":
        ds = tuple(deltas)
        sets = tuple(assignments)
        removals = tuple(clears)
        obs = tuple(return_obligations)
        if not ds and not sets and not removals and not obs:
            raise ValueError("semantic patch cannot be empty")

        occupied: dict[tuple[str, str], tuple[str, tuple]] = {}

        def claim(key: tuple[str, str], kind: str, payload: tuple) -> None:
            previous = occupied.get(key)
            if previous is not None:
                if previous == (kind, payload):
                    raise ValueError(f"duplicate semantic effect for {key}")
                raise ValueError(
                    f"conflicting semantic effects for {key}: {previous} versus {(kind, payload)}"
                )
            occupied[key] = (kind, payload)

        for delta in ds:
            if not isinstance(delta, RelationDelta):
                raise TypeError("all deltas must be RelationDelta")
            for relation in delta.relations:
                claim(
                    (delta.subject, relation),
                    "shift",
                    (delta.source, delta.destination),
                )

        for item in sets:
            if not isinstance(item, StateAssignment):
                raise TypeError("all assignments must be StateAssignment")
            claim((item.subject, item.dimension), "set", (item.value,))

        for item in removals:
            if not isinstance(item, StateClear):
                raise TypeError("all clears must be StateClear")
            claim((item.subject, item.dimension), "clear", ())

        for obligation in obs:
            if not isinstance(obligation, ReturnObligation):
                raise TypeError("all return obligations must be ReturnObligation")

        ds = tuple(sorted(ds, key=lambda d: d.transition_key()))
        sets = tuple(sorted(sets, key=lambda item: item.key()))
        removals = tuple(sorted(removals, key=lambda item: item.key()))
        obs = tuple(sorted(obs, key=lambda o: o.key()))
        return cls(ds, sets, removals, obs)

    def transition_fingerprint(self) -> tuple:
        return (
            tuple(delta.transition_key() for delta in self.deltas),
            tuple(item.key() for item in self.assignments),
            tuple(item.key() for item in self.clears),
            tuple(obligation.key() for obligation in self.return_obligations),
        )

    def transition_equivalent(self, other: "SemanticPatch") -> bool:
        return self.transition_fingerprint() == other.transition_fingerprint()


def compose_semantic_patches(*patches: SemanticPatch) -> SemanticPatch:
    """Union already-understood simultaneous meanings with exact conflict checks."""

    if not patches:
        raise ValueError("compose_semantic_patches requires at least one patch")

    transitions: dict[tuple[str, str], tuple[str, str]] = {}
    assignments: dict[tuple[str, str], StateAssignment] = {}
    clears: dict[tuple[str, str], StateClear] = {}
    obligations: dict[tuple[str, str, str], ReturnObligation] = {}
    kinds: dict[tuple[str, str], str] = {}

    def require_kind(key: tuple[str, str], kind: str) -> None:
        previous = kinds.get(key)
        if previous is not None and previous != kind:
            raise ValueError(f"conflicting effect types for {key}: {previous} versus {kind}")
        kinds[key] = kind

    for patch in patches:
        if not isinstance(patch, SemanticPatch):
            raise TypeError("all composed values must be SemanticPatch")
        for delta in patch.deltas:
            for relation in delta.relations:
                key = (delta.subject, relation)
                require_kind(key, "shift")
                effect = (delta.source, delta.destination)
                previous = transitions.get(key)
                if previous is not None and previous != effect:
                    raise ValueError(
                        f"conflicting transitions for {key}: {previous} versus {effect}"
                    )
                transitions[key] = effect
        for item in patch.assignments:
            key = (item.subject, item.dimension)
            require_kind(key, "set")
            previous = assignments.get(key)
            if previous is not None and previous != item:
                raise ValueError(f"conflicting assignments for {key}")
            assignments[key] = item
        for item in patch.clears:
            key = (item.subject, item.dimension)
            require_kind(key, "clear")
            clears[key] = item
        for obligation in patch.return_obligations:
            obligations[obligation.key()] = obligation

    # Compact compatibility view: regroup shifts that share subject/source/destination.
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for (subject, relation), (source, destination) in transitions.items():
        grouped.setdefault((subject, source, destination), []).append(relation)

    deltas = tuple(
        RelationDelta.build(subject, source, destination, tuple(relations))
        for (subject, source, destination), relations in grouped.items()
    )
    return SemanticPatch.build(
        deltas,
        assignments=tuple(assignments.values()),
        clears=tuple(clears.values()),
        return_obligations=tuple(obligations.values()),
    )


def compile_semantic_patch(patch: SemanticPatch) -> Program:
    instructions: list[Instruction] = []
    for delta in patch.deltas:
        for relation in delta.relations:
            instructions.append(Instruction.make(K_REQUIRE, delta.subject, relation, delta.source))
            instructions.append(
                Instruction.make(K_SHIFT, delta.subject, relation, delta.source, delta.destination)
            )
    for item in patch.assignments:
        instructions.append(Instruction.make(K_SET, item.subject, item.dimension, item.value))
    for item in patch.clears:
        instructions.append(Instruction.make(K_CLEAR, item.subject, item.dimension))
    for obligation in patch.return_obligations:
        key = f"obligation:return:{obligation.subject}:{obligation.holder}:{obligation.return_to}"
        instructions.append(Instruction.make(K_SET, key, "status", "active"))
    return Program.build(instructions, label="semantic_patch")
