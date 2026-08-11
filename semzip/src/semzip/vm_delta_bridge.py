from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .vm_delta import RelationDelta, SemanticDeltaFrame, SUPPORTED_RELATIONS
from .vm_ledger import atom


MAX_ENTITY_SLOTS = 4
# Neural pointer heads use 0..3 for entities and 4 as an explicit NONE class.
NONE_POINTER = MAX_ENTITY_SLOTS


class DeltaPredictionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeltaPrediction:
    """Closed neural output contract for one grounded semantic event.

    Pointers index a caller-supplied entity table. Relations are fixed-order
    booleans corresponding to SUPPORTED_RELATIONS. There are no free-form
    relation names, entity strings, action labels, or VM opcodes here.
    """

    primary_subject: int
    primary_source: int
    primary_destination: int
    primary_relations: tuple[bool, bool, bool]
    secondary_present: bool = False
    secondary_subject: int = NONE_POINTER
    secondary_source: int = NONE_POINTER
    secondary_destination: int = NONE_POINTER
    secondary_relations: tuple[bool, bool, bool] = (False, False, False)
    return_obligation: bool = False


def _validate_pointer(pointer: int, slot_count: int, *, field: str, allow_none: bool = False) -> None:
    if isinstance(pointer, bool) or not isinstance(pointer, int):
        raise DeltaPredictionError(f"{field} must be an integer pointer")
    if allow_none and pointer == NONE_POINTER:
        return
    if not 0 <= pointer < slot_count:
        raise DeltaPredictionError(
            f"{field} pointer {pointer} outside entity table of size {slot_count}"
        )


def _relation_names(bits: Sequence[bool], *, field: str) -> tuple[str, ...]:
    if len(bits) != len(SUPPORTED_RELATIONS):
        raise DeltaPredictionError(
            f"{field} must contain exactly {len(SUPPORTED_RELATIONS)} relation bits"
        )
    normalized: list[bool] = []
    for bit in bits:
        if not isinstance(bit, bool):
            raise DeltaPredictionError(f"{field} values must be bools")
        normalized.append(bit)
    return tuple(
        relation for relation, enabled in zip(SUPPORTED_RELATIONS, normalized) if enabled
    )


def resolve_delta_prediction(
    prediction: DeltaPrediction,
    entities: Sequence[str] | Mapping[int, str],
) -> SemanticDeltaFrame:
    """Validate and resolve a bounded model prediction into a VM delta frame."""

    if isinstance(entities, Mapping):
        if not entities:
            raise DeltaPredictionError("entity table cannot be empty")
        expected = set(range(len(entities)))
        if set(entities) != expected:
            raise DeltaPredictionError("mapping entity table must use contiguous 0..N-1 keys")
        table = tuple(atom(entities[i]) for i in range(len(entities)))
    else:
        table = tuple(atom(x) for x in entities)
        if not table:
            raise DeltaPredictionError("entity table cannot be empty")

    if len(table) > MAX_ENTITY_SLOTS:
        raise DeltaPredictionError(
            f"entity table has {len(table)} entries; model contract supports at most {MAX_ENTITY_SLOTS}"
        )

    n = len(table)
    _validate_pointer(prediction.primary_subject, n, field="primary_subject")
    _validate_pointer(prediction.primary_source, n, field="primary_source")
    _validate_pointer(prediction.primary_destination, n, field="primary_destination")
    primary_relations = _relation_names(
        prediction.primary_relations, field="primary_relations"
    )
    if not primary_relations:
        raise DeltaPredictionError("primary delta must change at least one relation")

    primary = RelationDelta.build(
        table[prediction.primary_subject],
        table[prediction.primary_source],
        table[prediction.primary_destination],
        primary_relations,
    )

    secondary = None
    if prediction.secondary_present:
        _validate_pointer(prediction.secondary_subject, n, field="secondary_subject")
        _validate_pointer(prediction.secondary_source, n, field="secondary_source")
        _validate_pointer(prediction.secondary_destination, n, field="secondary_destination")
        secondary_relations = _relation_names(
            prediction.secondary_relations, field="secondary_relations"
        )
        if not secondary_relations:
            raise DeltaPredictionError(
                "secondary_present requires at least one secondary relation"
            )
        secondary = RelationDelta.build(
            table[prediction.secondary_subject],
            table[prediction.secondary_source],
            table[prediction.secondary_destination],
            secondary_relations,
        )
    else:
        for field, value in (
            ("secondary_subject", prediction.secondary_subject),
            ("secondary_source", prediction.secondary_source),
            ("secondary_destination", prediction.secondary_destination),
        ):
            _validate_pointer(value, n, field=field, allow_none=True)
            if value != NONE_POINTER:
                raise DeltaPredictionError(
                    f"{field} must be NONE_POINTER when secondary_present is false"
                )
        if any(prediction.secondary_relations):
            raise DeltaPredictionError(
                "secondary relations must be empty when secondary_present is false"
            )

    if prediction.return_obligation and "possessor" not in primary_relations:
        raise DeltaPredictionError(
            "return obligation requires a primary possession transition"
        )

    return SemanticDeltaFrame(
        primary=primary,
        secondary=secondary,
        return_obligation=prediction.return_obligation,
    )
