"""SemZip: semantic codec prototype plus experimental Semantic VM."""

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
from .vm_patch import ReturnObligation, SemanticPatch, compile_semantic_patch
from .vm_relations import DEFAULT_RELATION_REGISTRY, RelationRegistry, RelationSpec

__all__ = [
    "AmbiguousReferenceError",
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
    "Program",
    "QueryAnswer",
    "RelationDelta",
    "RelationRegistry",
    "RelationSpec",
    "ReturnObligation",
    "SemanticDeltaFrame",
    "SemanticGraph",
    "SemanticPatch",
    "SemanticValidationError",
    "SemanticVM",
    "SemZipCodec",
    "UnsupportedMeaningError",
    "UnsupportedStorySentence",
    "VMExecutionError",
    "WorldModel",
    "WorldQueryEngine",
    "compile_delta_frame",
    "compile_semantic_patch",
    "resolve_delta_prediction",
    "validate_meaning",
]
__version__ = "0.4.0"
