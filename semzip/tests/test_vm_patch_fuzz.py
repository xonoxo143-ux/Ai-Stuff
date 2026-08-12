import random
import unittest

from semzip.vm_kernel import Instruction, Program, SemanticVM, K_SET
from semzip.vm_delta import RelationDelta
from semzip.vm_patch import (
    SemanticPatch,
    StateAssignment,
    StateClear,
    compile_semantic_patch,
    compose_semantic_patches,
)
from semzip.vm_sequence import SemanticSequence, compile_semantic_sequence


class PatchRandomizedRegressionTests(unittest.TestCase):
    def seed(self, vm, facts):
        vm.execute(Program.build(tuple(
            Instruction.make(K_SET, subject, dimension, value)
            for (subject, dimension), value in facts.items()
        )))

    def test_random_disjoint_parallel_composition_matches_one_patch(self):
        rng = random.Random(12345)
        dimensions = ("owner", "possessor", "location", "powered", "color")
        subjects = tuple(f"object{i}" for i in range(8))
        values = tuple(f"value{i}" for i in range(12))

        for _case in range(100):
            selected = rng.sample(
                [(subject, dimension) for subject in subjects for dimension in dimensions],
                8,
            )
            initial = {key: rng.choice(values) for key in selected}
            atomic = []
            expected = dict(initial)

            for index, (subject, dimension) in enumerate(selected):
                current = initial[(subject, dimension)]
                if index % 3 == 0:
                    destination = rng.choice(tuple(value for value in values if value != current))
                    patch = SemanticPatch.build((
                        RelationDelta.build(subject, current, destination, (dimension,)),
                    ))
                    expected[(subject, dimension)] = destination
                elif index % 3 == 1:
                    value = rng.choice(values)
                    patch = SemanticPatch.build(
                        assignments=(StateAssignment.build(subject, dimension, value),)
                    )
                    expected[(subject, dimension)] = value
                else:
                    patch = SemanticPatch.build(
                        clears=(StateClear.build(subject, dimension),)
                    )
                    expected[(subject, dimension)] = None
                atomic.append(patch)

            combined = compose_semantic_patches(*atomic)
            vm = SemanticVM()
            self.seed(vm, initial)
            vm.execute(compile_semantic_patch(combined))
            for key, value in expected.items():
                self.assertEqual(vm.ledger.current(*key), value)

    def test_random_composition_is_order_independent_for_disjoint_effects(self):
        rng = random.Random(54321)
        patches = tuple(
            SemanticPatch.build(assignments=(
                StateAssignment.build(f"item{i}", "value", f"v{i}"),
            ))
            for i in range(12)
        )
        expected = compose_semantic_patches(*patches)
        for _ in range(50):
            shuffled = list(patches)
            rng.shuffle(shuffled)
            self.assertEqual(compose_semantic_patches(*shuffled), expected)

    def test_random_ordered_chain_reaches_last_value(self):
        rng = random.Random(8128)
        for _case in range(50):
            chain = [f"v{rng.randrange(100000)}" for _ in range(7)]
            # Avoid accidental duplicate adjacent states.
            for index in range(1, len(chain)):
                if chain[index] == chain[index - 1]:
                    chain[index] += "x"
            steps = tuple(
                SemanticPatch.build((
                    RelationDelta.build("thing", source, destination, ("state",)),
                ))
                for source, destination in zip(chain, chain[1:])
            )
            vm = SemanticVM()
            self.seed(vm, {("thing", "state"): chain[0]})
            vm.execute(compile_semantic_sequence(SemanticSequence.build(steps)))
            self.assertEqual(vm.ledger.current("thing", "state"), chain[-1])

    def test_bad_random_chain_rolls_back_all_steps(self):
        rng = random.Random(9001)
        for _case in range(30):
            start = f"s{rng.randrange(100000)}"
            middle = f"m{rng.randrange(100000)}"
            wrong = f"w{rng.randrange(100000)}"
            end = f"e{rng.randrange(100000)}"
            first = SemanticPatch.build((
                RelationDelta.build("thing", start, middle, ("state",)),
            ))
            bad = SemanticPatch.build((
                RelationDelta.build("thing", wrong, end, ("state",)),
            ))
            vm = SemanticVM()
            self.seed(vm, {("thing", "state"): start})
            with self.assertRaises(Exception):
                vm.execute(compile_semantic_sequence(SemanticSequence.build((first, bad))))
            self.assertEqual(vm.ledger.current("thing", "state"), start)


if __name__ == "__main__":
    unittest.main()
