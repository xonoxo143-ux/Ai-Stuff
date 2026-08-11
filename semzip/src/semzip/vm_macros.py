from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Union

from .vm_kernel import Instruction, Program
from .vm_mdl import MacroCandidate, Pattern


@dataclass(frozen=True, slots=True)
class MacroDefinition:
    name: str
    pattern: Pattern

    @classmethod
    def from_candidate(cls, name: str, candidate: MacroCandidate) -> "MacroDefinition":
        return cls(name=name.upper(), pattern=candidate.pattern)


@dataclass(frozen=True, slots=True)
class MacroCall:
    name: str
    args: tuple[str, ...]


EncodedStep = Union[Instruction, MacroCall]


@dataclass(frozen=True, slots=True)
class EncodedProgram:
    steps: tuple[EncodedStep, ...]
    label: str | None = None


class MacroLibrary:
    def __init__(self, definitions: Iterable[MacroDefinition] = ()) -> None:
        self._definitions: dict[str, MacroDefinition] = {}
        for definition in definitions:
            self.add(definition)

    @property
    def definitions(self) -> tuple[MacroDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def add(self, definition: MacroDefinition) -> None:
        name = definition.name.upper()
        if name in self._definitions:
            raise ValueError(f"macro {name!r} already exists")
        if not definition.pattern:
            raise ValueError("macro pattern cannot be empty")
        self._definitions[name] = MacroDefinition(name, definition.pattern)

    def encode(self, program: Program) -> EncodedProgram:
        defs = sorted(self._definitions.values(), key=lambda d: (-len(d.pattern), d.name))
        out: list[EncodedStep] = []
        i = 0
        instructions = program.instructions
        while i < len(instructions):
            matched = False
            for definition in defs:
                size = len(definition.pattern)
                if i + size > len(instructions):
                    continue
                args = _match(definition.pattern, instructions[i : i + size])
                if args is None:
                    continue
                out.append(MacroCall(definition.name, args))
                i += size
                matched = True
                break
            if not matched:
                out.append(instructions[i])
                i += 1
        return EncodedProgram(tuple(out), program.label)

    def expand(self, encoded: EncodedProgram) -> Program:
        instructions: list[Instruction] = []
        for step in encoded.steps:
            if isinstance(step, Instruction):
                instructions.append(step)
                continue
            definition = self._definitions.get(step.name.upper())
            if definition is None:
                raise ValueError(f"unknown macro {step.name!r}")
            instructions.extend(_instantiate(definition.pattern, step.args))
        return Program.build(instructions, label=encoded.label)


def _match(pattern: Pattern, instructions: tuple[Instruction, ...]) -> tuple[str, ...] | None:
    if len(pattern) != len(instructions):
        return None
    bindings: dict[int, str] = {}
    max_var = -1
    for (p_opcode, p_vars), ins in zip(pattern, instructions):
        if p_opcode != ins.opcode or len(p_vars) != len(ins.args):
            return None
        for var, arg in zip(p_vars, ins.args):
            max_var = max(max_var, var)
            existing = bindings.get(var)
            if existing is not None and existing != arg:
                return None
            bindings[var] = arg
    return tuple(bindings[i] for i in range(max_var + 1))


def _instantiate(pattern: Pattern, args: tuple[str, ...]) -> tuple[Instruction, ...]:
    out: list[Instruction] = []
    for opcode, vars_ in pattern:
        try:
            concrete = tuple(args[i] for i in vars_)
        except IndexError as exc:
            raise ValueError("macro call has too few arguments") from exc
        out.append(Instruction.make(opcode, *concrete))
    return tuple(out)


def encoded_step_cost(step: EncodedStep) -> int:
    return 1 + len(step.args)


def library_description_cost(library: MacroLibrary, programs: Iterable[Program]) -> int:
    from .vm_mdl import pattern_cost, variable_count

    definitions = sum(
        pattern_cost(d.pattern) + variable_count(d.pattern)
        for d in library.definitions
    )
    encoded = 0
    for program in programs:
        encoded_program = library.encode(program)
        encoded += sum(encoded_step_cost(step) for step in encoded_program.steps)
    return definitions + encoded


@dataclass(frozen=True, slots=True)
class LearnedLibrary:
    library: MacroLibrary
    base_cost: int
    final_cost: int
    savings: int


def learn_library(
    programs: Iterable[Program],
    *,
    max_macros: int = 8,
    min_occurrences: int = 3,
    candidate_limit: int = 80,
) -> LearnedLibrary:
    """Greedily promote only macros that reduce realized total description cost."""
    from .vm_mdl import corpus_cost, discover_macros

    programs = tuple(programs)
    base = corpus_cost(programs)
    proposals = discover_macros(
        programs, min_occurrences=min_occurrences, min_len=2, max_len=6
    ).candidates[:candidate_limit]
    selected: list[MacroDefinition] = []
    current_cost = base
    used_patterns: set[Pattern] = set()

    for _ in range(max_macros):
        best_def: MacroDefinition | None = None
        best_cost = current_cost
        for candidate in proposals:
            if candidate.pattern in used_patterns:
                continue
            definition = MacroDefinition.from_candidate(f"M{len(selected)}", candidate)
            trial = MacroLibrary(selected + [definition])
            cost = library_description_cost(trial, programs)
            if cost < best_cost:
                best_cost = cost
                best_def = definition
        if best_def is None:
            break
        selected.append(best_def)
        used_patterns.add(best_def.pattern)
        current_cost = best_cost

    library = MacroLibrary(selected)
    return LearnedLibrary(library, base, current_cost, base - current_cost)
