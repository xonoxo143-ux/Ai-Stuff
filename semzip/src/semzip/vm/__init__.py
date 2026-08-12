"""Canonical Semantic VM API.

The top-level :mod:`semzip` package still exposes the preserved v0.3 semantic-codec
interfaces. New Semantic VM work should import from :mod:`semzip.vm` so experiments do
not have to know which historical ``vm_*`` module currently owns a concept.
"""

from ..vm_actions import ActionSchema, Parameter
from ..vm_algebra import (
    NonInvertibleMeaningError,
    equivalent_under_projection,
    inverse_patch,
    parallel,
    project_patch,
    sequential,
)
from ..vm_effects import ClearEffect, SemanticEffect, SetEffect, ShiftEffect
from ..vm_kernel import (
    Instruction,
    Program,
    SemanticVM,
    VMExecutionError,
    K_CLEAR,
    K_REQUIRE,
    K_SET,
    K_SHIFT,
)
from ..vm_ledger import EventLedger, LedgerEvent
from ..vm_patch import SemanticPatch, compile_semantic_patch, compose_semantic_patches
from ..vm_plan import Goal, PlanResult, PlanStep, SymbolicPlanner
from ..vm_relations import (
    DEFAULT_DIMENSION_REGISTRY,
    DimensionRegistry,
    DimensionSpec,
)
from ..vm_sequence import SemanticSequence, compile_semantic_sequence
from ..vm_state import StateSnapshot
from ..vm_transform import (
    SemanticTransform,
    StateConstraint,
    compile_semantic_transform,
    parallel_transforms,
)

__all__ = [
    "ActionSchema",
    "ClearEffect",
    "DEFAULT_DIMENSION_REGISTRY",
    "DimensionRegistry",
    "DimensionSpec",
    "EventLedger",
    "Goal",
    "Instruction",
    "K_CLEAR",
    "K_REQUIRE",
    "K_SET",
    "K_SHIFT",
    "LedgerEvent",
    "NonInvertibleMeaningError",
    "Parameter",
    "PlanResult",
    "PlanStep",
    "Program",
    "SemanticEffect",
    "SemanticPatch",
    "SemanticSequence",
    "SemanticTransform",
    "SemanticVM",
    "SetEffect",
    "ShiftEffect",
    "StateConstraint",
    "StateSnapshot",
    "SymbolicPlanner",
    "VMExecutionError",
    "compile_semantic_patch",
    "compile_semantic_sequence",
    "compile_semantic_transform",
    "compose_semantic_patches",
    "equivalent_under_projection",
    "inverse_patch",
    "parallel",
    "parallel_transforms",
    "project_patch",
    "sequential",
]
