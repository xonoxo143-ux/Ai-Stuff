from __future__ import annotations

import json
from dataclasses import dataclass

from .meaning import Meaning
from .schema import SemanticValidationError, validate_meaning


class ExternalMeaningError(ValueError):
    """External parser output could not be accepted as SemZip meaning."""


@dataclass(frozen=True, slots=True)
class ValidatedMeaning:
    meaning: Meaning
    source: str


class SemanticJSONBridge:
    """Trust boundary between learned/external parsers and SemZip.

    External systems may propose SemZip JSON, but proposals do not become trusted
    semantic objects until they deserialize and pass recursive schema validation.
    """

    def decode(self, text: str, *, source: str = "external") -> ValidatedMeaning:
        try:
            meaning = Meaning.from_json(text)
            validate_meaning(meaning)
        except (ValueError, TypeError, json.JSONDecodeError, SemanticValidationError) as exc:
            raise ExternalMeaningError(str(exc)) from exc
        return ValidatedMeaning(meaning=meaning, source=source)
