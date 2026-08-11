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
        return cls(atom(subject), atom(source), atom(destination), normalized)


@dataclass(frozen=True, slots=True)
class SemanticDeltaFrame:
    """Language-neutral world-change frame consumed by SemVM.

    The frame deliberately has no GIVE/LEND/SELL opcode. Complex events are
    compositions of one or more relation deltas plus optional side effects.
    """

    primary: RelationDelta
    secondary: RelationDelta | None = None
    return_obligation: bool = False


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
