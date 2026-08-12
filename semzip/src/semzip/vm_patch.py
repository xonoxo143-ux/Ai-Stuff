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
    """Semantic-library adapter, not a core effect kind.

    A return obligation expands into ordinary state assignments on an obligation
    entity. The adapter remains so old loan experiments can construct/read the same
    concept without making LOAN/OBLIGATION part of the semantic algebra or VM kernel.
    """

    subject: str
    holder: str
    return_to: str

    @classmethod
    def build(cls, subject: str, holder: str, return_to: str) -> "ReturnObligation":
        return cls(atom(subject), atom(holder), atom(return_to))

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.holder, self.return_to)

    @property
    def entity_id(self) -> str:
        # Preserve the historical ID so existing world-state regressions remain valid.
        return f"obligation:return:{self.subject}:{self.holder}:{self.return_to}"

    def effects(self) -> tuple[SetEffect, ...]:
        entity = self.entity_id
        return (
            SetEffect.build(entity, "kind", "return"),
            SetEffect.build(entity, "subject", self.subject),
            SetEffect.build(entity, "holder", self.holder),
            SetEffect.build(entity, "return_to", self.return_to),
            SetEffect.build(entity, "status", "active"),
        )


def _extract_return_obligations(effects: tuple[SemanticEffect, ...]) -> tuple[ReturnObligation, ...]:
    values: dict[str, dict[str, str]] = {}
    for effect in effects:
        if isinstance(effect, SetEffect):
            values.setdefault(effect.subject, {})[effect.dimension] = effect.value
    found = []
    for fields in values.values():
        if fields.get("kind") != "return" or fields.get("status") != "active":
            continue
        if not {"subject", "holder", "return_to"}.issubset(fields):
            continue
        found.append(
            ReturnObligation.build(
                fields["subject"],
                fields["holder"],
                fields["return_to"],
            )
        )
    return tuple(sorted(set(found), key=lambda item: item.key()))


@dataclass(frozen=True, slots=True)
class SemanticPatch:
    """Canonical unordered semantic transformation.

    The semantic truth is **only** a set of atomic Set/Shift/Clear effects. Grouped
    `RelationDelta` objects and domain concepts such as return obligations are derived
    compatibility/library views.
    """

    effects: tuple[SemanticEffect, ...] = ()

    @classmethod
    def empty(cls) -> "SemanticPatch":
        """Algebraic identity for parallel composition: an explicit no-change patch."""
        return cls()

    @property
    def is_empty(self) -> bool:
        return not self.effects

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
        for obligation in tuple(return_obligations):
            if not isinstance(obligation, ReturnObligation):
                raise TypeError("all return obligations must be ReturnObligation")
            atomic.extend(obligation.effects())

        if not atomic:
            raise ValueError("semantic patch cannot be empty; use SemanticPatch.empty() explicitly")

        occupied: dict[tuple[str, str], SemanticEffect] = {}
        canonical: list[SemanticEffect] = []
        for effect in atomic:
            if not isinstance(effect, (ShiftEffect, SetEffect, ClearEffect)):
                raise TypeError("all patch effects must be ShiftEffect, SetEffect, or ClearEffect")
            previous = occupied.get(effect.cell)
            if previous is not None:
                if previous == effect:
                    # Adapter expansion may encounter an already-explicit identical fact;
                    # semantic sets are idempotent, so keep one canonical copy.
                    continue
                raise ValueError(
                    f"conflicting semantic effects for {effect.cell}: {previous} versus {effect}"
                )
            occupied[effect.cell] = effect
            canonical.append(effect)

        return cls(tuple(sorted(canonical, key=effect_key)))

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

    @property
    def return_obligations(self) -> tuple[ReturnObligation, ...]:
        """Derived semantic-library view over ordinary state effects."""
        return _extract_return_obligations(self.effects)

    def transition_fingerprint(self) -> tuple:
        return tuple(effect_key(effect) for effect in self.effects)

    def transition_equivalent(self, other: "SemanticPatch") -> bool:
        return self.transition_fingerprint() == other.transition_fingerprint()


def compose_semantic_patches(*patches: SemanticPatch) -> SemanticPatch:
    """Partial commutative/idempotent composition of simultaneous meanings."""

    if not patches:
        return SemanticPatch.empty()

    occupied: dict[tuple[str, str], SemanticEffect] = {}
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

    if not occupied:
        return SemanticPatch.empty()
    return SemanticPatch.build(effects=tuple(occupied.values()))


def compile_semantic_patch(patch: SemanticPatch) -> Program:
    """Lower atomic semantic effects to the tiny kernel."""
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
    return Program.build(instructions, label="semantic_patch")
