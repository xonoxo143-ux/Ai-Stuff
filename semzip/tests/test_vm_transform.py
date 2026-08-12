import unittest

from semzip.vm_compile import seed_object
from semzip.vm_effects import ShiftEffect
from semzip.vm_kernel import K_REQUIRE, K_SHIFT, SemanticVM
from semzip.vm_patch import SemanticPatch, compile_semantic_patch
from semzip.vm_transform import (
    SemanticTransform,
    StateConstraint,
    compile_semantic_transform,
    parallel_transforms,
)


class SemanticTransformTests(unittest.TestCase):
    def possession_shift(self):
        return SemanticPatch.build(effects=(
            ShiftEffect.build("book", "possessor", "john", "mary"),
        ))

    def test_shift_source_is_its_own_precondition(self):
        program = compile_semantic_patch(self.possession_shift())
        self.assertEqual(tuple(ins.opcode for ins in program.instructions), (K_SHIFT,))

    def test_redundant_explicit_constraint_is_canonicalized_away(self):
        transform = SemanticTransform.build(
            self.possession_shift(),
            constraints=(StateConstraint.build("book", "possessor", "john"),),
        )
        self.assertEqual(transform.constraints, ())

    def test_extra_guard_remains_explicit(self):
        transform = SemanticTransform.build(
            self.possession_shift(),
            constraints=(StateConstraint.build("book", "owner", "john"),),
        )
        program = compile_semantic_transform(transform)
        self.assertEqual(tuple(ins.opcode for ins in program.instructions), (K_REQUIRE, K_SHIFT))

        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(program)
        self.assertEqual(vm.ledger.current("book", "owner"), "john")
        self.assertEqual(vm.ledger.current("book", "possessor"), "mary")

    def test_constraint_contradicting_shift_source_is_impossible(self):
        with self.assertRaises(ValueError):
            SemanticTransform.build(
                self.possession_shift(),
                constraints=(StateConstraint.build("book", "possessor", "alice"),),
            )

    def test_parallel_transform_combines_independent_guards_and_effects(self):
        possession = SemanticTransform.build(
            self.possession_shift(),
            constraints=(StateConstraint.build("book", "owner", "john"),),
        )
        location = SemanticTransform.build(
            SemanticPatch.build(effects=(
                ShiftEffect.build("book", "location", "desk", "bag"),
            ))
        )
        combined = parallel_transforms(possession, location)
        self.assertEqual(len(combined.patch.effects), 2)
        self.assertEqual(combined.constraints[0].key(), ("book", "owner", "john"))

    def test_transform_identity(self):
        identity = parallel_transforms()
        self.assertTrue(identity.patch.is_empty)
        self.assertEqual(identity.constraints, ())


if __name__ == "__main__":
    unittest.main()
