from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .vm_kernel import Program
from .vm_ledger import EventLedger


class EquivalenceLevel(IntEnum):
    SURFACE = 0
    PRAGMATIC = 1
    PROPOSITION = 2
    TRANSITION = 3
    KERNEL = 4


@dataclass(frozen=True, slots=True)
class RichExpression:
    """Thin envelope preserving information above executable semantics."""

    program: Program
    proposition: str | None = None
    perspective: str | None = None
    pragmatic_force: str | None = None
    surface: str | None = None
    provenance: str | None = None


def transition_signature(program: Program, seed: EventLedger) -> tuple[tuple[str, str, str], ...]:
    from .vm_kernel import SemanticVM

    vm = SemanticVM(seed.clone())
    before = vm.ledger.project()
    vm.execute(program)
    after = vm.ledger.project()
    delta: list[tuple[str, str, str]] = []
    keys = sorted(set(before) | set(after))
    for subject, relation in keys:
        b, a = before.get((subject, relation)), after.get((subject, relation))
        if b == a:
            continue
        delta.append((subject, relation, f"{b}->{a}"))
    return tuple(delta)


def equivalent(
    left: RichExpression,
    right: RichExpression,
    *,
    level: EquivalenceLevel,
    seed: EventLedger | None = None,
) -> bool:
    if level == EquivalenceLevel.SURFACE:
        return left.surface == right.surface
    if level == EquivalenceLevel.PRAGMATIC:
        return (
            left.pragmatic_force,
            left.perspective,
            left.proposition,
        ) == (
            right.pragmatic_force,
            right.perspective,
            right.proposition,
        )
    if level == EquivalenceLevel.PROPOSITION:
        return left.proposition == right.proposition
    if level == EquivalenceLevel.KERNEL:
        return left.program.instructions == right.program.instructions
    if seed is None:
        raise ValueError("transition equivalence requires a seed world")
    return transition_signature(left.program, seed) == transition_signature(right.program, seed)
