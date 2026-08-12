from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

from .vm_patch import SemanticPatch
from .vm_patch_mdl import (
    ConcreteRecord,
    PatchMacro,
    canonical_pattern,
    patch_records,
    raw_records_cost,
    records_to_patch,
)


@dataclass(frozen=True, slots=True)
class EncodedMacroCall:
    macro_id: str
    bindings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EncodedPatch:
    macro_calls: tuple[EncodedMacroCall, ...]
    residual_records: tuple[ConcreteRecord, ...]
    raw_cost: int
    encoded_cost: int

    @property
    def savings(self) -> int:
        return self.raw_cost - self.encoded_cost


@dataclass(frozen=True, slots=True)
class _Match:
    macro: PatchMacro
    indices: tuple[int, ...]
    bindings: tuple[str, ...]
    savings: int


def _matches(records: Sequence[ConcreteRecord], macro: PatchMacro) -> tuple[_Match, ...]:
    pattern = macro.pattern
    result: list[_Match] = []
    for indices in combinations(range(len(records)), pattern.record_count):
        subset = tuple(records[index] for index in indices)
        instance = canonical_pattern(subset)
        if instance.pattern != pattern:
            continue
        raw = raw_records_cost(subset)
        savings = raw - pattern.call_cost
        if savings > 0:
            result.append(_Match(macro, indices, instance.bindings, savings))
    return tuple(result)


def encode_patch(
    patch: SemanticPatch,
    macros: Sequence[PatchMacro],
) -> EncodedPatch:
    """Choose the best non-overlapping macro cover for a patch exactly.

    Patch sizes are currently small, so exhaustive set-packing is preferable to a
    greedy shortcut: encoding decisions are deterministic and can be regression-tested.
    Macro *definition* cost belongs to the library/corpus objective and is therefore
    not charged again for every encoded patch.
    """

    records = patch_records(patch)
    all_matches = tuple(
        match
        for macro in macros
        for match in _matches(records, macro)
    )

    best_savings = 0
    best_matches: tuple[_Match, ...] = ()

    def visit(position: int, used: frozenset[int], chosen: tuple[_Match, ...], savings: int):
        nonlocal best_savings, best_matches
        remaining_upper = savings + sum(
            max(0, match.savings) for match in all_matches[position:]
        )
        if remaining_upper < best_savings:
            return
        if position == len(all_matches):
            key = tuple((m.macro.macro_id, m.indices, m.bindings) for m in chosen)
            best_key = tuple((m.macro.macro_id, m.indices, m.bindings) for m in best_matches)
            if savings > best_savings or (savings == best_savings and key < best_key):
                best_savings = savings
                best_matches = chosen
            return

        visit(position + 1, used, chosen, savings)
        match = all_matches[position]
        index_set = frozenset(match.indices)
        if not used.intersection(index_set):
            visit(
                position + 1,
                used | index_set,
                chosen + (match,),
                savings + match.savings,
            )

    visit(0, frozenset(), (), 0)

    used = {index for match in best_matches for index in match.indices}
    residual = tuple(
        record for index, record in enumerate(records) if index not in used
    )
    calls = tuple(
        EncodedMacroCall(match.macro.macro_id, match.bindings)
        for match in sorted(best_matches, key=lambda item: (item.indices, item.macro.macro_id))
    )
    macro_by_id = {macro.macro_id: macro for macro in macros}
    encoded_cost = raw_records_cost(residual) + sum(
        macro_by_id[call.macro_id].pattern.call_cost for call in calls
    )
    return EncodedPatch(
        macro_calls=calls,
        residual_records=residual,
        raw_cost=raw_records_cost(records),
        encoded_cost=encoded_cost,
    )


def decode_patch(
    encoded: EncodedPatch,
    macros: Sequence[PatchMacro],
) -> SemanticPatch:
    macro_by_id = {macro.macro_id: macro for macro in macros}
    if len(macro_by_id) != len(tuple(macros)):
        raise ValueError("macro IDs must be unique")

    records: list[ConcreteRecord] = list(encoded.residual_records)
    for call in encoded.macro_calls:
        try:
            macro = macro_by_id[call.macro_id]
        except KeyError as exc:
            raise KeyError(f"missing semantic macro {call.macro_id!r}") from exc
        expanded = macro.expand(call.bindings)
        records.extend(patch_records(expanded))
    return records_to_patch(tuple(records))
