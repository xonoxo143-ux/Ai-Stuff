"""SemZip: experimental semantic codec and world substrate."""

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

__all__ = [
    "AmbiguousReferenceError",
    "Meaning",
    "MiniWorldInterpreter",
    "Ontology",
    "QueryAnswer",
    "SemanticGraph",
    "SemanticValidationError",
    "SemZipCodec",
    "UnsupportedMeaningError",
    "UnsupportedStorySentence",
    "WorldModel",
    "WorldQueryEngine",
    "validate_meaning",
]
__version__ = "0.3.0"
