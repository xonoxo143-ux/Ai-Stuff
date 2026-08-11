from __future__ import annotations

from dataclasses import dataclass

from .vm_kernel import Instruction, Program, K_REQUIRE, K_SET, K_SHIFT
from .vm_ledger import atom


SUPPORTED_RELATIONS = ("owner", "possessor", "location")


@dataclass(frozen=True, slots=True)
class RelationDelta:
    """One entity changing one or more grounded world relations."""

    subject: str
    source: str
    destination: str
    relations: tuple[str, ...]

    @classmethod
    def build(
        cls,
        subject: str,
        source: str,
        destination: str,
        relations: tuple[str, ...] | list[str],
    ) -> "RelationDelta":
        normalized = tuple(atom(x) for x in relations)
        if not normalized:
            raise ValueError("relation delta must change at least one relation")
        if len(set(normalized)) != len(normalized):
            raise ValueError("relation delta contains duplicate relations")
        unknown = tuple(x for x in normalized if x not in SUPPORTED_RELATIONS)
        if unknown:
            raise ValueError(f"unsupported grounded relations: {unknown}")
        # Relation ordering is declarative, not procedural.
        ordered = tuple(sorted(normalized, key=SUPPORTED_RELATIONS.index))
        return cls(atom(subject), atom(source), atom(destination), ordered)

    def transition_key(self) -> tuple[str, str, str, tuple[str, ...]]:
        return (self.subject, self.source, self.destination, self.relations)


@dataclass(frozen=True, slots=True)
class SemanticDeltaFrame:
    """Language-neutral world-change frame consumed by SemVM.

    The frame deliberately has no GIVE/LEND/SELL opcode. Complex events are
    compositions of one or more relation deltas plus optional side effects.
    """

    primary: RelationDelta
    secondary: RelationDelta | None = None
    return_obligation: bool = False

    def transition_fingerprint(self) -> tuple:
        """Canonical effect-level identity, independent of harmless delta ordering.

        A return obligation is anchored to the primary possession transition, so
        frames carrying one retain primary/secondary order. Pure multi-delta world
        transitions such as reciprocal exchange are canonicalized as an unordered
        set of relation deltas.
        """

        if self.secondary is None:
            deltas = (self.primary.transition_key(),)
        elif self.return_obligation:
            deltas = (self.primary.transition_key(), self.secondary.transition_key())
        else:
            deltas = tuple(sorted((
                self.primary.transition_key(),
                self.secondary.transition_key(),
            )))
        return (deltas, bool(self.return_obligation))

    def transition_equivalent(self, other: "SemanticDeltaFrame") -> bool:
        return self.transition_fingerprint() == other.transition_fingerprint()


def compile_delta_frame(frame: SemanticDeltaFrame) -> Program:
    instructions: list[Instruction] = []

    def add_delta(delta: RelationDelta) -> None:
        for relation in delta.relations:
            instructions.append(Instruction.make(K_REQUIRE, delta.subject, relation, delta.source))
            instructions.append(
                Instruction.make(K_SHIFT, delta.subject, relation, delta.source, delta.destination)
            )

    add_delta(frame.primary)
    if frame.secondary is not None:
        add_delta(frame.secondary)

    if frame.return_obligation:
        if "possessor" not in frame.primary.relations:
            raise ValueError("return obligation requires a primary possession transition")
        obligation = (
            f"obligation:return:{frame.primary.subject}:"
            f"{frame.primary.destination}:{frame.primary.source}"
        )
        instructions.append(Instruction.make(K_SET, obligation, "status", "active"))

    return Program.build(instructions, label="semantic_delta")
