import unittest

from semzip.vm_compile import seed_object
from semzip.vm_delta import RelationDelta, SemanticDeltaFrame, compile_delta_frame
from semzip.vm_kernel import SemanticVM
from semzip.vm_patch import (
    ReturnObligation,
    SemanticPatch,
    compile_semantic_patch,
    compose_semantic_patches,
)


class SemanticPatchTests(unittest.TestCase):
    def test_patch_supports_more_than_two_deltas(self):
        patch = SemanticPatch.build((
            RelationDelta.build("a", "x", "y", ("owner",)),
            RelationDelta.build("b", "y", "x", ("owner",)),
            RelationDelta.build("c", "room1", "room2", ("location",)),
        ))
        self.assertEqual(len(patch.deltas), 3)

    def test_patch_order_is_not_semantic(self):
        a = RelationDelta.build("book", "john", "mary", ("owner", "possessor"))
        b = RelationDelta.build("coin", "mary", "john", ("owner", "possessor"))
        left = SemanticPatch.build((a, b))
        right = SemanticPatch.build((b, a))
        self.assertEqual(left, right)
        self.assertTrue(left.transition_equivalent(right))

    def test_duplicate_subject_relation_is_rejected(self):
        with self.assertRaises(ValueError):
            SemanticPatch.build((
                RelationDelta.build("book", "john", "mary", ("owner",)),
                RelationDelta.build("book", "john", "alice", ("owner",)),
            ))

    def test_patch_executes_exchange_and_movement_atomically(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(seed_object("coin", "mary"))
        from semzip.vm_kernel import Instruction, Program, K_SET
        vm.execute(Program.build((Instruction.make(K_SET, "crate", "location", "room1"),)))
        patch = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
            RelationDelta.build("coin", "mary", "john", ("owner", "possessor")),
            RelationDelta.build("crate", "room1", "room2", ("location",)),
        ))
        vm.execute(compile_semantic_patch(patch))
        self.assertEqual(vm.ledger.current("book", "owner"), "mary")
        self.assertEqual(vm.ledger.current("coin", "owner"), "john")
        self.assertEqual(vm.ledger.current("crate", "location"), "room2")

    def test_explicit_return_obligation_is_not_bound_to_delta_order(self):
        patch = SemanticPatch.build(
            (RelationDelta.build("book", "john", "mary", ("possessor",)),),
            return_obligations=(ReturnObligation.build("book", "mary", "john"),),
        )
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(compile_semantic_patch(patch))
        self.assertEqual(vm.ledger.current("book", "owner"), "john")
        self.assertEqual(vm.ledger.current("book", "possessor"), "mary")
        self.assertEqual(vm.ledger.current("obligation:return:book:mary:john", "status"), "active")

    def test_legacy_delta_frame_maps_to_same_patch_effect(self):
        primary = RelationDelta.build("book", "john", "mary", ("possessor",))
        frame = SemanticDeltaFrame(primary, return_obligation=True)
        legacy = compile_delta_frame(frame)
        patch = compile_semantic_patch(frame.to_patch())
        self.assertEqual(legacy.instructions, patch.instructions)

    def test_composition_unions_independent_semantic_dimensions(self):
        owner = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner",)),
        ))
        possession = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("possessor",)),
        ))
        combined = compose_semantic_patches(owner, possession)
        expected = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
        ))
        self.assertEqual(combined, expected)

    def test_composition_deduplicates_identical_meaning(self):
        patch = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner",)),
        ))
        self.assertEqual(compose_semantic_patches(patch, patch), patch)

    def test_composition_rejects_conflicting_meanings(self):
        mary = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner",)),
        ))
        alice = SemanticPatch.build((
            RelationDelta.build("book", "john", "alice", ("owner",)),
        ))
        with self.assertRaises(ValueError):
            compose_semantic_patches(mary, alice)

    def test_composition_unions_reciprocal_atomic_patches(self):
        owner = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner",)),
            RelationDelta.build("coin", "mary", "john", ("owner",)),
        ))
        possession = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("possessor",)),
            RelationDelta.build("coin", "mary", "john", ("possessor",)),
        ))
        combined = compose_semantic_patches(owner, possession)
        self.assertEqual(len(combined.deltas), 2)
        self.assertEqual(set(combined.deltas[0].relations + combined.deltas[1].relations), {"owner", "possessor"})


if __name__ == "__main__":
    unittest.main()
