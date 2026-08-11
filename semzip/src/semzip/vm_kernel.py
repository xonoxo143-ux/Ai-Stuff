from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .vm_ledger import EventLedger, atom

# Deliberately tiny kernel. Human aliases are debug conveniences; K* are the ISA.
K_SET = "K0"
K_SHIFT = "K1"
K_REQUIRE = "K2"
K_CLEAR = "K3"

ALIASES = {
    K_SET: "set",
    K_SHIFT: "shift",
    K_REQUIRE: "require",
    K_CLEAR: "clear",
}


@dataclass(frozen=True, slots=True)
class Instruction:
    opcode: str
    args: tuple[str, ...]

    @classmethod
    def make(cls, opcode: str, *args: str) -> "Instruction":
        opcode = opcode.upper()
        if opcode not in ALIASES:
            raise ValueError(f"unknown VM opcode {opcode!r}")
        return cls(opcode, tuple(atom(arg) for arg in args))


@dataclass(frozen=True, slots=True)
class Program:
    instructions: tuple[Instruction, ...]
    label: str | None = None

    @classmethod
    def build(cls, instructions: Iterable[Instruction], *, label: str | None = None) -> "Program":
        items = tuple(instructions)
        if not items:
            raise ValueError("program cannot be empty")
        return cls(items, atom(label) if label else None)


class VMExecutionError(RuntimeError):
    pass


class SemanticVM:
    """Transactional interpreter for the minimal semantic kernel."""

    def __init__(self, ledger: EventLedger | None = None) -> None:
        self.ledger = ledger or EventLedger()

    def execute(self, program: Program, *, branch: str = "main") -> tuple[int, int]:
        trial = self.ledger.clone()
        start = trial.clock
        try:
            for instruction in program.instructions:
                self._execute_one(trial, instruction, branch=branch)
        except Exception as exc:
            raise VMExecutionError(str(exc)) from exc
        self.ledger.replace_with(trial)
        return start + 1, trial.clock

    def _execute_one(self, ledger: EventLedger, ins: Instruction, *, branch: str) -> None:
        op, args = ins.opcode, ins.args
        if op == K_SET:
            self._arity(ins, 3)
            ledger.append_state(args[0], args[1], args[2], branch=branch, provenance="vm")
            return
        if op == K_SHIFT:
            self._arity(ins, 4)
            ledger.transition(args[0], args[1], args[2], args[3], branch=branch, provenance="vm")
            return
        if op == K_REQUIRE:
            self._arity(ins, 3)
            actual = ledger.current(args[0], args[1], branch=branch)
            if actual != args[2]:
                raise VMExecutionError(
                    f"require failed: {args[0]}.{args[1]} expected {args[2]!r}, found {actual!r}"
                )
            return
        if op == K_CLEAR:
            self._arity(ins, 2)
            ledger.retract(args[0], args[1], branch=branch, provenance="vm")
            return
        raise VMExecutionError(f"unimplemented opcode {op}")

    @staticmethod
    def _arity(ins: Instruction, expected: int) -> None:
        if len(ins.args) != expected:
            raise VMExecutionError(
                f"{ins.opcode} expects {expected} args, got {len(ins.args)}"
            )
