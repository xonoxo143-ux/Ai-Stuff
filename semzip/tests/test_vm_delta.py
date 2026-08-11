import unittest

from semzip.vm_compile import seed_object
from semzip.vm_delta import RelationDelta, SemanticDeltaFrame, compile_delta_frame
from semzip.vm_kernel import SemanticVM
from semzip.vm_relations import DEFAULT_RELATION_REGISTRY


class SemanticDeltaCompilerTests(unittest.TestCase):
    def test_gift_is_relation_delta_not_lexical_opcode(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        frame = SemanticDeltaFrame(
            RelationDelta.build("book", "john", "mary", ("owner", "possessor"))
        )
        vm.execute(compile_delta_frame(frame))
        self.assertEqual(vm.ledger.current("book", "owner"), "mary")
        self.assertEqual(vm.ledger.current("book", "possessor"), "mary")

    def test_loan_preserves_owner_and_creates_return_obligation(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        frame = SemanticDeltaFrame(
            RelationDelta.build("book", "john", "mary", ("possessor",)),
            return_obligation=True,
        )
        vm.execute(compile_delta_frame(frame))
        self.assertEqual(vm.ledger.current("book", "owner"), "john")
        self.assertEqual(vm.ledger.current("book", "possessor"), "mary")
        self.assertEqual(
            vm.ledger.current("obligation:return:book:mary:john", "status"),
            "active",
        )

    def test_exchange_is_two_relation_deltas(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(seed_object("coin", "mary"))
        frame = SemanticDeltaFrame(
            RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
            secondary=RelationDelta.build("coin", "mary", "john", ("owner", "possessor")),
        )
        vm.execute(compile_delta_frame(frame))
        self.assertEqual(vm.ledger.current("book", "owner"), "mary")
        self.assertEqual(vm.ledger.current("coin", "owner"), "john")

    def test_reciprocal_delta_order_does_not_change_transition_identity(self):
        goods = RelationDelta.build("book", "john", "mary", ("possessor", "owner"))
        payment = RelationDelta.build("coin", "mary", "john", ("owner", "possessor"))
        left = SemanticDeltaFrame(goods, secondary=payment)
        right = SemanticDeltaFrame(payment, secondary=goods)
        self.assertTrue(left.transition_equivalent(right))
        self.assertEqual(left.transition_fingerprint(), right.transition_fingerprint())

    def test_relation_order_is_canonical(self):
        left = RelationDelta.build("book", "john", "mary", ("possessor", "owner"))
        right = RelationDelta.build("book", "john", "mary", ("owner", "possessor"))
        self.assertEqual(left, right)

    def test_legacy_obligation_must_be_anchored_to_possession_primary(self):
        borrowed = RelationDelta.build("book", "john", "mary", ("possessor",))
        other = RelationDelta.build("coin", "mary", "john", ("owner",))
        valid = SemanticDeltaFrame(borrowed, secondary=other, return_obligation=True)
        invalid = SemanticDeltaFrame(other, secondary=borrowed, return_obligation=True)
        self.assertTrue(valid.to_patch().return_obligations)
        with self.assertRaises(ValueError):
            invalid.to_patch()

    def test_obligation_requires_possession_delta(self):
        frame = SemanticDeltaFrame(
            RelationDelta.build("book", "john", "mary", ("owner",)),
            return_obligation=True,
        )
        with self.assertRaises(ValueError):
            compile_delta_frame(frame)

    def test_vm_relation_delta_is_not_limited_to_toy_vocabulary(self):
        delta = RelationDelta.build("switch", "off", "on", ("powered",))
        self.assertEqual(delta.relations, ("powered",))

    def test_compiler_registry_rejects_unregistered_relation(self):
        with self.assertRaises(ValueError):
            RelationDelta.build(
                "book", "john", "mary", ("magic",),
                registry=DEFAULT_RELATION_REGISTRY,
            )


if __name__ == "__main__":
    unittest.main()
