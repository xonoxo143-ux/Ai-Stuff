from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semzip.vm_compile import lend, seed_object
from semzip.vm_deltas import discover_delta_macros, recursive_factorizations
from semzip.vm_kernel import SemanticVM
from semzip.vm_lab import balanced_experiences, freeze_state
from semzip.vm_macros import learn_library
from semzip.vm_plan import Goal, SymbolicPlanner


def main():
    vm = SemanticVM()
    vm.execute(seed_object("book", "john", location="room0"))
    vm.execute(lend("john", "mary", "book"))
    assert vm.ledger.current("book", "owner") == "john"
    assert vm.ledger.current("book", "possessor") == "mary"

    experiences = balanced_experiences(1000, seed=8)
    delta_report = discover_delta_macros(experiences, min_experiences=20)
    assert delta_report.best is not None
    exact_recursive = [
        x for x in recursive_factorizations(delta_report)
        if x[2].exact and x[2].uses >= 2
    ]
    assert exact_recursive

    library = learn_library([x.program for x in experiences], max_macros=6, min_occurrences=10)
    assert library.savings > 0

    planner = SymbolicPlanner(
        agents=("john",),
        rooms=("room0", "room1", "room2", "room3"),
        connections=(("room0", "room1"), ("room1", "room2"), ("room2", "room3")),
    )
    world = SemanticVM()
    world.execute(seed_object("key", "john", location="room0"))
    plan = planner.plan(
        freeze_state(world.ledger.project()),
        Goal("key", "location", "room3"),
        max_depth=4,
    )
    assert plan is not None and len(plan.steps) == 3

    print("semvm_progress_gate=PASS")
    print(f"delta_base_cost={delta_report.base_cost}")
    print(f"best_delta_macro_width={len(delta_report.best.pattern)}")
    print(f"best_delta_macro_savings={delta_report.best.net_savings}")
    print(f"recursive_exact_factorizations={len(exact_recursive)}")
    print(f"program_library_savings={library.savings}")
    print(f"planner_steps={len(plan.steps)}")


if __name__ == "__main__":
    main()
