from __future__ import annotations

from dataclasses import dataclass

from .vm_kernel import Program
from .vm_patch import SemanticPatch, compile_semantic_patch


@dataclass(frozen=True, slots=True)
class SemanticSequence:
    """Ordered semantic transformations.

    Parallel/conjunctive effects belong inside one SemanticPatch. Changes whose
    ordering matters belong in separate sequence steps. The explicit empty sequence
    is the identity element for sequential composition.
    """

    steps: tuple[SemanticPatch, ...]

    @classmethod
    def empty(cls) -> "SemanticSequence":
        return cls(())

    @property
    def is_empty(self) -> bool:
        return not self.steps

    @classmethod
    def build(cls, steps) -> "SemanticSequence":
        normalized = tuple(steps)
        if not normalized:
            raise ValueError("semantic sequence cannot be empty; use SemanticSequence.empty() explicitly")
        if any(not isinstance(step, SemanticPatch) for step in normalized):
            raise TypeError("all semantic sequence steps must be SemanticPatch")
        return cls(normalized)

    def fingerprint(self) -> tuple:
        return tuple(step.transition_fingerprint() for step in self.steps)

    def append(self, patch: SemanticPatch) -> "SemanticSequence":
        if not isinstance(patch, SemanticPatch):
            raise TypeError("sequence step must be SemanticPatch")
        if patch.is_empty:
            return self
        return SemanticSequence(self.steps + (patch,))

    def extend(self, other: "SemanticSequence") -> "SemanticSequence":
        if not isinstance(other, SemanticSequence):
            raise TypeError("can only extend with SemanticSequence")
        return SemanticSequence(self.steps + other.steps)


def compile_semantic_sequence(sequence: SemanticSequence) -> Program:
    """Compile ordered patches into one transactional VM program."""

    instructions = []
    for step in sequence.steps:
        instructions.extend(compile_semantic_patch(step).instructions)
    return Program.build(tuple(instructions), label="semantic_sequence")
