import unittest

from semzip.vm_identity import AmbiguousEntityIdentity, IdentityStore
from semzip.vm_mentions import slotize_mentions


class IdentityStoreTests(unittest.TestCase):
    def test_unknown_repeated_surface_mentions_stay_distinct(self):
        store = IdentityStore()
        slotted = slotize_mentions(
            "Mary met Mary",
            ((0, 4), (9, 13)),
        )
        resolved = store.resolve_slotted(slotted)
        self.assertEqual(resolved[0].status, "provisional")
        self.assertEqual(resolved[1].status, "provisional")
        self.assertNotEqual(resolved[0].entity_id, resolved[1].entity_id)

    def test_explicit_alias_commitment_links_future_mentions(self):
        store = IdentityStore()
        store.register_entity("person:mary", aliases=("Mary",))
        first, status = store.resolve_surface("mary")
        second, second_status = store.resolve_surface("  MARY  ")
        self.assertEqual(first, "person:mary")
        self.assertEqual(second, "person:mary")
        self.assertEqual(status, "known")
        self.assertEqual(second_status, "known")

    def test_unknown_surface_is_not_silently_committed_as_alias(self):
        store = IdentityStore()
        first, _ = store.resolve_surface("the book")
        second, _ = store.resolve_surface("the book")
        self.assertNotEqual(first, second)
        self.assertEqual(store.alias_candidates("the book"), ())

    def test_ambiguous_alias_remains_explicit(self):
        store = IdentityStore()
        store.register_entity("person:alex-1", aliases=("Alex",))
        store.register_entity("person:alex-2", aliases=("Alex",))
        self.assertEqual(
            store.alias_candidates("alex"),
            ("person:alex-1", "person:alex-2"),
        )
        with self.assertRaises(AmbiguousEntityIdentity):
            store.resolve_surface("Alex")

    def test_frontend_resolver_returns_one_id_per_mention(self):
        store = IdentityStore()
        store.register_entity("person:john", aliases=("John",))
        slotted = slotize_mentions("John found a key", ((0, 4), (13, 16)))
        ids = store.frontend_resolver(slotted)
        self.assertEqual(ids[0], "person:john")
        self.assertTrue(ids[1].startswith("entity#"))


if __name__ == "__main__":
    unittest.main()
