from __future__ import annotations

from dataclasses import dataclass

from .vm_effects import ShiftEffect
from .vm_kernel import Instruction, Program, K_REQUIRE
from .vm_ledger import atom
from .vm_patch import SemanticPatch, compile_semantic_patch, compose_semantic_patches


@dataclass(frozen=True, slots=True)
class StateConstraint:
    """Required state that is not itself the changed value of a ShiftEffect."""

    subject: str
    dimension: str
    value: str

    @classmethod
    def build(cls, subject: str, dimension: str, value: str) -> "StateConstraint":
        return cls(atom(subject), atom(dimension), atom(value))

    @property
    def cell(self) -> tuple[str, str]:
        return (self.subject, self.dimension)

    def key(self) -> tuple[str, str, str]:
        return (self.subject, self.dimension, self.value)


@dataclass(frozen=True, slots=True)
class SemanticTransform:
    """A partial world-state transformation: constraints define its domain."""

    patch: SemanticPatch
    constraints: tuple[StateConstraint, ...] = ()

    @classmethod
    def build(cls, patch: SemanticPatch, *, constraints=()) -> "SemanticTransform":
        if not isinstance(patch, SemanticPatch):
            raise TypeError("transform patch must be SemanticPatch")

        shifts = {
            effect.cell: effect
            for effect in patch.effects
            if isinstance(effect, ShiftEffect)
        }
        seen: dict[tuple[str, str], StateConstraint] = {}
        kept: list[StateConstraint] = []
        for constraint in tuple(constraints):
            if not isinstance(constraint, StateConstraint):
                raise TypeError("all transform constraints must be StateConstraint")
            previous = seen.get(constraint.cell)
            if previous is not None and previous != constraint:
                raise ValueError(
                    f"incompatible constraints for {constraint.cell}: "
                    f"{previous.value!r} versus {constraint.value!r}"
                )
            seen[constraint.cell] = constraint

            shift = shifts.get(constraint.cell)
            if shift is not None:
                if constraint.value != shift.source:
                    raise ValueError(
                        f"constraint {constraint.key()} contradicts shift source {shift.source!r}"
                    )
                # ShiftEffect already carries this exact domain condition.
                continue
            kept.append(constraint)

        return cls(patch, tuple(sorted(set(kept), key=lambda item: item.key())))

    @classmethod
    def identity(cls) -> "SemanticTransform":
        return cls(SemanticPatch.empty(), ())

    def fingerprint(self) -> tuple:
        return (
            tuple(item.key() for item in self.constraints),
            self.patch.transition_fingerprint(),
        )


def parallel_transforms(*transforms: SemanticTransform) -> SemanticTransform:
    if not transforms:
        return SemanticTransform.identity()
    patch = compose_semantic_patches(*(item.patch for item in transforms))
    constraints = tuple(
        constraint
        for item in transforms
        for constraint in item.constraints
    )
    return SemanticTransform.build(patch, constraints=constraints)


def compile_semantic_transform(transform: SemanticTransform) -> Program:
    instructions = [
        Instruction.make(K_REQUIRE, item.subject, item.dimension, item.value)
        for item in transform.constraints
    ]
    instructions.extend(compile_semantic_patch(transform.patch).instructions)
    return Program.build(instructions, label="semantic_transform")
