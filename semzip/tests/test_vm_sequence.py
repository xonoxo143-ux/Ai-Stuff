import unittest

from semzip.vm_compile import seed_object
from semzip.vm_delta import RelationDelta
from semzip.vm_kernel import SemanticVM
from semzip.vm_patch import SemanticPatch, compose_semantic_patches
from semzip.vm_sequence import SemanticSequence, compile_semantic_sequence


class SemanticSequenceTests(unittest.TestCase):
    def transfer(self, source, destination):
        return SemanticPatch.build((
            RelationDelta.build("book", source, destination, ("owner", "possessor")),
        ))

    def test_ordered_transfers_are_not_parallel_conflicts(self):
        first = self.transfer("john", "mary")
        second = self.transfer("mary", "alice")
        with self.assertRaises(ValueError):
            compose_semantic_patches(first, second)

        sequence = SemanticSequence.build((first, second))
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        vm.execute(compile_semantic_sequence(sequence))
        self.assertEqual(vm.ledger.current("book", "owner"), "alice")
        self.assertEqual(vm.ledger.current("book", "possessor"), "alice")

    def test_sequence_order_is_semantic(self):
        first = self.transfer("john", "mary")
        second = self.transfer("mary", "alice")
        forward = SemanticSequence.build((first, second))
        reverse = SemanticSequence.build((second, first))
        self.assertNotEqual(forward.fingerprint(), reverse.fingerprint())

    def test_sequence_compiles_as_one_transaction(self):
        first = self.transfer("john", "mary")
        # Invalid second step expects the wrong intermediate owner.
        bad = self.transfer("bob", "alice")
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        with self.assertRaises(Exception):
            vm.execute(compile_semantic_sequence(SemanticSequence.build((first, bad))))
        # First step did not leak through the failed compound utterance.
        self.assertEqual(vm.ledger.current("book", "owner"), "john")
        self.assertEqual(vm.ledger.current("book", "possessor"), "john")

    def test_append_and_extend_preserve_order(self):
        a = self.transfer("john", "mary")
        b = self.transfer("mary", "alice")
        c = self.transfer("alice", "bob")
        sequence = SemanticSequence.build((a,)).append(b)
        self.assertEqual(sequence.steps, (a, b))
        self.assertEqual(sequence.extend(SemanticSequence.build((c,))).steps, (a, b, c))


if __name__ == "__main__":
    unittest.main()
