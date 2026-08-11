from __future__ import annotations

from dataclasses import dataclass
import random

from .vm_compile import seed_object
from .vm_kernel import SemanticVM
from .vm_lab import State, freeze_state
from .vm_plan import Goal, SymbolicPlanner


@dataclass(frozen=True, slots=True)
class ControllerExample:
    state: State
    goal: Goal
    action: str
    target_object: str
    target_value: str


class PlanningDatasetBuilder:
    """Generate supervised next-operation examples from exact symbolic search."""

    def __init__(self, *, seed: int = 0, agents: int = 3, objects: int = 3, rooms: int = 3) -> None:
        self.rng = random.Random(seed)
        self.agents = tuple(f"agent{i}" for i in range(agents))
        self.objects = tuple(f"object{i}" for i in range(objects))
        self.rooms = tuple(f"room{i}" for i in range(rooms))
        connections = tuple((self.rooms[i], self.rooms[i + 1]) for i in range(len(self.rooms) - 1))
        self.planner = SymbolicPlanner(
            agents=self.agents, rooms=self.rooms, connections=connections
        )

    def random_state(self) -> State:
        vm = SemanticVM()
        for obj in self.objects:
            owner = self.rng.choice(self.agents)
            location = self.rng.choice(self.rooms)
            vm.execute(seed_object(obj, owner, location=location))
        return freeze_state(vm.ledger.project())

    def build(self, count: int, *, max_depth: int = 4) -> tuple[ControllerExample, ...]:
        out: list[ControllerExample] = []
        attempts = 0
        while len(out) < count:
            attempts += 1
            if attempts > count * 50:
                raise RuntimeError("could not generate enough planning examples")
            state = self.random_state()
            obj = self.rng.choice(self.objects)
            if self.rng.random() < 0.65:
                goal = Goal(obj, "location", self.rng.choice(self.rooms))
            else:
                goal = Goal(obj, "owner", self.rng.choice(self.agents))
            result = self.planner.plan(state, goal, max_depth=max_depth)
            if result is None or not result.steps:
                continue
            current = state
            for step in result.steps:
                if step.label == "move":
                    shift = next(ins for ins in step.program.instructions if ins.opcode == "K1")
                    target = shift.args[3]
                else:
                    owner_shift = next(
                        ins for ins in step.program.instructions
                        if ins.opcode == "K1" and ins.args[1] == "owner"
                    )
                    target = owner_shift.args[3]
                out.append(ControllerExample(current, goal, step.label, obj, target))
                if len(out) >= count:
                    break
                next_state = self.planner.apply_program(current, step.program)
                if next_state is None:
                    raise RuntimeError("planner emitted a non-executable training step")
                current = next_state
        return tuple(out)
