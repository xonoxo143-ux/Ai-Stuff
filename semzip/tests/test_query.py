import unittest

from semzip.meaning import Meaning
from semzip.query import WorldQueryEngine
from semzip.story import MiniWorldInterpreter


STORY = [
    "John owned a red key.",
    "John gave the key to Mary.",
    "Mary put it in the kitchen.",
    "Bob believes the key is still with John.",
    "Later, Mary moved the key to the garage.",
    "John does not know where the key is.",
]


class QueryTests(unittest.TestCase):
    def setUp(self):
        interpreter = MiniWorldInterpreter()
        for sentence in STORY:
            interpreter.feed(sentence)
        self.query = WorldQueryEngine(interpreter.world)

    def q(self, operator, **roles):
        return self.query.answer(Meaning.build(operator, roles)).value

    def test_world_gate_through_semantic_queries(self):
        self.assertEqual(
            self.q("QUERY_VALUE", subject="key", dimension="owner"), "mary"
        )
        self.assertEqual(
            self.q("QUERY_VALUE", subject="key", dimension="location"), "garage"
        )
        self.assertEqual(
            self.q("QUERY_PREVIOUS_VALUE", subject="key", dimension="location"),
            "kitchen",
        )
        self.assertEqual(
            self.q(
                "QUERY_BELIEF",
                holder="bob",
                subject="key",
                dimension="owner",
            ),
            "john",
        )
        self.assertFalse(
            self.q(
                "QUERY_BELIEF_TRUE",
                holder="bob",
                subject="key",
                dimension="owner",
            )
        )
        self.assertFalse(
            self.q(
                "QUERY_KNOWS_VALUE",
                holder="john",
                subject="key",
                dimension="location",
            )
        )

    def test_unknown_answer_is_explicit(self):
        answer = self.query.answer(
            Meaning.build(
                "QUERY_VALUE", {"subject": "key", "dimension": "weight"}
            )
        )
        self.assertFalse(answer.known)
        self.assertIsNone(answer.value)


if __name__ == "__main__":
    unittest.main()
