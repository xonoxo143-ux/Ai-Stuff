from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .meaning import Meaning, MeaningValue


@dataclass(frozen=True, slots=True)
class CompressionReport:
    surface_forms: int
    unique_meanings: int
    unique_shapes: int
    exact_deduplication: float
    shape_reuse: float
    operator_counts: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "surface_forms": self.surface_forms,
            "unique_meanings": self.unique_meanings,
            "unique_shapes": self.unique_shapes,
            "exact_deduplication": self.exact_deduplication,
            "shape_reuse": self.shape_reuse,
            "operator_counts": dict(self.operator_counts),
        }


def structural_signature(meaning: Meaning) -> tuple[object, ...]:
    """Return meaning structure while erasing concrete atom values.

    Exact hashes answer "are these the same meaning?"
    Structural signatures answer "are these built from the same machinery?"
    """
    roles: list[tuple[str, object]] = []
    for role, value in meaning.roles:
        roles.append((role, _value_shape(value)))
    return (meaning.operator, tuple(roles))


def operator_inventory(meaning: Meaning) -> Counter[str]:
    counts: Counter[str] = Counter()

    def visit(node: Meaning) -> None:
        counts[node.operator] += 1
        for _, value in node.roles:
            if isinstance(value, Meaning):
                visit(value)

    visit(meaning)
    return counts


def analyze(meanings: Iterable[Meaning]) -> CompressionReport:
    items = tuple(meanings)
    total = len(items)
    if total == 0:
        return CompressionReport(0, 0, 0, 0.0, 0.0, ())

    unique_hashes = {item.semantic_hash() for item in items}
    unique_shapes = {structural_signature(item) for item in items}
    operators: Counter[str] = Counter()
    for item in items:
        operators.update(operator_inventory(item))

    return CompressionReport(
        surface_forms=total,
        unique_meanings=len(unique_hashes),
        unique_shapes=len(unique_shapes),
        exact_deduplication=1.0 - (len(unique_hashes) / total),
        shape_reuse=1.0 - (len(unique_shapes) / total),
        operator_counts=tuple(sorted(operators.items())),
    )


def _value_shape(value: MeaningValue) -> object:
    if isinstance(value, Meaning):
        return structural_signature(value)
    if isinstance(value, bool):
        return "$BOOL"
    if isinstance(value, (int, float)):
        return "$NUMBER"
    return "$ATOM"
