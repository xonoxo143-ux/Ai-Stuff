"""SemZip: preserved semantic codec plus the experimental Semantic VM.

The historical top-level exports remain for v0.3/v0.4 compatibility. New Semantic VM
code should prefer ``semzip.vm`` for the canonical algebra-facing API.
"""

from .codec import SemZipCodec, UnsupportedMeaningError
from .meaning import Meaning
from .model import SemanticGraph
from .query import QueryAnswer, WorldQueryEngine
from .schema import SemanticValidationError, validate_meaning
from .story import (
    AmbiguousReferenceError,
    MiniWorldInterpreter,
    UnsupportedStorySentence,
)
from .world import Ontology, WorldModel
from .vm_delta import RelationDelta, SemanticDeltaFrame, compile_delta_frame
from .vm_delta_bridge import (
    DeltaPrediction,
    DeltaPredictionError,
    resolve_delta_prediction,
)
from .vm_kernel import Instruction, Program, SemanticVM, VMExecutionError
from .vm_ledger import EventLedger, LedgerEvent
from .vm_minds import MindSpace
from .vm_patch import (
    ReturnObligation,
    SemanticPatch,
    compile_semantic_patch,
    compose_semantic_patches,
)
from .vm_patch_bridge import (
    PatchPrediction,
    PatchPredictionError,
    RelationCellPrediction,
    ReturnObligationPrediction,
    resolve_patch_prediction,
)
from .vm_relations import DEFAULT_RELATION_REGISTRY, RelationRegistry, RelationSpec
from .vm_semantic_parse import (
    AtomicSemanticCandidate,
    SemanticParse,
    candidate_splits,
    parse_semantics,
)

__all__ = [
    "AmbiguousReferenceError",
    "AtomicSemanticCandidate",
    "DEFAULT_RELATION_REGISTRY",
    "DeltaPrediction",
    "DeltaPredictionError",
    "EventLedger",
    "Instruction",
    "LedgerEvent",
    "Meaning",
    "MindSpace",
    "MiniWorldInterpreter",
    "Ontology",
    "PatchPrediction",
    "PatchPredictionError",
    "Program",
    "QueryAnswer",
    "RelationCellPrediction",
    "RelationDelta",
    "RelationRegistry",
    "RelationSpec",
    "ReturnObligation",
    "ReturnObligationPrediction",
    "SemanticDeltaFrame",
    "SemanticGraph",
    "SemanticParse",
    "SemanticPatch",
    "SemanticValidationError",
    "SemanticVM",
    "SemZipCodec",
    "UnsupportedMeaningError",
    "UnsupportedStorySentence",
    "VMExecutionError",
    "WorldModel",
    "WorldQueryEngine",
    "candidate_splits",
    "compile_delta_frame",
    "compile_semantic_patch",
    "compose_semantic_patches",
    "parse_semantics",
    "resolve_delta_prediction",
    "resolve_patch_prediction",
    "validate_meaning",
]
__version__ = "0.5.0"
