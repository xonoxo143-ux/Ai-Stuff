from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from .vm_compile import give, move
from .vm_kernel import Program, SemanticVM, VMExecutionError
from .vm_lab import State, freeze_state
from .vm_ledger import EventLedger


@dataclass(frozen=True, slots=True)
class Goal:
    subject: str
    relation: str
    value: str

    def satisfied(self, state: State) -> bool:
        return (self.subject, self.relation, self.value) in state


@dataclass(frozen=True, slots=True)
class PlanStep:
    label: str
    program: Program


@dataclass(frozen=True, slots=True)
class PlanResult:
    steps: tuple[PlanStep, ...]
    visited_states: int


class SymbolicPlanner:
    """Breadth-first baseline over VM programs."""

    def __init__(
        self,
        *,
        agents: Iterable[str],
        rooms: Iterable[str],
        connections: Iterable[tuple[str, str]] | None = None,
    ) -> None:
        self.agents = tuple(agents)
        self.rooms = tuple(rooms)
        if connections is None:
            self._neighbors = {room: tuple(r for r in self.rooms if r != room) for room in self.rooms}
        else:
            graph: dict[str, set[str]] = {room: set() for room in self.rooms}
            for a, b in connections:
                if a not in graph or b not in graph:
                    raise ValueError("connection references unknown room")
                graph[a].add(b)
                graph[b].add(a)
            self._neighbors = {room: tuple(sorted(values)) for room, values in graph.items()}

    def plan(self, initial: State, goal: Goal, *, max_depth: int = 5) -> PlanResult | None:
        if goal.satisfied(initial):
            return PlanResult((), 1)
        queue = deque([(initial, tuple())])
        seen = {initial}
        while queue:
            state, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for step, next_state in self.successors(state):
                if next_state in seen:
                    continue
                new_path = path + (step,)
                if goal.satisfied(next_state):
                    return PlanResult(new_path, len(seen) + 1)
                seen.add(next_state)
                queue.append((next_state, new_path))
        return None

    def successors(self, state: State) -> tuple[tuple[PlanStep, State], ...]:
        state_map = {(s, r): v for s, r, v in state}
        objects = sorted({s for s, r, _ in state if r == "owner"})
        results: list[tuple[PlanStep, State]] = []
        for obj in objects:
            owner = state_map.get((obj, "owner"))
            possessor = state_map.get((obj, "possessor"))
            location = state_map.get((obj, "location"))
            if possessor is not None and location is not None:
                for room in self._neighbors.get(location, ()):
                    program = move(possessor, obj, location, room)
                    next_state = self.apply_program(state, program)
                    if next_state is not None:
                        results.append((PlanStep("move", program), next_state))
            if owner is not None and owner == possessor:
                for recipient in self.agents:
                    if recipient == owner:
                        continue
                    program = give(owner, recipient, obj)
                    next_state = self.apply_program(state, program)
                    if next_state is not None:
                        results.append((PlanStep("give", program), next_state))
        return tuple(results)

    @staticmethod
    def apply_program(state: State, program: Program) -> State | None:
        ledger = EventLedger()
        for subject, relation, value in state:
            ledger.append_state(subject, relation, value, provenance="planner_seed")
        vm = SemanticVM(ledger)
        try:
            vm.execute(program)
        except VMExecutionError:
            return None
        return freeze_state(vm.ledger.project())
