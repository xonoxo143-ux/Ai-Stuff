from __future__ import annotations

from collections.abc import Iterable

from .vm_effects import ClearEffect, SetEffect, ShiftEffect
from .vm_patch import SemanticPatch, compose_semantic_patches
from .vm_sequence import SemanticSequence


class NonInvertibleMeaningError(ValueError):
    pass


def parallel(*patches: SemanticPatch) -> SemanticPatch:
    """Commutative/idempotent composition where simultaneous effects are compatible."""
    return compose_semantic_patches(*patches)


def sequential(*parts: SemanticPatch | SemanticSequence) -> SemanticSequence:
    """Associative ordered composition; nested sequences flatten exactly."""
    steps: list[SemanticPatch] = []
    for part in parts:
        if isinstance(part, SemanticPatch):
            if not part.is_empty:
                steps.append(part)
        elif isinstance(part, SemanticSequence):
            steps.extend(step for step in part.steps if not step.is_empty)
        else:
            raise TypeError("sequential parts must be SemanticPatch or SemanticSequence")
    return SemanticSequence(tuple(steps)) if steps else SemanticSequence.empty()


def inverse_patch(patch: SemanticPatch) -> SemanticPatch:
    """Invert a patch only when every effect is intrinsically reversible.

    SHIFT carries the previous value and therefore has a local inverse. SET and CLEAR
    do not retain enough information to invert without consulting history, and opaque
    side effects are not assumed reversible.
    """
    if patch.return_obligations:
        raise NonInvertibleMeaningError("patch contains semantic-library side effects")
    inverse = []
    for effect in patch.effects:
        if isinstance(effect, ShiftEffect):
            inverse.append(effect.inverse())
        elif isinstance(effect, (SetEffect, ClearEffect)):
            raise NonInvertibleMeaningError(
                f"{type(effect).__name__} has no intrinsic inverse without prior state"
            )
    return SemanticPatch.build(effects=tuple(inverse)) if inverse else SemanticPatch.empty()


def project_patch(
    patch: SemanticPatch,
    *,
    dimensions: Iterable[str] | None = None,
    subjects: Iterable[str] | None = None,
) -> SemanticPatch:
    """Project a meaning onto selected state dimensions/subjects.

    Projection is deliberately lower-level than proposition/pragmatic equivalence:
    two meanings can differ globally while being equivalent for a selected view.
    """
    dimension_set = None if dimensions is None else {str(value).casefold() for value in dimensions}
    subject_set = None if subjects is None else {str(value).casefold() for value in subjects}
    selected = tuple(
        effect
        for effect in patch.effects
        if (dimension_set is None or effect.dimension in dimension_set)
        and (subject_set is None or effect.subject in subject_set)
    )
    # Opaque side effects are excluded from a state-dimension projection. They remain
    # available at the full semantic level instead of being silently equated here.
    return SemanticPatch.build(effects=selected) if selected else SemanticPatch.empty()


def equivalent_under_projection(
    left: SemanticPatch,
    right: SemanticPatch,
    *,
    dimensions: Iterable[str] | None = None,
    subjects: Iterable[str] | None = None,
) -> bool:
    return project_patch(left, dimensions=dimensions, subjects=subjects).transition_equivalent(
        project_patch(right, dimensions=dimensions, subjects=subjects)
    )
