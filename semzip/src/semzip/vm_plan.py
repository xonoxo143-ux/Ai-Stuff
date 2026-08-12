from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .vm_actions import ActionSchema, toy_location_schema, toy_transfer_schema
from .vm_kernel import K_CLEAR, K_REQUIRE, K_SET, K_SHIFT, Program
from .vm_ledger import atom
from .vm_state import StateSnapshot, StateTuple, snapshot_from_state
from .vm_transform import SemanticTransform, compile_semantic_transform


State = StateTuple


@dataclass(frozen=True, slots=True)
class Goal:
    subject: str
    relation: str
    value: str

    def __post_init__(self):
        object.__setattr__(self, "subject", atom(self.subject))
        object.__setattr__(self, "relation", atom(self.relation))
        object.__setattr__(self, "value", atom(self.value))

    def satisfied(self, state: State | StateSnapshot) -> bool:
        return snapshot_from_state(state).contains(self.subject, self.relation, self.value)


@dataclass(frozen=True, slots=True)
class PlanStep:
    schema: str
    transform: SemanticTransform
    bindings: tuple[tuple[str, str], ...] = ()

    @property
    def label(self) -> str:
        """Compatibility alias: labels are metadata, never semantic opcodes."""
        return self.schema

    @property
    def program(self) -> Program:
        return compile_semantic_transform(self.transform)


@dataclass(frozen=True, slots=True)
class PlanResult:
    steps: tuple[PlanStep, ...]
    visited_states: int


class SymbolicPlanner:
    """Breadth-first baseline over generic parameterized semantic transforms.

    The canonical planner knows nothing about GIVE/MOVE or the EventLedger. It searches
    immutable projected StateSnapshots. The legacy agents/rooms constructor only builds
    two toy schemas so existing v0.4 experiments remain reproducible.
    """

    def __init__(
        self,
        *,
        schemas: Sequence[ActionSchema] | None = None,
        domains: Mapping[str, Sequence[str]] | None = None,
        agents: Iterable[str] = (),
        rooms: Iterable[str] = (),
        connections: Iterable[tuple[str, str]] | None = None,
    ) -> None:
        agents = tuple(atom(value) for value in agents)
        rooms = tuple(atom(value) for value in rooms)

        if schemas is None:
            if not agents and not rooms:
                raise ValueError("planner requires schemas or the legacy agents/rooms toy domains")
            if connections is None:
                neighbors = {room: tuple(r for r in rooms if r != room) for room in rooms}
            else:
                graph: dict[str, set[str]] = {room: set() for room in rooms}
                for raw_a, raw_b in connections:
                    a, b = atom(raw_a), atom(raw_b)
                    if a not in graph or b not in graph:
                        raise ValueError("connection references unknown room")
                    graph[a].add(b)
                    graph[b].add(a)
                neighbors = {room: tuple(sorted(values)) for room, values in graph.items()}
            schemas = (toy_location_schema(neighbors), toy_transfer_schema())
            domains = {
                "agents": agents,
                "rooms": rooms,
                **({} if domains is None else dict(domains)),
            }

        self.schemas = tuple(schemas)
        self.domains = {
            str(name): tuple(atom(value) for value in values)
            for name, values in (domains or {}).items()
        }

    def plan(
        self,
        initial: State | StateSnapshot,
        goal: Goal,
        *,
        max_depth: int = 5,
    ) -> PlanResult | None:
        start = snapshot_from_state(initial)
        if goal.satisfied(start):
            return PlanResult((), 1)
        queue = deque([(start, tuple())])
        seen = {start}
        while queue:
            state, path = queue.popleft()
            if len(path) >= max_depth:
                continue
            for step, next_state in self.successor_snapshots(state):
                if next_state in seen:
                    continue
                new_path = path + (step,)
                if goal.satisfied(next_state):
                    return PlanResult(new_path, len(seen) + 1)
                seen.add(next_state)
                queue.append((next_state, new_path))
        return None

    def successor_snapshots(
        self,
        state: State | StateSnapshot,
    ) -> tuple[tuple[PlanStep, StateSnapshot], ...]:
        snapshot = snapshot_from_state(state)
        domains = dict(self.domains)
        domains.setdefault("objects", snapshot.subjects("owner"))
        results: list[tuple[PlanStep, StateSnapshot]] = []
        for schema in self.schemas:
            for bindings, transform in schema.groundings(snapshot, domains):
                next_state = snapshot.apply(transform)
                if next_state is None or next_state == snapshot:
                    continue
                results.append(
                    (
                        PlanStep(
                            schema.name,
                            transform,
                            tuple(sorted((atom(k), atom(v)) for k, v in bindings.items())),
                        ),
                        next_state,
                    )
                )
        return tuple(results)

    def successors(self, state: State) -> tuple[tuple[PlanStep, State], ...]:
        """Compatibility view for callers that still use frozen tuple states."""
        return tuple((step, snapshot.facts) for step, snapshot in self.successor_snapshots(state))

    @staticmethod
    def apply_program(state: State, program: Program) -> State | None:
        """Pure compatibility interpreter; never constructs an EventLedger."""
        values = snapshot_from_state(state).as_dict()
        for instruction in program.instructions:
            op, args = instruction.opcode, instruction.args
            if op == K_REQUIRE:
                if values.get((args[0], args[1])) != args[2]:
                    return None
            elif op == K_SHIFT:
                if values.get((args[0], args[1])) != args[2]:
                    return None
                values[(args[0], args[1])] = args[3]
            elif op == K_SET:
                values[(args[0], args[1])] = args[2]
            elif op == K_CLEAR:
                values.pop((args[0], args[1]), None)
            else:
                raise ValueError(f"unknown planner opcode {op!r}")
        return StateSnapshot.build(values).facts
