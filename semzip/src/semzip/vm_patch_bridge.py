from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .vm_delta import RelationDelta
from .vm_ledger import atom
from .vm_patch import ReturnObligation, SemanticPatch
from .vm_relations import DEFAULT_RELATION_REGISTRY, RelationRegistry


class PatchPredictionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RelationCellPrediction:
    """One compiler-proposed grounded relation transition using closed IDs/pointers."""

    relation_id: int
    subject: int
    source: int
    destination: int


@dataclass(frozen=True, slots=True)
class ReturnObligationPrediction:
    subject: int
    holder: int
    return_to: int


@dataclass(frozen=True, slots=True)
class PatchPrediction:
    """Closed compiler output contract for an arbitrary-size SemanticPatch."""

    relation_registry_signature: str
    cells: tuple[RelationCellPrediction, ...]
    return_obligations: tuple[ReturnObligationPrediction, ...] = ()


def _entity_table(entities: Sequence[str] | Mapping[int, str]) -> tuple[str, ...]:
    if isinstance(entities, Mapping):
        if not entities:
            raise PatchPredictionError("entity table cannot be empty")
        expected = set(range(len(entities)))
        if set(entities) != expected:
            raise PatchPredictionError("mapping entity table must use contiguous 0..N-1 keys")
        return tuple(atom(entities[i]) for i in range(len(entities)))
    table = tuple(atom(x) for x in entities)
    if not table:
        raise PatchPredictionError("entity table cannot be empty")
    return table


def _pointer(pointer: int, table: tuple[str, ...], *, field: str) -> str:
    if isinstance(pointer, bool) or not isinstance(pointer, int):
        raise PatchPredictionError(f"{field} must be an integer entity pointer")
    if not 0 <= pointer < len(table):
        raise PatchPredictionError(
            f"{field} pointer {pointer} outside entity table of size {len(table)}"
        )
    return table[pointer]


def resolve_patch_prediction(
    prediction: PatchPrediction,
    entities: Sequence[str] | Mapping[int, str],
    *,
    registry: RelationRegistry = DEFAULT_RELATION_REGISTRY,
) -> SemanticPatch:
    """Validate a neural/compiler proposal and resolve it into executable semantics.

    The registry signature is part of the trust boundary: a compiler trained against
    a different relation-ID mapping cannot silently reinterpret its outputs.
    """

    expected_signature = registry.signature()
    if prediction.relation_registry_signature != expected_signature:
        raise PatchPredictionError(
            "relation registry signature mismatch: compiler/runtime vocabularies differ"
        )
    table = _entity_table(entities)
    if not prediction.cells and not prediction.return_obligations:
        raise PatchPredictionError("predicted patch cannot be empty")

    # First validate individual relation cells and enforce one transition per
    # subject/relation. Identical duplicates are harmless and collapse; conflicting
    # duplicates are rejected.
    effects: dict[tuple[str, str], tuple[str, str]] = {}
    for index, cell in enumerate(prediction.cells):
        if isinstance(cell.relation_id, bool) or not isinstance(cell.relation_id, int):
            raise PatchPredictionError(f"cells[{index}].relation_id must be an integer")
        try:
            relation = registry.resolve_id(cell.relation_id).name
        except KeyError as exc:
            raise PatchPredictionError(f"cells[{index}] uses unknown relation id {cell.relation_id}") from exc
        subject = _pointer(cell.subject, table, field=f"cells[{index}].subject")
        source = _pointer(cell.source, table, field=f"cells[{index}].source")
        destination = _pointer(cell.destination, table, field=f"cells[{index}].destination")
        key = (subject, relation)
        effect = (source, destination)
        previous = effects.get(key)
        if previous is not None and previous != effect:
            raise PatchPredictionError(
                f"conflicting predictions for {key}: {previous} versus {effect}"
            )
        effects[key] = effect

    # Compact relation cells that share the same grounded transition.
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for (subject, relation), (source, destination) in effects.items():
        grouped.setdefault((subject, source, destination), []).append(relation)
    deltas = tuple(
        RelationDelta.build(
            subject,
            source,
            destination,
            tuple(relations),
            registry=registry,
        )
        for (subject, source, destination), relations in grouped.items()
    )

    obligations: list[ReturnObligation] = []
    seen_obligations: set[tuple[str, str, str]] = set()
    for index, item in enumerate(prediction.return_obligations):
        obligation = ReturnObligation.build(
            _pointer(item.subject, table, field=f"return_obligations[{index}].subject"),
            _pointer(item.holder, table, field=f"return_obligations[{index}].holder"),
            _pointer(item.return_to, table, field=f"return_obligations[{index}].return_to"),
        )
        if obligation.key() not in seen_obligations:
            obligations.append(obligation)
            seen_obligations.add(obligation.key())

    return SemanticPatch.build(deltas, return_obligations=tuple(obligations))
