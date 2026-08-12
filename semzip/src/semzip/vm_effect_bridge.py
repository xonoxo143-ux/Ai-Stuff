from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .vm_delta import RelationDelta
from .vm_ledger import atom
from .vm_patch import ReturnObligation, SemanticPatch, StateAssignment, StateClear
from .vm_relations import DEFAULT_RELATION_REGISTRY, RelationRegistry


class EffectPredictionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TransitionPrediction:
    dimension_id: int
    subject: int
    source: int
    destination: int


@dataclass(frozen=True, slots=True)
class AssignmentPrediction:
    dimension_id: int
    subject: int
    value: int


@dataclass(frozen=True, slots=True)
class ClearPrediction:
    dimension_id: int
    subject: int


@dataclass(frozen=True, slots=True)
class ReturnEffectPrediction:
    subject: int
    holder: int
    return_to: int


@dataclass(frozen=True, slots=True)
class SemanticEffectPrediction:
    registry_signature: str
    transitions: tuple[TransitionPrediction, ...] = ()
    assignments: tuple[AssignmentPrediction, ...] = ()
    clears: tuple[ClearPrediction, ...] = ()
    returns: tuple[ReturnEffectPrediction, ...] = ()


def _table(values: Sequence[str] | Mapping[int, str], *, label: str) -> tuple[str, ...]:
    if isinstance(values, Mapping):
        if not values:
            raise EffectPredictionError(f"{label} table cannot be empty")
        expected = set(range(len(values)))
        if set(values) != expected:
            raise EffectPredictionError(f"{label} mapping must use contiguous 0..N-1 keys")
        return tuple(atom(values[i]) for i in range(len(values)))
    result = tuple(atom(value) for value in values)
    if not result:
        raise EffectPredictionError(f"{label} table cannot be empty")
    return result


def _pointer(index: int, table: tuple[str, ...], *, field: str) -> str:
    if isinstance(index, bool) or not isinstance(index, int):
        raise EffectPredictionError(f"{field} must be an integer pointer")
    if not 0 <= index < len(table):
        raise EffectPredictionError(
            f"{field} pointer {index} outside table of size {len(table)}"
        )
    return table[index]


def _dimension(dimension_id: int, registry: RelationRegistry, *, field: str) -> str:
    if isinstance(dimension_id, bool) or not isinstance(dimension_id, int):
        raise EffectPredictionError(f"{field} must be an integer dimension id")
    try:
        return registry.resolve_id(dimension_id).name
    except KeyError as exc:
        raise EffectPredictionError(f"{field} uses unknown dimension id {dimension_id}") from exc


def resolve_effect_prediction(
    prediction: SemanticEffectPrediction,
    entities: Sequence[str] | Mapping[int, str],
    *,
    atoms: Sequence[str] | Mapping[int, str] | None = None,
    registry: RelationRegistry = DEFAULT_RELATION_REGISTRY,
) -> SemanticPatch:
    """Resolve a closed compiler proposal into a validated SemanticPatch.

    `entities` contains referents that may occupy subject/source/destination roles.
    `atoms` is an optional closed value table for static assignments. When omitted,
    the entity table doubles as the value table; no free-form value generation occurs.
    """

    if prediction.registry_signature != registry.signature():
        raise EffectPredictionError("semantic dimension registry signature mismatch")

    entity_table = _table(entities, label="entity")
    atom_table = entity_table if atoms is None else _table(atoms, label="atom")

    grouped_transitions: dict[tuple[str, str, str], list[str]] = {}
    occupied: dict[tuple[str, str], tuple[str, tuple]] = {}

    def claim(key: tuple[str, str], kind: str, payload: tuple) -> bool:
        previous = occupied.get(key)
        if previous is None:
            occupied[key] = (kind, payload)
            return True
        if previous == (kind, payload):
            return False
        raise EffectPredictionError(
            f"conflicting predicted effects for {key}: {previous} versus {(kind, payload)}"
        )

    for i, item in enumerate(prediction.transitions):
        dimension = _dimension(item.dimension_id, registry, field=f"transitions[{i}].dimension_id")
        subject = _pointer(item.subject, entity_table, field=f"transitions[{i}].subject")
        source = _pointer(item.source, entity_table, field=f"transitions[{i}].source")
        destination = _pointer(item.destination, entity_table, field=f"transitions[{i}].destination")
        if claim((subject, dimension), "transition", (source, destination)):
            grouped_transitions.setdefault((subject, source, destination), []).append(dimension)

    assignments: list[StateAssignment] = []
    for i, item in enumerate(prediction.assignments):
        dimension = _dimension(item.dimension_id, registry, field=f"assignments[{i}].dimension_id")
        subject = _pointer(item.subject, entity_table, field=f"assignments[{i}].subject")
        value = _pointer(item.value, atom_table, field=f"assignments[{i}].value")
        if claim((subject, dimension), "assignment", (value,)):
            assignments.append(StateAssignment.build(subject, dimension, value))

    clears: list[StateClear] = []
    for i, item in enumerate(prediction.clears):
        dimension = _dimension(item.dimension_id, registry, field=f"clears[{i}].dimension_id")
        subject = _pointer(item.subject, entity_table, field=f"clears[{i}].subject")
        if claim((subject, dimension), "clear", ()):
            clears.append(StateClear.build(subject, dimension))

    returns: dict[tuple[str, str, str], ReturnObligation] = {}
    for i, item in enumerate(prediction.returns):
        effect = ReturnObligation.build(
            _pointer(item.subject, entity_table, field=f"returns[{i}].subject"),
            _pointer(item.holder, entity_table, field=f"returns[{i}].holder"),
            _pointer(item.return_to, entity_table, field=f"returns[{i}].return_to"),
        )
        returns[effect.key()] = effect

    deltas = tuple(
        RelationDelta.build(
            subject,
            source,
            destination,
            tuple(dimensions),
            registry=registry,
        )
        for (subject, source, destination), dimensions in grouped_transitions.items()
    )

    if not deltas and not assignments and not clears and not returns:
        raise EffectPredictionError("predicted semantic effect set cannot be empty")

    return SemanticPatch.build(
        deltas,
        assignments=tuple(assignments),
        clears=tuple(clears),
        return_obligations=tuple(returns.values()),
    )
