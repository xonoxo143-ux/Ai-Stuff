import unittest

from semzip.vm_binary import AtomTable, decode_patch_binary, decode_varint, encode_patch_binary, encode_varint
from semzip.vm_delta import RelationDelta
from semzip.vm_patch import ReturnObligation, SemanticPatch, StateAssignment, StateClear
from semzip.vm_relations import RelationRegistry


class SemanticBinaryCodecTests(unittest.TestCase):
    def registry(self):
        return RelationRegistry(("owner", "possessor", "location", "color", "tag"))

    def mixed_patch(self):
        return SemanticPatch.build(
            (
                RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
                RelationDelta.build("crate", "room1", "room2", ("location",)),
            ),
            assignments=(StateAssignment.build("book", "color", "red"),),
            clears=(StateClear.build("book", "tag"),),
            return_obligations=(ReturnObligation.build("tool", "mary", "john"),),
        )

    def test_varint_round_trip(self):
        for value in (0, 1, 127, 128, 255, 16384, 2**32):
            encoded = encode_varint(value)
            decoded, offset = decode_varint(encoded)
            self.assertEqual(decoded, value)
            self.assertEqual(offset, len(encoded))

    def test_patch_round_trip(self):
        registry = self.registry()
        atoms = AtomTable()
        original = self.mixed_patch()
        encoded = encode_patch_binary(original, atoms, registry)
        decoded = decode_patch_binary(encoded, atoms, registry)
        self.assertEqual(decoded, original)

    def test_atom_table_reuses_strings_across_patches(self):
        registry = self.registry()
        atoms = AtomTable()
        first = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner",)),
        ))
        second = SemanticPatch.build((
            RelationDelta.build("book", "mary", "john", ("owner",)),
        ))
        encode_patch_binary(first, atoms, registry)
        size_after_first = len(atoms)
        encode_patch_binary(second, atoms, registry)
        self.assertEqual(len(atoms), size_after_first)

    def test_small_transfer_payload_is_tiny_after_atom_interning(self):
        registry = self.registry()
        atoms = AtomTable()
        patch = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
        ))
        encoded = encode_patch_binary(patch, atoms, registry)
        # version + record count + two 5-varint transition records; all IDs are <128.
        self.assertLessEqual(len(encoded), 12)
        self.assertEqual(decode_patch_binary(encoded, atoms, registry), patch)

    def test_unregistered_dimension_is_rejected(self):
        registry = self.registry()
        atoms = AtomTable()
        patch = SemanticPatch.build((
            RelationDelta.build("switch", "off", "on", ("powered",)),
        ))
        with self.assertRaises(ValueError):
            encode_patch_binary(patch, atoms, registry)

    def test_wrong_format_version_is_rejected(self):
        registry = self.registry()
        atoms = AtomTable()
        patch = SemanticPatch.build(assignments=(StateAssignment.build("book", "color", "red"),))
        encoded = bytearray(encode_patch_binary(patch, atoms, registry))
        encoded[0] = 99
        with self.assertRaises(ValueError):
            decode_patch_binary(bytes(encoded), atoms, registry)

    def test_trailing_bytes_are_rejected(self):
        registry = self.registry()
        atoms = AtomTable()
        patch = SemanticPatch.build(assignments=(StateAssignment.build("book", "color", "red"),))
        encoded = encode_patch_binary(patch, atoms, registry) + b"\x00"
        with self.assertRaises(ValueError):
            decode_patch_binary(encoded, atoms, registry)


if __name__ == "__main__":
    unittest.main()
