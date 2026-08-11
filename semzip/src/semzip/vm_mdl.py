from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator

from .vm_kernel import Instruction, Program

PatternInstruction = tuple[str, tuple[int, ...]]
Pattern = tuple[PatternInstruction, ...]


@dataclass(frozen=True, slots=True)
class MacroCandidate:
    pattern: Pattern
    occurrences: int
    definition_cost: int
    encoded_corpus_cost: int
    net_savings: int


@dataclass(frozen=True, slots=True)
class MDLReport:
    base_cost: int
    candidates: tuple[MacroCandidate, ...]

    @property
    def best(self) -> MacroCandidate | None:
        return self.candidates[0] if self.candidates else None


def instruction_cost(ins: Instruction) -> int:
    return 1 + len(ins.args)


def program_cost(program: Program) -> int:
    return sum(instruction_cost(ins) for ins in program.instructions)


def corpus_cost(programs: Iterable[Program]) -> int:
    return sum(program_cost(program) for program in programs)


def normalize_fragment(instructions: tuple[Instruction, ...]) -> Pattern:
    """Erase atom names while preserving argument equality/reuse structure."""
    ids: dict[str, int] = {}
    next_id = 0
    out: list[PatternInstruction] = []
    for ins in instructions:
        encoded: list[int] = []
        for arg in ins.args:
            if arg not in ids:
                ids[arg] = next_id
                next_id += 1
            encoded.append(ids[arg])
        out.append((ins.opcode, tuple(encoded)))
    return tuple(out)


def fragments(program: Program, *, min_len: int = 2, max_len: int = 5) -> Iterator[Pattern]:
    items = program.instructions
    upper = min(max_len, len(items))
    for length in range(min_len, upper + 1):
        for start in range(0, len(items) - length + 1):
            yield normalize_fragment(items[start : start + length])


def pattern_cost(pattern: Pattern) -> int:
    return sum(1 + len(args) for _, args in pattern)


def variable_count(pattern: Pattern) -> int:
    return 1 + max((v for _, args in pattern for v in args), default=-1)


def _match(pattern: Pattern, instructions: tuple[Instruction, ...]) -> bool:
    if len(pattern) != len(instructions):
        return False
    bindings: dict[int, str] = {}
    for (p_opcode, p_vars), ins in zip(pattern, instructions):
        if p_opcode != ins.opcode or len(p_vars) != len(ins.args):
            return False
        for var, arg in zip(p_vars, ins.args):
            previous = bindings.get(var)
            if previous is not None and previous != arg:
                return False
            bindings[var] = arg
    return True


def realized_cost(programs: tuple[Program, ...], pattern: Pattern) -> tuple[int, int, int]:
    """Return total encoded cost, actual non-overlapping uses, and definition cost."""
    call_cost = 1 + variable_count(pattern)
    definition_cost = pattern_cost(pattern) + variable_count(pattern)
    encoded = definition_cost
    uses = 0
    width = len(pattern)
    for program in programs:
        items = program.instructions
        i = 0
        while i < len(items):
            if i + width <= len(items) and _match(pattern, items[i : i + width]):
                encoded += call_cost
                uses += 1
                i += width
            else:
                encoded += instruction_cost(items[i])
                i += 1
    return encoded, uses, definition_cost


def discover_macros(
    programs: Iterable[Program],
    *,
    min_occurrences: int = 2,
    min_len: int = 2,
    max_len: int = 5,
) -> MDLReport:
    """Mine candidates and rank by *realized* description-length savings.

    Candidate frequency is only a proposal mechanism. A macro survives only if
    substituting its actual non-overlapping matches plus storing its definition makes
    the corpus shorter.
    """
    programs = tuple(programs)
    base = corpus_cost(programs)
    proposal_counts: Counter[Pattern] = Counter()
    for program in programs:
        proposal_counts.update(fragments(program, min_len=min_len, max_len=max_len))

    candidates: list[MacroCandidate] = []
    for pattern, proposed in proposal_counts.items():
        if proposed < min_occurrences:
            continue
        encoded, uses, definition_cost = realized_cost(programs, pattern)
        if uses < min_occurrences:
            continue
        net = base - encoded
        if net > 0:
            candidates.append(
                MacroCandidate(
                    pattern=pattern,
                    occurrences=uses,
                    definition_cost=definition_cost,
                    encoded_corpus_cost=encoded,
                    net_savings=net,
                )
            )
    candidates.sort(key=lambda c: (-c.net_savings, -c.occurrences, c.pattern))
    return MDLReport(base, tuple(candidates))
