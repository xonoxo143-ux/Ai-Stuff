import unittest

from semzip.meaning import Meaning
from semzip.story import MiniWorldInterpreter, UnsupportedStorySentence
from semzip.world import WorldModel


STORY = [
    "John owned a red key.",
    "John gave the key to Mary.",
    "Mary put it in the kitchen.",
    "Bob believes the key is still with John.",
    "Later, Mary moved the key to the garage.",
    "John does not know where the key is.",
]


class MeaningTests(unittest.TestCase):
    def test_nested_meaning_is_canonical(self):
        content = Meaning.build(
            "STATE", {"value": "John", "subject": "key", "dimension": "owner"}
        )
        a = Meaning.build("BELIEVE", {"content": content, "holder": "Bob"})
        b = Meaning.build(
            "BELIEVE",
            {
                "holder": "bob",
                "content": Meaning.build(
                    "state",
                    {"dimension": "owner", "subject": "key", "value": "john"},
                ),
            },
        )
        self.assertEqual(a, b)
        self.assertEqual(a.semantic_hash(), b.semantic_hash())

    def test_negation_changes_semantic_identity(self):
        p = Meaning.build(
            "KNOW_VALUE",
            {"holder": "John", "subject": "key", "dimension": "location"},
        )
        self.assertNotEqual(
            p.semantic_hash(),
            Meaning.build("NOT", {"content": p}).semantic_hash(),
        )


class WorldTests(unittest.TestCase):
    def build_story(self):
        interpreter = MiniWorldInterpreter()
        for sentence in STORY:
            interpreter.feed(sentence)
        return interpreter.world

    def test_key_world_gate(self):
        world = self.build_story()
        self.assertEqual(world.fact("key", "owner"), "mary")
        self.assertEqual(world.fact("key", "location"), "garage")
        self.assertEqual(world.previous("key", "location"), "kitchen")
        self.assertEqual(world.fact("key", "color"), "red")
        self.assertEqual(world.latest_belief("bob", "key", "owner"), "john")
        self.assertFalse(world.belief_is_true("bob", "key", "owner"))
        self.assertFalse(world.knows_value("john", "key", "location"))

    def test_belief_does_not_mutate_reality(self):
        world = WorldModel()
        world.apply(
            Meaning.build(
                "STATE", {"subject": "key", "dimension": "owner", "value": "mary"}
            )
        )
        belief = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "john"}
        )
        world.apply(Meaning.build("BELIEVE", {"holder": "bob", "content": belief}))
        self.assertEqual(world.fact("key", "owner"), "mary")
        self.assertEqual(world.latest_belief("bob", "key", "owner"), "john")

    def test_change_history_is_preserved(self):
        world = WorldModel()
        world.apply(
            Meaning.build(
                "STATE", {"subject": "key", "dimension": "location", "value": "table"}
            )
        )
        world.apply(
            Meaning.build(
                "CHANGE", {"subject": "key", "dimension": "location", "after": "kitchen"}
            )
        )
        world.apply(
            Meaning.build(
                "CHANGE", {"subject": "key", "dimension": "location", "after": "garage"}
            )
        )
        self.assertEqual(world.fact("key", "location"), "garage")
        self.assertEqual(world.previous("key", "location"), "kitchen")
        self.assertEqual([x.after for x in world.history], ["kitchen", "garage"])

    def test_change_precondition_catches_contradiction(self):
        world = WorldModel()
        world.apply(
            Meaning.build(
                "STATE", {"subject": "key", "dimension": "owner", "value": "mary"}
            )
        )
        with self.assertRaises(ValueError):
            world.apply(
                Meaning.build(
                    "CHANGE",
                    {
                        "subject": "key",
                        "dimension": "owner",
                        "before": "john",
                        "after": "bob",
                    },
                )
            )

    def test_unknown_knowledge_is_distinct_from_unrepresented(self):
        world = WorldModel()
        self.assertIsNone(world.knows_value("john", "key", "location"))
        q = Meaning.build(
            "KNOW_VALUE",
            {"holder": "john", "subject": "key", "dimension": "location"},
        )
        world.apply(Meaning.build("NOT", {"content": q}))
        self.assertFalse(world.knows_value("john", "key", "location"))

    def test_timeline_queries_arbitrary_past_state(self):
        world = WorldModel()
        world.apply(
            Meaning.build(
                "STATE", {"subject": "key", "dimension": "location", "value": "table"}
            )
        )
        t_table = world.clock
        world.apply(
            Meaning.build(
                "CHANGE", {"subject": "key", "dimension": "location", "after": "kitchen"}
            )
        )
        t_kitchen = world.clock
        world.apply(
            Meaning.build(
                "CHANGE", {"subject": "key", "dimension": "location", "after": "garage"}
            )
        )
        self.assertEqual(world.fact_at("key", "location", t_table), "table")
        self.assertEqual(world.fact_at("key", "location", t_kitchen), "kitchen")
        self.assertEqual(world.fact("key", "location"), "garage")

    def test_modality_is_not_reality(self):
        world = WorldModel()
        p = Meaning.build(
            "STATE", {"subject": "door", "dimension": "open", "value": "true"}
        )
        world.apply(Meaning.build("POSSIBLE", {"content": p}))
        self.assertIsNone(world.fact("door", "open"))
        self.assertEqual(world.modal_statements[0].operator, "POSSIBLE")

    def test_causation_is_explicit_not_inferred_from_order(self):
        world = WorldModel()
        first = Meaning.build("EVENT", {"name": "collision"})
        second = Meaning.build("EVENT", {"name": "glass_break"})
        relation = Meaning.build("CAUSE", {"cause": first, "effect": second})
        world.apply(relation)
        self.assertEqual(world.causal_relations, (relation,))

    def test_ontology_transitivity(self):
        world = WorldModel()
        for child, parent in [
            ("dog", "mammal"),
            ("mammal", "animal"),
            ("animal", "living_entity"),
        ]:
            world.apply(Meaning.build("IS_A", {"child": child, "parent": parent}))
        self.assertTrue(world.ontology.is_a("dog", "living_entity"))
        self.assertFalse(world.ontology.is_a("dog", "vehicle"))

    def test_unsupported_story_fails_loudly(self):
        interpreter = MiniWorldInterpreter()
        with self.assertRaises(UnsupportedStorySentence):
            interpreter.feed("John probably hid the key because Mary was angry.")


if __name__ == "__main__":
    unittest.main()
