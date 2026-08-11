"""Variable-domain controller experiment.

The model never receives fixed entity/room IDs. It scores anonymous candidate VM
operations using relational features, so the same tiny network can run on worlds with
different numbers and names of agents/rooms.
"""
from __future__ import annotations

from collections import deque
import random
import sys
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semzip.vm_compile import seed_object
from semzip.vm_kernel import SemanticVM
from semzip.vm_lab import freeze_state
from semzip.vm_plan import Goal, PlanStep, SymbolicPlanner


def distance(planner: SymbolicPlanner, start: str, goal: str) -> int:
    if start == goal:
        return 0
    q = deque([(start, 0)])
    seen = {start}
    while q:
        node, d = q.popleft()
        for nxt in planner._neighbors.get(node, ()):
            if nxt == goal:
                return d + 1
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, d + 1))
    return 99


def changed_relation(step: PlanStep, subject: str):
    for ins in step.program.instructions:
        if ins.opcode == "K1" and ins.args[0] == subject:
            return ins.args[1], ins.args[3]
    return None, None


def features(state, goal: Goal, step: PlanStep, next_state, planner: SymbolicPlanner) -> torch.Tensor:
    facts = {(s, r): v for s, r, v in state}
    next_facts = {(s, r): v for s, r, v in next_state}
    relation, target = changed_relation(step, goal.subject)
    is_move = float(step.label == "move")
    is_give = float(step.label == "give")
    goal_location = float(goal.relation == "location")
    goal_owner = float(goal.relation == "owner")
    relation_match = float(relation == goal.relation)
    target_match = float(target == goal.value)

    before_dist = 0.0
    after_dist = 0.0
    if goal.relation == "location":
        before_loc = facts.get((goal.subject, "location"))
        after_loc = next_facts.get((goal.subject, "location"))
        if before_loc is not None and after_loc is not None:
            scale = max(1, len(planner.rooms) - 1)
            before_dist = distance(planner, before_loc, goal.value) / scale
            after_dist = distance(planner, after_loc, goal.value) / scale
    elif goal.relation == "owner":
        before_dist = float(facts.get((goal.subject, "owner")) != goal.value)
        after_dist = float(next_facts.get((goal.subject, "owner")) != goal.value)

    return torch.tensor(
        [
            is_move, is_give, goal_location, goal_owner,
            relation_match, target_match,
            before_dist, after_dist, before_dist - after_dist,
        ],
        dtype=torch.float32,
    )


class CandidateScorer(nn.Module):
    def __init__(self, hidden: int = 6) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(9, hidden), nn.Tanh(), nn.Linear(hidden, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def random_problem(rng: random.Random, *, max_agents: int, max_rooms: int, prefix: str):
    agent_count = rng.randint(2, max_agents)
    room_count = rng.randint(2, max_rooms)
    agents = tuple(f"{prefix}_person_{i}" for i in range(agent_count))
    rooms = tuple(f"{prefix}_place_{i}" for i in range(room_count))
    connections = tuple((rooms[i], rooms[i + 1]) for i in range(room_count - 1))
    planner = SymbolicPlanner(agents=agents, rooms=rooms, connections=connections)
    owner = rng.choice(agents)
    location = rng.choice(rooms)
    obj = f"{prefix}_object"
    vm = SemanticVM()
    vm.execute(seed_object(obj, owner, location=location))
    state = freeze_state(vm.ledger.project())
    if rng.random() < 0.7:
        goal = Goal(obj, "location", rng.choice(rooms))
    else:
        goal = Goal(obj, "owner", rng.choice(agents))
    return planner, state, goal


def training_rows(seed=0, problems=500):
    rng = random.Random(seed)
    rows = []
    for i in range(problems):
        planner, state, goal = random_problem(
            rng, max_agents=5, max_rooms=6, prefix=f"train{i}"
        )
        result = planner.plan(state, goal, max_depth=7)
        if result is None or not result.steps:
            continue
        current = state
        for optimal in result.steps:
            optimal_next = planner.apply_program(current, optimal.program)
            if optimal_next is None:
                raise RuntimeError("reference plan failed")
            candidates = planner.successors(current)
            for step, nxt in candidates:
                y = 1.0 if nxt == optimal_next else 0.0
                rows.append((features(current, goal, step, nxt, planner), y))
            current = optimal_next
    return rows


def train(seed=0):
    torch.manual_seed(seed)
    rows = training_rows(seed, problems=450)
    x = torch.stack([r[0] for r in rows])
    y = torch.tensor([r[1] for r in rows], dtype=torch.float32)
    model = CandidateScorer(hidden=6)
    opt = torch.optim.Adam(model.parameters(), lr=0.03)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(4.0))
    for _ in range(80):
        opt.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()
        opt.step()
    return model, sum(p.numel() for p in model.parameters())


def run_episode(model, planner, state, goal, max_steps=12):
    current = state
    for _ in range(max_steps):
        if goal.satisfied(current):
            return True
        candidates = planner.successors(current)
        if not candidates:
            return False
        batch = torch.stack(
            [features(current, goal, step, nxt, planner) for step, nxt in candidates]
        )
        with torch.no_grad():
            idx = int(torch.argmax(model(batch)).item())
        current = candidates[idx][1]
    return goal.satisfied(current)


def evaluate(model, seed=999, episodes=300):
    rng = random.Random(seed)
    solved = 0
    attempted = 0
    longest_reference = 0
    for i in range(episodes * 5):
        if attempted >= episodes:
            break
        planner, state, goal = random_problem(
            rng, max_agents=8, max_rooms=10, prefix=f"unseen{i}"
        )
        reference = planner.plan(state, goal, max_depth=12)
        if reference is None or not reference.steps:
            continue
        attempted += 1
        longest_reference = max(longest_reference, len(reference.steps))
        solved += int(run_episode(model, planner, state, goal, max_steps=12))
    return solved / max(attempted, 1), attempted, longest_reference


if __name__ == "__main__":
    model, params = train()
    score, episodes, longest = evaluate(model)
    print(f"parameters={params}")
    print(f"unseen_variable_domain_success={score:.4f} over {episodes} episodes")
    print(f"longest_reference_plan={longest}")
