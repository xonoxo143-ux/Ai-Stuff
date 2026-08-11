from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .vm_lab import Experience, State


@dataclass(frozen=True, slots=True)
class Delta:
    subject: str
    relation: str
    before: str | None
    after: str | None


DeltaPattern = tuple[int, int, int, int]
DeltaFragment = tuple[DeltaPattern, ...]


@dataclass(frozen=True, slots=True)
class DeltaMacroCandidate:
    pattern: DeltaFragment
    experiences: int
    uses: int
    definition_cost: int
    encoded_cost: int
    net_savings: int


@dataclass(frozen=True, slots=True)
class DeltaDiscoveryReport:
    base_cost: int
    candidates: tuple[DeltaMacroCandidate, ...]

    @property
    def best(self) -> DeltaMacroCandidate | None:
        return self.candidates[0] if self.candidates else None


def world_delta(before: State, after: State) -> tuple[Delta, ...]:
    b = {(s, r): v for s, r, v in before}
    a = {(s, r): v for s, r, v in after}
    out: list[Delta] = []
    for subject, relation in sorted(set(b) | set(a)):
        old, new = b.get((subject, relation)), a.get((subject, relation))
        if old != new:
            out.append(Delta(subject, relation, old, new))
    return tuple(out)


def normalize_deltas(deltas: Iterable[Delta]) -> DeltaFragment:
    """Canonicalize identities while preserving cross-change equality structure."""
    deltas = tuple(deltas)
    deltas = tuple(sorted(deltas, key=lambda d: (d.relation, d.subject, d.before or "", d.after or "")))
    mapping: dict[str, int] = {}
    next_id = 0

    def encode(value: str | None) -> int:
        nonlocal next_id
        if value is None:
            return -1
        if value not in mapping:
            mapping[value] = next_id
            next_id += 1
        return mapping[value]

    out = tuple(
        (encode(d.subject), encode(d.relation), encode(d.before), encode(d.after))
        for d in deltas
    )
    return _renumber(tuple(sorted(out)))


def _renumber(pattern: DeltaFragment) -> DeltaFragment:
    remap: dict[int, int] = {}
    next_id = 0
    out: list[DeltaPattern] = []
    for row in pattern:
        new_row = []
        for value in row:
            if value < 0:
                new_row.append(-1)
                continue
            if value not in remap:
                remap[value] = next_id
                next_id += 1
            new_row.append(remap[value])
        out.append(tuple(new_row))
    return tuple(out)  # type: ignore[return-value]


def delta_cost(delta: Delta) -> int:
    return 4


def pattern_variable_count(pattern: DeltaFragment) -> int:
    return 1 + max((v for row in pattern for v in row if v >= 0), default=-1)


def pattern_cost(pattern: DeltaFragment) -> int:
    return len(pattern) * 4 + pattern_variable_count(pattern)


def _match_pattern(pattern: DeltaFragment, chosen: tuple[Delta, ...]) -> bool:
    return normalize_deltas(chosen) == pattern


def _nonoverlap_uses(pattern: DeltaFragment, deltas: tuple[Delta, ...]) -> tuple[int, set[int]]:
    width = len(pattern)
    if width > len(deltas):
        return 0, set()
    matches: list[tuple[int, ...]] = []
    for idxs in combinations(range(len(deltas)), width):
        chosen = tuple(deltas[i] for i in idxs)
        if _match_pattern(pattern, chosen):
            matches.append(idxs)
    used: set[int] = set()
    count = 0
    for idxs in matches:
        if any(i in used for i in idxs):
            continue
        used.update(idxs)
        count += 1
    return count, used


def discover_delta_macros(
    experiences: Iterable[Experience],
    *,
    min_experiences: int = 3,
    min_width: int = 1,
    max_width: int = 4,
) -> DeltaDiscoveryReport:
    """Discover reusable transformations from world deltas alone.

    The action labels and source VM programs are deliberately ignored.
    """
    deltas_by_exp = tuple(world_delta(x.before, x.after) for x in experiences)
    base = sum(delta_cost(d) for ds in deltas_by_exp for d in ds)
    proposal_exp_counts: Counter[DeltaFragment] = Counter()

    for deltas in deltas_by_exp:
        seen_here: set[DeltaFragment] = set()
        upper = min(max_width, len(deltas))
        for width in range(min_width, upper + 1):
            for chosen in combinations(deltas, width):
                seen_here.add(normalize_deltas(chosen))
        proposal_exp_counts.update(seen_here)

    candidates: list[DeltaMacroCandidate] = []
    for pattern, exp_count in proposal_exp_counts.items():
        if exp_count < min_experiences:
            continue
        definition = pattern_cost(pattern)
        call_cost = 1 + pattern_variable_count(pattern)
        encoded = definition
        total_uses = 0
        experiences_used = 0
        for deltas in deltas_by_exp:
            uses, used_indices = _nonoverlap_uses(pattern, deltas)
            if uses:
                experiences_used += 1
                total_uses += uses
            encoded += uses * call_cost
            encoded += sum(
                delta_cost(delta) for i, delta in enumerate(deltas) if i not in used_indices
            )
        net = base - encoded
        if net > 0:
            candidates.append(
                DeltaMacroCandidate(
                    pattern,
                    experiences_used,
                    total_uses,
                    definition,
                    encoded,
                    net,
                )
            )
    candidates.sort(key=lambda c: (-c.net_savings, -len(c.pattern), -c.uses, c.pattern))
    return DeltaDiscoveryReport(base, tuple(candidates))
