import unittest

from semzip.vm_compile import seed_object
from semzip.vm_delta import RelationDelta, SemanticDeltaFrame, compile_delta_frame
from semzip.vm_kernel import SemanticVM


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

    def test_obligation_requires_possession_delta(self):
        frame = SemanticDeltaFrame(
            RelationDelta.build("book", "john", "mary", ("owner",)),
            return_obligation=True,
        )
        with self.assertRaises(ValueError):
            compile_delta_frame(frame)

    def test_unknown_relation_is_rejected(self):
        with self.assertRaises(ValueError):
            RelationDelta.build("book", "john", "mary", ("magic",))


if __name__ == "__main__":
    unittest.main()
