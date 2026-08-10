"""SemZip: experimental semantic codec."""

from .codec import SemZipCodec, UnsupportedMeaningError
from .model import SemanticGraph

__all__ = ["SemZipCodec", "SemanticGraph", "UnsupportedMeaningError"]
__version__ = "0.1.0"
