import unittest

from semzip.vm_delta import RelationDelta
from semzip.vm_patch import SemanticPatch, StateAssignment
from semzip.vm_patch_codec import decode_patch, encode_patch
from semzip.vm_patch_mdl import PatchMacro, patch_pattern


def transfer(subject, source, destination):
    return SemanticPatch.build((
        RelationDelta.build(subject, source, destination, ("owner", "possessor")),
    ))


def exchange(goods, seller, buyer, payment):
    return SemanticPatch.build((
        RelationDelta.build(goods, seller, buyer, ("owner", "possessor")),
        RelationDelta.build(payment, buyer, seller, ("owner", "possessor")),
    ))


class PatchCodecTests(unittest.TestCase):
    def transfer_macro(self):
        return PatchMacro(
            "M_transfer",
            patch_pattern(transfer("thing", "source", "destination")).pattern,
        )

    def test_exchange_encodes_as_two_transfer_calls(self):
        original = exchange("book", "john", "mary", "coin")
        encoded = encode_patch(original, (self.transfer_macro(),))
        self.assertEqual(len(encoded.macro_calls), 2)
        self.assertEqual(encoded.residual_records, ())
        self.assertGreater(encoded.savings, 0)
        self.assertEqual(decode_patch(encoded, (self.transfer_macro(),)), original)

    def test_single_transfer_round_trip(self):
        original = transfer("key", "alice", "bob")
        macro = self.transfer_macro()
        encoded = encode_patch(original, (macro,))
        self.assertEqual(len(encoded.macro_calls), 1)
        self.assertEqual(decode_patch(encoded, (macro,)), original)

    def test_unmatched_static_effect_remains_residual_and_round_trips(self):
        original = SemanticPatch.build(
            assignments=(StateAssignment.build("book", "color", "red"),)
        )
        macro = self.transfer_macro()
        encoded = encode_patch(original, (macro,))
        self.assertEqual(encoded.macro_calls, ())
        self.assertEqual(decode_patch(encoded, (macro,)), original)
        self.assertEqual(encoded.savings, 0)

    def test_mixed_patch_uses_macro_and_preserves_residual(self):
        original = SemanticPatch.build(
            (
                RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
            ),
            assignments=(StateAssignment.build("book", "color", "red"),),
        )
        macro = self.transfer_macro()
        encoded = encode_patch(original, (macro,))
        self.assertEqual(len(encoded.macro_calls), 1)
        self.assertTrue(encoded.residual_records)
        self.assertEqual(decode_patch(encoded, (macro,)), original)

    def test_missing_macro_fails_decode(self):
        macro = self.transfer_macro()
        encoded = encode_patch(transfer("book", "john", "mary"), (macro,))
        with self.assertRaises(KeyError):
            decode_patch(encoded, ())

    def test_duplicate_macro_ids_are_rejected_on_decode(self):
        macro = self.transfer_macro()
        encoded = encode_patch(transfer("book", "john", "mary"), (macro,))
        duplicate = PatchMacro("M_transfer", macro.pattern)
        with self.assertRaises(ValueError):
            decode_patch(encoded, (macro, duplicate))


if __name__ == "__main__":
    unittest.main()
