from __future__ import annotations

from dataclasses import dataclass

from .vm_delta import RelationDelta
from .vm_kernel import Instruction, Program, K_REQUIRE, K_SET, K_SHIFT
from .vm_ledger import atom


@dataclass(frozen=True, slots=True)
class ReturnObligation:
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
    """Order-independent collection of grounded world changes.

    This is the general execution boundary. It has no lexical event class and no
    primary/secondary transition. A gift, sale, movement, or unseen composition is
    simply a set of relation deltas plus optional explicit side effects.
    """

    deltas: tuple[RelationDelta, ...]
    return_obligations: tuple[ReturnObligation, ...] = ()

    @classmethod
    def build(
        cls,
        deltas,
        *,
        return_obligations=(),
    ) -> "SemanticPatch":
        ds = tuple(deltas)
        obs = tuple(return_obligations)
        if not ds and not obs:
            raise ValueError("semantic patch cannot be empty")

        # The same subject/relation may be changed at most once in one atomic patch.
        occupied: set[tuple[str, str]] = set()
        for delta in ds:
            if not isinstance(delta, RelationDelta):
                raise TypeError("all deltas must be RelationDelta")
            for relation in delta.relations:
                key = (delta.subject, relation)
                if key in occupied:
                    raise ValueError(f"duplicate transition for {key}")
                occupied.add(key)
        for obligation in obs:
            if not isinstance(obligation, ReturnObligation):
                raise TypeError("all return obligations must be ReturnObligation")

        # Storage order is not semantic. Canonicalize immediately.
        ds = tuple(sorted(ds, key=lambda d: d.transition_key()))
        obs = tuple(sorted(obs, key=lambda o: o.key()))
        return cls(ds, obs)

    def transition_fingerprint(self) -> tuple:
        return (
            tuple(delta.transition_key() for delta in self.deltas),
            tuple(obligation.key() for obligation in self.return_obligations),
        )

    def transition_equivalent(self, other: "SemanticPatch") -> bool:
        return self.transition_fingerprint() == other.transition_fingerprint()


def compose_semantic_patches(*patches: SemanticPatch) -> SemanticPatch:
    """Union already-understood meanings with exact conflict detection.

    Composition is deterministic cognitive work. Identical facts contributed by
    multiple chunks are deduplicated; incompatible transitions for the same
    subject/relation are rejected instead of being silently ordered or overwritten.
    """

    if not patches:
        raise ValueError("compose_semantic_patches requires at least one patch")

    transitions: dict[tuple[str, str], tuple[str, str]] = {}
    obligations: dict[tuple[str, str, str], ReturnObligation] = {}

    for patch in patches:
        if not isinstance(patch, SemanticPatch):
            raise TypeError("all composed values must be SemanticPatch")
        for delta in patch.deltas:
            for relation in delta.relations:
                key = (delta.subject, relation)
                effect = (delta.source, delta.destination)
                previous = transitions.get(key)
                if previous is not None and previous != effect:
                    raise ValueError(
                        f"conflicting transitions for {key}: {previous} versus {effect}"
                    )
                transitions[key] = effect
        for obligation in patch.return_obligations:
            obligations[obligation.key()] = obligation

    # Recombine relation cells that share subject/source/destination so the result
    # stays compact without reintroducing event-class assumptions.
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for (subject, relation), (source, destination) in transitions.items():
        grouped.setdefault((subject, source, destination), []).append(relation)

    deltas = tuple(
        RelationDelta.build(subject, source, destination, tuple(relations))
        for (subject, source, destination), relations in grouped.items()
    )
    return SemanticPatch.build(
        deltas,
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
    for obligation in patch.return_obligations:
        key = f"obligation:return:{obligation.subject}:{obligation.holder}:{obligation.return_to}"
        instructions.append(Instruction.make(K_SET, key, "status", "active"))
    return Program.build(instructions, label="semantic_patch")
