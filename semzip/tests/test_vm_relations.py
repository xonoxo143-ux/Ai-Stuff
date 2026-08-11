import unittest

from semzip.vm_relations import DEFAULT_RELATION_REGISTRY, RelationRegistry


class RelationRegistryTests(unittest.TestCase):
    def test_default_ids_are_stable_for_current_library(self):
        self.assertEqual(DEFAULT_RELATION_REGISTRY.resolve_id(0).name, "owner")
        self.assertEqual(DEFAULT_RELATION_REGISTRY.resolve_id(1).name, "possessor")
        self.assertEqual(DEFAULT_RELATION_REGISTRY.resolve_id(2).name, "location")

    def test_registry_can_grow_without_kernel_change(self):
        registry = RelationRegistry(("owner",))
        spec = registry.register("powered")
        self.assertEqual(spec.relation_id, 1)
        self.assertEqual(registry.resolve_name("powered"), spec)

    def test_signature_changes_when_relation_vocabulary_changes(self):
        a = RelationRegistry(("owner", "possessor"))
        b = RelationRegistry(("owner", "possessor", "location"))
        self.assertNotEqual(a.signature(), b.signature())

    def test_explicit_ids_are_preserved(self):
        registry = RelationRegistry()
        registry.register("location", relation_id=7)
        self.assertEqual(registry.resolve_id(7).name, "location")

    def test_duplicate_id_is_rejected(self):
        registry = RelationRegistry()
        registry.register("owner", relation_id=0)
        with self.assertRaises(ValueError):
            registry.register("possessor", relation_id=0)


if __name__ == "__main__":
    unittest.main()
