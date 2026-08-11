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
from .vm_kernel import Instruction, Program, SemanticVM, VMExecutionError
from .vm_ledger import EventLedger, LedgerEvent
from .vm_minds import MindSpace

__all__ = [
    "AmbiguousReferenceError",
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
    "SemanticDeltaFrame",
    "SemanticGraph",
    "SemanticValidationError",
    "SemanticVM",
    "SemZipCodec",
    "UnsupportedMeaningError",
    "UnsupportedStorySentence",
    "VMExecutionError",
    "WorldModel",
    "WorldQueryEngine",
    "compile_delta_frame",
    "validate_meaning",
]
__version__ = "0.4.0"
