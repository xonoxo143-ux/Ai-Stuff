from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable

from .vm_compile import give, lend, move, seed_object, sell
from .vm_kernel import Program, SemanticVM, VMExecutionError


State = tuple[tuple[str, str, str], ...]


def freeze_state(state: dict[tuple[str, str], str]) -> State:
    return tuple(sorted((s, r, v) for (s, r), v in state.items()))


@dataclass(frozen=True, slots=True)
class Experience:
    label: str
    program: Program
    before: State
    after: State


class SyntheticUniverse:
    """Deterministic toy world for grounded semantic experiments.

    It intentionally avoids language. Every experience contains exact before/after
    state and the VM program that caused the transition.
    """

    def __init__(self, *, seed: int = 0, agents: int = 4, objects: int = 8, rooms: int = 4) -> None:
        self.rng = random.Random(seed)
        self.agents = tuple(f"agent{i}" for i in range(agents))
        self.objects = tuple(f"object{i}" for i in range(objects))
        self.rooms = tuple(f"room{i}" for i in range(rooms))
        self.vm = SemanticVM()
        for i, obj in enumerate(self.objects):
            owner = self.agents[i % len(self.agents)]
            room = self.rooms[i % len(self.rooms)]
            self.vm.execute(seed_object(obj, owner, location=room))

    def snapshot(self) -> State:
        return freeze_state(self.vm.ledger.project())

    def generate(self, count: int) -> tuple[Experience, ...]:
        experiences: list[Experience] = []
        attempts = 0
        while len(experiences) < count:
            attempts += 1
            if attempts > count * 50:
                raise RuntimeError("could not generate enough valid experiences")
            candidate = self._candidate()
            before = self.snapshot()
            try:
                self.vm.execute(candidate.program)
            except VMExecutionError:
                continue
            after = self.snapshot()
            experiences.append(Experience(candidate.label, candidate.program, before, after))
        return tuple(experiences)

    def _candidate(self) -> Experience:
        action = self.rng.choice(("give", "lend", "move", "sell"))
        state = self.vm.ledger.project()
        obj = self.rng.choice(self.objects)
        owner = state.get((obj, "owner"))
        possessor = state.get((obj, "possessor"))
        location = state.get((obj, "location"))
        if owner is None or possessor is None or location is None:
            raise RuntimeError("synthetic world lost a required object relation")

        if action == "move":
            destination = self.rng.choice([r for r in self.rooms if r != location])
            program = move(possessor, obj, location, destination)
            return Experience("move", program, (), ())

        if action == "give":
            if owner != possessor:
                destination = self.rng.choice([r for r in self.rooms if r != location])
                return Experience("move", move(possessor, obj, location, destination), (), ())
            recipient = self.rng.choice([a for a in self.agents if a != owner])
            return Experience("give", give(owner, recipient, obj), (), ())

        if action == "lend":
            if owner != possessor:
                destination = self.rng.choice([r for r in self.rooms if r != location])
                return Experience("move", move(possessor, obj, location, destination), (), ())
            borrower = self.rng.choice([a for a in self.agents if a != owner])
            return Experience("lend", lend(owner, borrower, obj), (), ())

        if owner != possessor:
            destination = self.rng.choice([r for r in self.rooms if r != location])
            return Experience("move", move(possessor, obj, location, destination), (), ())
        candidates = []
        for payment in self.objects:
            if payment == obj:
                continue
            p_owner = state.get((payment, "owner"))
            p_possessor = state.get((payment, "possessor"))
            if p_owner is not None and p_owner == p_possessor and p_owner != owner:
                candidates.append((payment, p_owner))
        if not candidates:
            destination = self.rng.choice([r for r in self.rooms if r != location])
            return Experience("move", move(possessor, obj, location, destination), (), ())
        payment, buyer = self.rng.choice(candidates)
        return Experience("sell", sell(owner, buyer, obj, payment), (), ())


def balanced_experiences(count: int, *, seed: int = 0) -> tuple[Experience, ...]:
    """Generate a balanced corpus from fresh micro-worlds.

    Each sample is independently grounded. This prevents long-running state drift from
    starving the corpus of action families while keeping before/after truth exact.
    """
    rng = random.Random(seed)
    agents = ("agent0", "agent1", "agent2", "agent3")
    rooms = ("room0", "room1", "room2", "room3")
    actions = ("move", "give", "lend", "sell")
    out: list[Experience] = []
    for i in range(count):
        action = actions[i % len(actions)]
        vm = SemanticVM()
        item = f"object{i % 17}"
        a, b = rng.sample(agents, 2)
        room_a, room_b = rng.sample(rooms, 2)
        vm.execute(seed_object(item, a, location=room_a))
        if action == "move":
            program = move(a, item, room_a, room_b)
        elif action == "give":
            program = give(a, b, item)
        elif action == "lend":
            program = lend(a, b, item)
        else:
            payment = f"payment{i % 13}"
            vm.execute(seed_object(payment, b, location=room_b))
            program = sell(a, b, item, payment)
        before = freeze_state(vm.ledger.project())
        vm.execute(program)
        after = freeze_state(vm.ledger.project())
        out.append(Experience(action, program, before, after))
    return tuple(out)
