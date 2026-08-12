from __future__ import annotations

from dataclasses import dataclass

from .vm_delta import RelationDelta
from .vm_effects import ClearEffect, SemanticEffect, SetEffect, ShiftEffect, effect_key
from .vm_kernel import Instruction, Program, K_CLEAR, K_SET, K_SHIFT
from .vm_ledger import atom


# Compatibility names used by earlier experiments. The canonical algebraic objects
# are SetEffect / ClearEffect in vm_effects.
StateAssignment = SetEffect
StateClear = ClearEffect


@dataclass(frozen=True, slots=True)
class ReturnObligation:
    """Compatibility semantic-library effect for early loan experiments.

    It is not a kernel instruction. A later consolidation may lower this entirely
    into ordinary state effects once the obligation schema is generalized.
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
    """Canonical unordered semantic transformation.

    The semantic truth is a set of atomic state effects. Grouping multiple dimensions
    into one RelationDelta is retained only as a compatibility/compression view.
    """

    effects: tuple[SemanticEffect, ...] = ()
    return_obligations: tuple[ReturnObligation, ...] = ()

    @classmethod
    def empty(cls) -> "SemanticPatch":
        """Algebraic identity for parallel composition: an explicit no-change patch."""
        return cls()

    @property
    def is_empty(self) -> bool:
        return not self.effects and not self.return_obligations

    @classmethod
    def build(
        cls,
        deltas=(),
        *,
        effects=(),
        assignments=(),
        clears=(),
        return_obligations=(),
    ) -> "SemanticPatch":
        atomic: list[SemanticEffect] = []
        for delta in tuple(deltas):
            if not isinstance(delta, RelationDelta):
                raise TypeError("all deltas must be RelationDelta")
            for dimension in delta.relations:
                atomic.append(
                    ShiftEffect.build(
                        delta.subject,
                        dimension,
                        delta.source,
                        delta.destination,
                    )
                )
        atomic.extend(tuple(effects))
        atomic.extend(tuple(assignments))
        atomic.extend(tuple(clears))
        obligations = tuple(return_obligations)
        if not atomic and not obligations:
            raise ValueError("semantic patch cannot be empty; use SemanticPatch.empty() explicitly")

        occupied: dict[tuple[str, str], SemanticEffect] = {}
        canonical: list[SemanticEffect] = []
        for effect in atomic:
            if not isinstance(effect, (ShiftEffect, SetEffect, ClearEffect)):
                raise TypeError("all patch effects must be ShiftEffect, SetEffect, or ClearEffect")
            previous = occupied.get(effect.cell)
            if previous is not None:
                if previous == effect:
                    raise ValueError(f"duplicate semantic effect for {effect.cell}")
                raise ValueError(
                    f"conflicting semantic effects for {effect.cell}: {previous} versus {effect}"
                )
            occupied[effect.cell] = effect
            canonical.append(effect)

        for obligation in obligations:
            if not isinstance(obligation, ReturnObligation):
                raise TypeError("all return obligations must be ReturnObligation")

        return cls(
            tuple(sorted(canonical, key=effect_key)),
            tuple(sorted(obligations, key=lambda item: item.key())),
        )

    @property
    def deltas(self) -> tuple[RelationDelta, ...]:
        """Compatibility view grouping atomic shifts with identical endpoints."""
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for effect in self.effects:
            if isinstance(effect, ShiftEffect):
                grouped.setdefault(
                    (effect.subject, effect.source, effect.destination), []
                ).append(effect.dimension)
        return tuple(
            sorted(
                (
                    RelationDelta.build(subject, source, destination, tuple(dimensions))
                    for (subject, source, destination), dimensions in grouped.items()
                ),
                key=lambda delta: delta.transition_key(),
            )
        )

    @property
    def assignments(self) -> tuple[SetEffect, ...]:
        return tuple(effect for effect in self.effects if isinstance(effect, SetEffect))

    @property
    def clears(self) -> tuple[ClearEffect, ...]:
        return tuple(effect for effect in self.effects if isinstance(effect, ClearEffect))

    def transition_fingerprint(self) -> tuple:
        return (
            tuple(effect_key(effect) for effect in self.effects),
            tuple(obligation.key() for obligation in self.return_obligations),
        )

    def transition_equivalent(self, other: "SemanticPatch") -> bool:
        return self.transition_fingerprint() == other.transition_fingerprint()


def compose_semantic_patches(*patches: SemanticPatch) -> SemanticPatch:
    """Partial commutative/idempotent composition of simultaneous meanings."""

    if not patches:
        return SemanticPatch.empty()

    occupied: dict[tuple[str, str], SemanticEffect] = {}
    obligations: dict[tuple[str, str, str], ReturnObligation] = {}
    for patch in patches:
        if not isinstance(patch, SemanticPatch):
            raise TypeError("all composed values must be SemanticPatch")
        for effect in patch.effects:
            previous = occupied.get(effect.cell)
            if previous is not None and previous != effect:
                raise ValueError(
                    f"conflicting semantic effects for {effect.cell}: {previous} versus {effect}"
                )
            occupied[effect.cell] = effect
        for obligation in patch.return_obligations:
            obligations[obligation.key()] = obligation

    if not occupied and not obligations:
        return SemanticPatch.empty()
    return SemanticPatch.build(
        effects=tuple(occupied.values()),
        return_obligations=tuple(obligations.values()),
    )


def compile_semantic_patch(patch: SemanticPatch) -> Program:
    """Lower atomic semantic effects to the tiny kernel.

    ShiftEffect is already a partial transformation: its `source` is the required
    previous value. K_SHIFT enforces that domain condition, so emitting K_REQUIRE for
    the same cell would only duplicate information and computation.
    """
    instructions: list[Instruction] = []
    for effect in patch.effects:
        if isinstance(effect, ShiftEffect):
            instructions.append(
                Instruction.make(
                    K_SHIFT,
                    effect.subject,
                    effect.dimension,
                    effect.source,
                    effect.destination,
                )
            )
        elif isinstance(effect, SetEffect):
            instructions.append(Instruction.make(K_SET, effect.subject, effect.dimension, effect.value))
        elif isinstance(effect, ClearEffect):
            instructions.append(Instruction.make(K_CLEAR, effect.subject, effect.dimension))
    for obligation in patch.return_obligations:
        key = f"obligation:return:{obligation.subject}:{obligation.holder}:{obligation.return_to}"
        instructions.append(Instruction.make(K_SET, key, "status", "active"))
    return Program.build(instructions, label="semantic_patch")
