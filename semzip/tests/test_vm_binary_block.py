import unittest

from semzip.vm_binary_block import decode_semantic_block, encode_semantic_block
from semzip.vm_effects import SetEffect, ShiftEffect
from semzip.vm_patch import SemanticPatch
from semzip.vm_relations import DimensionRegistry


class SemanticBinaryBlockTests(unittest.TestCase):
    def registry(self):
        return DimensionRegistry(("owner", "possessor", "location", "color"))

    def patches(self):
        return (
            SemanticPatch.build(effects=(
                ShiftEffect.build("book", "owner", "john", "mary"),
                ShiftEffect.build("book", "possessor", "john", "mary"),
            )),
            SemanticPatch.build(effects=(
                SetEffect.build("book", "color", "red"),
            )),
        )

    def test_block_round_trip_preserves_atomic_semantics(self):
        registry = self.registry()
        encoded = encode_semantic_block(self.patches(), registry)
        decoded = decode_semantic_block(encoded, registry)
        self.assertEqual(decoded.patches, self.patches())
        self.assertEqual(decoded.registry_signature, registry.signature())
        self.assertGreater(decoded.atom_count, 0)

    def test_wrong_dimension_registry_is_rejected_before_payload_decode(self):
        encoded = encode_semantic_block(self.patches(), self.registry())
        incompatible = DimensionRegistry(("owner", "location", "possessor", "color"))
        with self.assertRaises(ValueError):
            decode_semantic_block(encoded, incompatible)

    def test_truncated_block_is_rejected(self):
        encoded = encode_semantic_block(self.patches(), self.registry())
        with self.assertRaises(ValueError):
            decode_semantic_block(encoded[:-3], self.registry())

    def test_corrupt_magic_is_rejected(self):
        encoded = bytearray(encode_semantic_block(self.patches(), self.registry()))
        encoded[0:4] = b"NOPE"
        with self.assertRaises(ValueError):
            decode_semantic_block(bytes(encoded), self.registry())

    def test_shared_atom_table_avoids_repeating_long_names_per_patch(self):
        registry = self.registry()
        repeated = tuple(
            SemanticPatch.build(effects=(
                ShiftEffect.build(
                    "very_long_object_identifier",
                    "location",
                    f"room{i}",
                    f"room{i + 1}",
                ),
            ))
            for i in range(20)
        )
        encoded = encode_semantic_block(repeated, registry)
        # A deliberately loose guard: the long subject should live in the shared atom
        # table once rather than appearing verbatim in every patch payload.
        self.assertLess(encoded.count(b"very_long_object_identifier"), 2)
        self.assertEqual(decode_semantic_block(encoded, registry).patches, repeated)


if __name__ == "__main__":
    unittest.main()
