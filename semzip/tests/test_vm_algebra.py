import unittest

from semzip.vm_algebra import (
    NonInvertibleMeaningError,
    equivalent_under_projection,
    inverse_patch,
    parallel,
    sequential,
)
from semzip.vm_compile import seed_object
from semzip.vm_effects import SetEffect, ShiftEffect
from semzip.vm_kernel import SemanticVM
from semzip.vm_patch import SemanticPatch, compile_semantic_patch
from semzip.vm_sequence import compile_semantic_sequence


class SemanticAlgebraTests(unittest.TestCase):
    def shift(self, dimension, source, destination):
        return SemanticPatch.build(effects=(
            ShiftEffect.build("book", dimension, source, destination),
        ))

    def test_parallel_has_explicit_identity(self):
        a = self.shift("owner", "john", "mary")
        self.assertEqual(parallel(SemanticPatch.empty(), a), a)
        self.assertEqual(parallel(a, SemanticPatch.empty()), a)
        self.assertTrue(parallel().is_empty)

    def test_parallel_is_commutative_when_compatible(self):
        a = self.shift("owner", "john", "mary")
        b = self.shift("possessor", "john", "mary")
        self.assertEqual(parallel(a, b), parallel(b, a))

    def test_parallel_is_associative_when_compatible(self):
        a = self.shift("owner", "john", "mary")
        b = self.shift("possessor", "john", "mary")
        c = SemanticPatch.build(effects=(SetEffect.build("book", "color", "red"),))
        self.assertEqual(parallel(parallel(a, b), c), parallel(a, parallel(b, c)))

    def test_parallel_is_idempotent(self):
        a = self.shift("owner", "john", "mary")
        self.assertEqual(parallel(a, a), a)

    def test_parallel_conflict_is_undefined(self):
        a = self.shift("owner", "john", "mary")
        b = self.shift("owner", "john", "alice")
        with self.assertRaises(ValueError):
            parallel(a, b)

    def test_sequence_has_identity_and_is_associative(self):
        a = self.shift("owner", "john", "mary")
        b = self.shift("owner", "mary", "alice")
        c = self.shift("owner", "alice", "bob")
        self.assertEqual(sequential().steps, ())
        self.assertEqual(sequential(sequential(a, b), c), sequential(a, sequential(b, c)))

    def test_sequence_is_not_commutative(self):
        a = self.shift("owner", "john", "mary")
        b = self.shift("owner", "mary", "alice")
        self.assertNotEqual(sequential(a, b).fingerprint(), sequential(b, a).fingerprint())

    def test_shift_has_intrinsic_inverse(self):
        a = self.shift("owner", "john", "mary")
        inverse = inverse_patch(a)
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(compile_semantic_sequence(sequential(a, inverse)))
        self.assertEqual(vm.ledger.current("book", "owner"), "john")

    def test_set_is_not_intrinsically_invertible(self):
        patch = SemanticPatch.build(effects=(SetEffect.build("book", "color", "red"),))
        with self.assertRaises(NonInvertibleMeaningError):
            inverse_patch(patch)

    def test_projection_equivalence_is_layered(self):
        gift = parallel(
            self.shift("owner", "john", "mary"),
            self.shift("possessor", "john", "mary"),
        )
        possession_only = self.shift("possessor", "john", "mary")
        self.assertTrue(
            equivalent_under_projection(
                gift, possession_only, dimensions=("possessor",)
            )
        )
        self.assertFalse(gift.transition_equivalent(possession_only))

    def test_grouped_relation_delta_is_not_semantic_identity(self):
        # The canonical patch stores one atomic effect per dimension regardless of
        # whether a compatibility view later groups them for display/storage.
        patch = parallel(
            self.shift("owner", "john", "mary"),
            self.shift("possessor", "john", "mary"),
        )
        self.assertEqual(len(patch.effects), 2)
        self.assertEqual(len(patch.deltas), 1)

    def test_identity_program_executes_without_mutation(self):
        vm = SemanticVM()
        before = vm.ledger.clock
        vm.execute(compile_semantic_patch(SemanticPatch.empty()))
        self.assertEqual(vm.ledger.clock, before)


if __name__ == "__main__":
    unittest.main()
