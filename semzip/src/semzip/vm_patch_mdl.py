from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations, product
from typing import Iterable, Sequence

from .vm_delta import RelationDelta
from .vm_patch import ReturnObligation, SemanticPatch


# Concrete semantic records. Relation names/effect kinds are constants; entity
# positions are the only values abstracted into anonymous variables.
ConcreteRecord = tuple[str, str, str, str, str]
PatternRecord = tuple[str, str, str, str, str]


RELATION_RECORD_COST = 5
OBLIGATION_RECORD_COST = 4
MACRO_DEFINITION_OVERHEAD = 2
MACRO_CALL_OVERHEAD = 1


def patch_records(patch: SemanticPatch) -> tuple[ConcreteRecord, ...]:
    records: list[ConcreteRecord] = []
    for delta in patch.deltas:
        for relation in delta.relations:
            records.append(("REL", relation, delta.subject, delta.source, delta.destination))
    for obligation in patch.return_obligations:
        records.append(
            (
                "EFF",
                "return",
                obligation.subject,
                obligation.holder,
                obligation.return_to,
            )
        )
    return tuple(records)


def _record_cost(record: ConcreteRecord | PatternRecord) -> int:
    return RELATION_RECORD_COST if record[0] == "REL" else OBLIGATION_RECORD_COST


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
    # V0, V1, ... in index order.
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
        return records_to_patch(
            tuple(
                (
                    record[0],
                    record[1],
                    bindings[int(record[2][1:])],
                    bindings[int(record[3][1:])],
                    bindings[int(record[4][1:])],
                )
                for record in self.pattern.records
            )
        )


def _canonicalize_order(records: Sequence[ConcreteRecord]) -> PatternInstance:
    entity_to_var: dict[str, str] = {}
    bindings: list[str] = []
    normalized: list[PatternRecord] = []

    def variable(entity: str) -> str:
        found = entity_to_var.get(entity)
        if found is not None:
            return found
        name = f"V{len(bindings)}"
        entity_to_var[entity] = name
        bindings.append(entity)
        return name

    for kind, label, a, b, c in records:
        normalized.append((kind, label, variable(a), variable(b), variable(c)))
    return PatternInstance(PatchPattern(tuple(normalized), len(bindings)), tuple(bindings))


def canonical_pattern(records: Sequence[ConcreteRecord]) -> PatternInstance:
    """Canonicalize an effect pattern independently of entity names and record order.

    Records with different semantic labels already have a deterministic order. Only
    equal-label records need permutation search. This keeps the search tiny for the
    patch sizes SemVM currently promotes while correctly handling symmetric exchanges.
    """

    concrete = tuple(records)
    if not concrete:
        raise ValueError("cannot canonicalize an empty semantic pattern")

    groups: dict[tuple[str, str], list[ConcreteRecord]] = {}
    for record in concrete:
        groups.setdefault((record[0], record[1]), []).append(record)

    group_keys = sorted(groups)
    permutations_by_group = [tuple(permutations(groups[key])) for key in group_keys]
    candidate_count = 1
    for variants in permutations_by_group:
        candidate_count *= len(variants)
    if candidate_count > 100_000:
        raise ValueError(
            "semantic pattern is too symmetric for exact canonicalization; "
            "split it into smaller macro candidates"
        )

    best: PatternInstance | None = None
    for choices in product(*permutations_by_group):
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

    grouped: dict[tuple[str, str, str], list[str]] = {}
    obligations: list[ReturnObligation] = []
    for kind, label, a, b, c in records:
        if kind == "REL":
            grouped.setdefault((a, b, c), []).append(label)
        elif kind == "EFF" and label == "return":
            obligations.append(ReturnObligation.build(a, b, c))
        else:
            raise ValueError(f"unsupported semantic record {(kind, label)!r}")

    deltas = tuple(
        RelationDelta.build(subject, source, destination, tuple(relations))
        for (subject, source, destination), relations in grouped.items()
    )
    return SemanticPatch.build(deltas, return_obligations=tuple(obligations))


def _matching_subsets(
    records: Sequence[ConcreteRecord],
    pattern: PatchPattern,
) -> tuple[tuple[tuple[int, ...], tuple[str, ...]], ...]:
    matches: list[tuple[tuple[int, ...], tuple[str, ...]]] = []
    for indices in combinations(range(len(records)), pattern.record_count):
        subset = tuple(records[index] for index in indices)
        instance = canonical_pattern(subset)
        if instance.pattern == pattern:
            matches.append((indices, instance.bindings))
    return tuple(matches)


def _max_nonoverlapping_matches(
    matches: Sequence[tuple[tuple[int, ...], tuple[str, ...]]],
) -> tuple[tuple[tuple[int, ...], tuple[str, ...]], ...]:
    best: tuple[tuple[tuple[int, ...], tuple[str, ...]], ...] = ()

    def visit(position: int, used: frozenset[int], chosen: tuple) -> None:
        nonlocal best
        if len(chosen) + (len(matches) - position) <= len(best):
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


def candidate_cost(
    corpus: Sequence[SemanticPatch],
    pattern: PatchPattern,
) -> PatchMacroCandidate:
    """Score one macro by real non-overlapping substitution, not frequency alone."""

    base_cost = sum(raw_records_cost(patch_records(patch)) for patch in corpus)
    encoded_body_cost = 0
    occurrences = 0

    for patch in corpus:
        records = patch_records(patch)
        selected = _max_nonoverlapping_matches(_matching_subsets(records, pattern))
        used: set[int] = set()
        for indices, _ in selected:
            used.update(indices)
        occurrences += len(selected)
        encoded_body_cost += len(selected) * pattern.call_cost
        encoded_body_cost += raw_records_cost(
            tuple(record for index, record in enumerate(records) if index not in used)
        )

    encoded_cost = encoded_body_cost + pattern.definition_cost
    return PatchMacroCandidate(
        pattern=pattern,
        occurrences=occurrences,
        base_cost=base_cost,
        encoded_cost=encoded_cost,
        savings=base_cost - encoded_cost,
    )


def discover_patch_macro_candidates(
    corpus: Sequence[SemanticPatch],
    *,
    min_records: int = 2,
    max_records: int = 4,
    min_occurrences: int = 2,
) -> tuple[PatchMacroCandidate, ...]:
    """Mine anonymous effect subpatterns and rank them by actual description savings."""

    if min_records < 1 or max_records < min_records:
        raise ValueError("invalid candidate record limits")

    unique: dict[PatchPattern, None] = {}
    for patch in corpus:
        records = patch_records(patch)
        upper = min(max_records, len(records))
        for width in range(min_records, upper + 1):
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
