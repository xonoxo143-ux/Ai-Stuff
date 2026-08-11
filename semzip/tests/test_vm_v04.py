import json
import unittest

from semzip.vm_bridge import VMProposalError, program_from_json
from semzip.vm_compile import give, lend, seed_object, sell
from semzip.vm_deltas import discover_delta_macros, recursive_factorizations
from semzip.vm_equivalence import EquivalenceLevel, RichExpression, equivalent
from semzip.vm_kernel import SemanticVM, VMExecutionError
from semzip.vm_lab import balanced_experiences, freeze_state
from semzip.vm_ledger import EventLedger
from semzip.vm_macros import learn_library
from semzip.vm_minds import MindSpace
from semzip.vm_plan import Goal, SymbolicPlanner


class SemVMV04Gate(unittest.TestCase):
    def test_event_ledger_projects_and_branches(self):
        ledger = EventLedger()
        ledger.append_state("key", "location", "kitchen")
        t = ledger.clock
        ledger.fork("what_if")
        ledger.transition("key", "location", "kitchen", "garage", branch="what_if")
        self.assertEqual(ledger.current("key", "location"), "kitchen")
        self.assertEqual(ledger.current("key", "location", branch="what_if"), "garage")
        self.assertEqual(ledger.current_at("key", "location", t), "kitchen")

    def test_observation_is_evidence_not_reality(self):
        ledger = EventLedger()
        ledger.append_state("key", "location", "kitchen")
        obs = ledger.observe("key", "location", "garage", confidence=0.72, provenance="camera")
        self.assertEqual(ledger.current("key", "location"), "kitchen")
        self.assertEqual(ledger.best_observation("key", "location"), obs)
        ledger.accept_observation(obs)
        self.assertEqual(ledger.current("key", "location"), "garage")

    def test_lending_preserves_ownership(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(lend("john", "mary", "book"))
        self.assertEqual(vm.ledger.current("book", "owner"), "john")
        self.assertEqual(vm.ledger.current("book", "possessor"), "mary")

    def test_failed_compound_program_is_atomic(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        event_count = len(vm.ledger.events)
        with self.assertRaises(VMExecutionError):
            vm.execute(sell("john", "mary", "book", "missing_cash"))
        self.assertEqual(vm.ledger.current("book", "owner"), "john")
        self.assertEqual(len(vm.ledger.events), event_count)

    def test_delta_discovery_is_blind_to_action_labels(self):
        from semzip.vm_lab import Experience
        xs = balanced_experiences(600, seed=4)
        relabeled = tuple(Experience("nonsense", x.program, x.before, x.after) for x in xs)
        a = discover_delta_macros(xs, min_experiences=15)
        b = discover_delta_macros(relabeled, min_experiences=15)
        self.assertIsNotNone(a.best)
        self.assertEqual(a.best.pattern, b.best.pattern)
        self.assertEqual(a.best.net_savings, b.best.net_savings)

    def test_learned_exchange_factors_into_smaller_pattern(self):
        report = discover_delta_macros(
            balanced_experiences(1000, seed=8), min_experiences=20
        )
        exact = [x for x in recursive_factorizations(report) if x[2].exact and x[2].uses >= 2]
        self.assertTrue(exact)

    def test_program_macro_library_is_lossless_and_cheaper(self):
        xs = balanced_experiences(500, seed=9)
        corpus = tuple(x.program for x in xs)
        learned = learn_library(corpus, max_macros=6, min_occurrences=8)
        self.assertGreater(learned.savings, 0)
        for p in corpus[:20]:
            expanded = learned.library.expand(learned.library.encode(p))
            self.assertEqual(expanded.instructions, p.instructions)

    def test_equivalence_can_differ_above_same_transition(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        p = give("john", "mary", "book")
        a = RichExpression(p, proposition="transfer", perspective="john", surface="John gave Mary the book")
        b = RichExpression(p, proposition="transfer", perspective="mary", surface="Mary received the book from John")
        self.assertFalse(equivalent(a, b, level=EquivalenceLevel.SURFACE))
        self.assertTrue(equivalent(a, b, level=EquivalenceLevel.PROPOSITION))
        self.assertTrue(equivalent(a, b, level=EquivalenceLevel.TRANSITION, seed=vm.ledger))

    def test_symbolic_planner_solves_multistep_goal(self):
        planner = SymbolicPlanner(
            agents=("john",),
            rooms=("r0", "r1", "r2", "r3"),
            connections=(("r0", "r1"), ("r1", "r2"), ("r2", "r3")),
        )
        vm = SemanticVM()
        vm.execute(seed_object("key", "john", location="r0"))
        result = planner.plan(freeze_state(vm.ledger.project()), Goal("key", "location", "r3"), max_depth=4)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.steps), 3)

    def test_mind_can_be_stale_without_corrupting_reality(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        minds = MindSpace(vm.ledger)
        minds.register("bob")
        vm.execute(give("john", "mary", "book"))
        belief = minds.belief("bob", "book", "owner")
        self.assertEqual(belief.value, "john")
        self.assertFalse(belief.agrees_with_reality)
        self.assertEqual(vm.ledger.current("book", "owner"), "mary")

    def test_external_program_bridge_rejects_invented_opcode(self):
        with self.assertRaises(VMProposalError):
            program_from_json(json.dumps({"instructions": [{"opcode": "MAGIC", "args": []}]}))


if __name__ == "__main__":
    unittest.main()
