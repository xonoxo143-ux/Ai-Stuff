from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .vm_ledger import EventLedger, atom

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

ARITIES = {
    K_SET: 3,
    K_SHIFT: 4,
    K_REQUIRE: 3,
    K_CLEAR: 2,
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
        expected = ARITIES[opcode]
        if len(args) != expected:
            raise ValueError(f"{opcode} expects {expected} args, got {len(args)}")
        return cls(opcode, tuple(atom(arg) for arg in args))


@dataclass(frozen=True, slots=True)
class Program:
    instructions: tuple[Instruction, ...]
    label: str | None = None

    @classmethod
    def build(cls, instructions: Iterable[Instruction], *, label: str | None = None) -> "Program":
        items = tuple(instructions)
        for ins in items:
            if ins.opcode not in ARITIES:
                raise ValueError(f"unknown VM opcode {ins.opcode!r}")
            expected = ARITIES[ins.opcode]
            if len(ins.args) != expected:
                raise ValueError(f"{ins.opcode} expects {expected} args, got {len(ins.args)}")
        # Empty programs are the explicit identity transformation. Untrusted bridges
        # still reject empty proposals unless their protocol explicitly permits NOOP.
        return cls(items, atom(label) if label else None)

    @classmethod
    def empty(cls, *, label: str | None = "identity") -> "Program":
        return cls.build((), label=label)

    @property
    def is_empty(self) -> bool:
        return not self.instructions


class VMExecutionError(RuntimeError):
    pass


class SemanticVM:
    """Transactional interpreter for the minimal semantic kernel.

    Atomicity uses a tiny copy-on-write shadow of only the relations touched by the
    current program. The event history is never cloned for ordinary execution.
    """

    def __init__(self, ledger: EventLedger | None = None) -> None:
        self.ledger = ledger or EventLedger()

    def execute(self, program: Program, *, branch: str = "main") -> tuple[int, int]:
        branch = atom(branch)
        overlay: dict[tuple[str, str], str | None] = {}
        mutations: list[Instruction] = []

        def read(subject: str, relation: str) -> str | None:
            key = (subject, relation)
            if key in overlay:
                return overlay[key]
            return self.ledger.current(subject, relation, branch=branch)

        try:
            for ins in program.instructions:
                op, args = ins.opcode, ins.args
                if op == K_SET:
                    self._arity(ins, 3)
                    overlay[(args[0], args[1])] = args[2]
                    mutations.append(ins)
                elif op == K_SHIFT:
                    self._arity(ins, 4)
                    actual = read(args[0], args[1])
                    if actual != args[2]:
                        raise VMExecutionError(
                            f"shift failed: {args[0]}.{args[1]} expected {args[2]!r}, found {actual!r}"
                        )
                    overlay[(args[0], args[1])] = args[3]
                    mutations.append(ins)
                elif op == K_REQUIRE:
                    self._arity(ins, 3)
                    actual = read(args[0], args[1])
                    if actual != args[2]:
                        raise VMExecutionError(
                            f"require failed: {args[0]}.{args[1]} expected {args[2]!r}, found {actual!r}"
                        )
                elif op == K_CLEAR:
                    self._arity(ins, 2)
                    overlay[(args[0], args[1])] = None
                    mutations.append(ins)
                else:
                    raise VMExecutionError(f"unimplemented opcode {op}")
        except Exception as exc:
            if isinstance(exc, VMExecutionError):
                raise
            raise VMExecutionError(str(exc)) from exc

        start = self.ledger.clock
        for ins in mutations:
            op, args = ins.opcode, ins.args
            if op == K_SET:
                self.ledger.append_state(args[0], args[1], args[2], branch=branch, provenance="vm")
            elif op == K_SHIFT:
                self.ledger.transition(args[0], args[1], args[2], args[3], branch=branch, provenance="vm")
            elif op == K_CLEAR:
                self.ledger.retract(args[0], args[1], branch=branch, provenance="vm")
        return (start + 1 if mutations else start), self.ledger.clock

    @staticmethod
    def _arity(ins: Instruction, expected: int) -> None:
        if len(ins.args) != expected:
            raise VMExecutionError(
                f"{ins.opcode} expects {expected} args, got {len(ins.args)}"
            )
