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
    "SemanticGraph",
    "SemanticValidationError",
    "SemanticVM",
    "SemZipCodec",
    "UnsupportedMeaningError",
    "UnsupportedStorySentence",
    "VMExecutionError",
    "WorldModel",
    "WorldQueryEngine",
    "validate_meaning",
]
__version__ = "0.4.0"
