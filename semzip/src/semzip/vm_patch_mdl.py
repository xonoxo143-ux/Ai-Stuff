from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations, product
from typing import Sequence

from .vm_effects import ClearEffect, SetEffect, ShiftEffect
from .vm_patch import SemanticPatch


ConcreteRecord = tuple[str, str, str, str, str]
PatternRecord = tuple[str, str, str, str, str]

RELATION_RECORD_COST = 5
ASSIGNMENT_RECORD_COST = 4
CLEAR_RECORD_COST = 3
MACRO_DEFINITION_OVERHEAD = 2
MACRO_CALL_OVERHEAD = 1
_CONSTANT = "_"


def patch_records(patch: SemanticPatch) -> tuple[ConcreteRecord, ...]:
    """Convert canonical atomic effects to anonymous-learning records.

    There are intentionally no word/event-specific record kinds here. A loan-style
    obligation is ordinary SetEffect structure and must earn any abstraction exactly
    like other state.
    """
    records: list[ConcreteRecord] = []
    for effect in patch.effects:
        if isinstance(effect, ShiftEffect):
            records.append(
                ("REL", effect.dimension, effect.subject, effect.source, effect.destination)
            )
        elif isinstance(effect, SetEffect):
            records.append(("SET", effect.dimension, effect.subject, effect.value, _CONSTANT))
        elif isinstance(effect, ClearEffect):
            records.append(("CLEAR", effect.dimension, effect.subject, _CONSTANT, _CONSTANT))
    return tuple(records)


def _record_cost(record: ConcreteRecord | PatternRecord) -> int:
    if record[0] == "REL":
        return RELATION_RECORD_COST
    if record[0] == "SET":
        return ASSIGNMENT_RECORD_COST
    if record[0] == "CLEAR":
        return CLEAR_RECORD_COST
    raise ValueError(f"unknown semantic record kind {record[0]!r}")


def raw_records_cost(records: Sequence[ConcreteRecord | PatternRecord]) -> int:
    return sum(_record_cost(record) for record in records)


@dataclass(frozen=True, slots=True)
class PatchPattern:
    records: tuple[PatternRecord, ...]
    variable_count: int

    @property
    def record_count(self) -> int:
        return len(self.records)

    @property
    def raw_cost(self) -> int:
        return raw_records_cost(self.records)

    @property
    def definition_cost(self) -> int:
        return MACRO_DEFINITION_OVERHEAD + self.raw_cost

    @property
    def call_cost(self) -> int:
        return MACRO_CALL_OVERHEAD + self.variable_count


@dataclass(frozen=True, slots=True)
class PatternInstance:
    pattern: PatchPattern
    bindings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatchMacroCandidate:
    pattern: PatchPattern
    occurrences: int
    base_cost: int
    encoded_cost: int
    savings: int


@dataclass(frozen=True, slots=True)
class PatchMacro:
    macro_id: str
    pattern: PatchPattern

    def call(self, patch: SemanticPatch) -> PatternInstance:
        instance = canonical_pattern(patch_records(patch))
        if instance.pattern != self.pattern:
            raise ValueError(f"patch does not match macro {self.macro_id}")
        return instance

    def expand(self, bindings: Sequence[str]) -> SemanticPatch:
        if len(bindings) != self.pattern.variable_count:
            raise ValueError(
                f"macro {self.macro_id} expects {self.pattern.variable_count} bindings, "
                f"got {len(bindings)}"
            )

        def concrete(token: str) -> str:
            if token == _CONSTANT:
                return _CONSTANT
            if token.startswith("V") and token[1:].isdigit():
                return bindings[int(token[1:])]
            return token

        return records_to_patch(
            tuple(
                (
                    record[0],
                    record[1],
                    concrete(record[2]),
                    concrete(record[3]),
                    concrete(record[4]),
                )
                for record in self.pattern.records
            )
        )


def _canonicalize_order(records: Sequence[ConcreteRecord]) -> PatternInstance:
    entity_to_var: dict[str, str] = {}
    bindings: list[str] = []
    normalized: list[PatternRecord] = []

    def variable(value: str) -> str:
        if value == _CONSTANT:
            return _CONSTANT
        found = entity_to_var.get(value)
        if found is not None:
            return found
        name = f"V{len(bindings)}"
        entity_to_var[value] = name
        bindings.append(value)
        return name

    for kind, label, a, b, c in records:
        normalized.append((kind, label, variable(a), variable(b), variable(c)))
    return PatternInstance(PatchPattern(tuple(normalized), len(bindings)), tuple(bindings))


def canonical_pattern(records: Sequence[ConcreteRecord]) -> PatternInstance:
    concrete = tuple(records)
    if not concrete:
        raise ValueError("cannot canonicalize an empty semantic pattern")

    groups: dict[tuple[str, str], list[ConcreteRecord]] = {}
    for record in concrete:
        groups.setdefault((record[0], record[1]), []).append(record)

    variants = [tuple(permutations(groups[key])) for key in sorted(groups)]
    candidate_count = 1
    for group in variants:
        candidate_count *= len(group)
    if candidate_count > 100_000:
        raise ValueError(
            "semantic pattern is too symmetric for exact canonicalization; "
            "split it into smaller macro candidates"
        )

    best: PatternInstance | None = None
    for choices in product(*variants):
        ordered = tuple(record for group in choices for record in group)
        candidate = _canonicalize_order(ordered)
        if best is None or candidate.pattern.records < best.pattern.records:
            best = candidate
    assert best is not None
    return best


def patch_pattern(patch: SemanticPatch) -> PatternInstance:
    return canonical_pattern(patch_records(patch))


def records_to_patch(records: Sequence[ConcreteRecord]) -> SemanticPatch:
    if not records:
        raise ValueError("cannot construct an empty patch")
    effects = []
    for kind, label, a, b, c in records:
        if kind == "REL":
            effects.append(ShiftEffect.build(a, label, b, c))
        elif kind == "SET":
            effects.append(SetEffect.build(a, label, b))
        elif kind == "CLEAR":
            effects.append(ClearEffect.build(a, label))
        else:
            raise ValueError(f"unsupported semantic record {(kind, label)!r}")
    return SemanticPatch.build(effects=tuple(effects))


def _matching_subsets(
    records: Sequence[ConcreteRecord], pattern: PatchPattern
) -> tuple[tuple[tuple[int, ...], tuple[str, ...]], ...]:
    matches = []
    for indices in combinations(range(len(records)), pattern.record_count):
        instance = canonical_pattern(tuple(records[index] for index in indices))
        if instance.pattern == pattern:
            matches.append((indices, instance.bindings))
    return tuple(matches)


def _max_nonoverlapping_matches(
    matches: Sequence[tuple[tuple[int, ...], tuple[str, ...]]],
) -> tuple[tuple[tuple[int, ...], tuple[str, ...]], ...]:
    best = ()

    def visit(position: int, used: frozenset[int], chosen: tuple) -> None:
        nonlocal best
        if len(chosen) + len(matches) - position <= len(best):
            return
        if position == len(matches):
            if len(chosen) > len(best):
                best = chosen
            return
        visit(position + 1, used, chosen)
        indices, bindings = matches[position]
        index_set = frozenset(indices)
        if not used.intersection(index_set):
            visit(position + 1, used | index_set, chosen + ((indices, bindings),))

    visit(0, frozenset(), ())
    return best


def factor_pattern(
    pattern: PatchPattern, component: PatchPattern
) -> tuple[tuple[str, ...], ...] | None:
    if component.record_count >= pattern.record_count:
        return None
    records: tuple[ConcreteRecord, ...] = tuple(pattern.records)
    selected = _max_nonoverlapping_matches(_matching_subsets(records, component))
    if len(selected) < 2:
        return None
    used = {index for indices, _ in selected for index in indices}
    if len(used) != len(records):
        return None
    return tuple(bindings for _, bindings in selected)


def candidate_cost(corpus: Sequence[SemanticPatch], pattern: PatchPattern) -> PatchMacroCandidate:
    """Provisional MDL score using exact substitution but fixed record weights.

    The substitution accounting is exact; the record weights remain a bootstrap
    approximation until the compact wire-format objective replaces them.
    """
    base_cost = sum(raw_records_cost(patch_records(patch)) for patch in corpus)
    encoded_body_cost = 0
    occurrences = 0
    for patch in corpus:
        records = patch_records(patch)
        selected = _max_nonoverlapping_matches(_matching_subsets(records, pattern))
        used = {index for indices, _ in selected for index in indices}
        occurrences += len(selected)
        encoded_body_cost += len(selected) * pattern.call_cost
        encoded_body_cost += raw_records_cost(
            tuple(record for index, record in enumerate(records) if index not in used)
        )
    encoded_cost = encoded_body_cost + pattern.definition_cost
    return PatchMacroCandidate(
        pattern, occurrences, base_cost, encoded_cost, base_cost - encoded_cost
    )


def discover_patch_macro_candidates(
    corpus: Sequence[SemanticPatch],
    *,
    min_records: int = 2,
    max_records: int = 4,
    min_occurrences: int = 2,
) -> tuple[PatchMacroCandidate, ...]:
    if min_records < 1 or max_records < min_records:
        raise ValueError("invalid candidate record limits")
    unique: dict[PatchPattern, None] = {}
    for patch in corpus:
        records = patch_records(patch)
        for width in range(min_records, min(max_records, len(records)) + 1):
            for subset in combinations(records, width):
                unique[canonical_pattern(subset).pattern] = None
    candidates = []
    for pattern in unique:
        score = candidate_cost(corpus, pattern)
        if score.occurrences >= min_occurrences and score.savings > 0:
            candidates.append(score)
    candidates.sort(
        key=lambda item: (item.savings, item.occurrences, item.pattern.record_count),
        reverse=True,
    )
    return tuple(candidates)


def promote_best_patch_macro(
    corpus: Sequence[SemanticPatch],
    *,
    macro_id: str = "M0",
    min_records: int = 2,
    max_records: int = 4,
    min_occurrences: int = 2,
) -> tuple[PatchMacro | None, PatchMacroCandidate | None]:
    candidates = discover_patch_macro_candidates(
        corpus,
        min_records=min_records,
        max_records=max_records,
        min_occurrences=min_occurrences,
    )
    if not candidates:
        return None, None
    best = candidates[0]
    return PatchMacro(macro_id, best.pattern), best
