import unittest

from semzip.meaning import Meaning
from semzip.query import WorldQueryEngine
from semzip.reference import quantify
from semzip.schema import validate_meaning
from semzip.world import WorldModel


class ReferenceTests(unittest.TestCase):
    def test_quantifiers_are_distinct_semantics(self):
        meanings = [
            quantify("key", "ALL"),
            quantify("key", "SOME"),
            quantify("key", "NONE"),
            quantify("key", "EXACT", count=3),
            quantify("key", "EXACT", count=4),
        ]
        for meaning in meanings:
            validate_meaning(meaning)
        self.assertEqual(len({meaning.semantic_hash() for meaning in meanings}), 5)

    def test_exact_requires_count(self):
        with self.assertRaises(ValueError):
            quantify("key", "EXACT")

    def test_non_exact_rejects_count(self):
        with self.assertRaises(ValueError):
            quantify("key", "ALL", count=3)

    def test_world_can_enumerate_instances_by_type(self):
        world = WorldModel()
        for subject, type_name in [
            ("key", "key"),
            ("key#2", "key"),
            ("key#3", "key"),
            ("coin", "coin"),
        ]:
            world.apply(
                Meaning.build(
                    "STATE",
                    {"subject": subject, "dimension": "type", "value": type_name},
                )
            )
        query = WorldQueryEngine(world)
        members = query.answer(
            Meaning.build("QUERY_MEMBERS_OF_TYPE", {"type": "key"})
        )
        count = query.answer(Meaning.build("QUERY_COUNT_TYPE", {"type": "key"}))
        self.assertEqual(members.value, ("key", "key#2", "key#3"))
        self.assertEqual(count.value, 3)


if __name__ == "__main__":
    unittest.main()
