import unittest

from semzip.vm_delta import RelationDelta
from semzip.vm_frontend import MentionCandidate
from semzip.vm_identity_frontend import (
    compile_resolved_utterance,
    distinct_mention_ids,
)
from semzip.vm_patch import SemanticPatch
from semzip.vm_semantic_parse import AtomicSemanticCandidate


class IdentityFrontendTests(unittest.TestCase):
    def test_default_keeps_repeated_surface_mentions_distinct(self):
        text = "Mary to Alice then Mary to Bob"

        def mentions(_text):
            return (
                MentionCandidate(0, 4, 0.99),
                MentionCandidate(8, 13, 0.99),
                MentionCandidate(19, 23, 0.99),
                MentionCandidate(27, 30, 0.99),
            )

        def compiler(span):
            if span == "E0 to E1":
                return (AtomicSemanticCandidate(SemanticPatch.build((
                    RelationDelta.build("book", "E0", "E1", ("owner",)),
                )), 0.99),)
            if span == "E2 to E3":
                return (AtomicSemanticCandidate(SemanticPatch.build((
                    RelationDelta.build("book", "E2", "E3", ("owner",)),
                )), 0.99),)
            return ()

        result = compile_resolved_utterance(text, mentions, compiler)
        self.assertIsNotNone(result)
        self.assertEqual(result.raw.slotted.entities, ("Mary", "Alice", "Mary", "Bob"))
        self.assertEqual(result.entity_ids, ("mention#0", "mention#1", "mention#2", "mention#3"))
        first = result.grounded_sequence.steps[0].deltas[0]
        second = result.grounded_sequence.steps[1].deltas[0]
        self.assertEqual(first.source, "mention#0")
        self.assertEqual(second.source, "mention#2")
        self.assertNotEqual(first.source, second.source)

    def test_explicit_resolver_can_link_coreferent_mentions(self):
        text = "Mary to Alice then Mary to Bob"

        def mentions(_text):
            return (
                MentionCandidate(0, 4, 0.99),
                MentionCandidate(8, 13, 0.99),
                MentionCandidate(19, 23, 0.99),
                MentionCandidate(27, 30, 0.99),
            )

        def compiler(span):
            if span == "E0 to E1":
                return (AtomicSemanticCandidate(SemanticPatch.build((
                    RelationDelta.build("book", "E0", "E1", ("owner",)),
                )), 0.99),)
            if span == "E2 to E3":
                return (AtomicSemanticCandidate(SemanticPatch.build((
                    RelationDelta.build("book", "E2", "E3", ("owner",)),
                )), 0.99),)
            return ()

        def resolver(slotted):
            self.assertEqual(slotted.entities[0], "Mary")
            self.assertEqual(slotted.entities[2], "Mary")
            return ("person:mary", "person:alice", "person:mary", "person:bob")

        result = compile_resolved_utterance(
            text,
            mentions,
            compiler,
            entity_resolver=resolver,
        )
        self.assertEqual(result.entity_ids[0], result.entity_ids[2])
        self.assertEqual(
            result.grounded_sequence.steps[0].deltas[0].source,
            result.grounded_sequence.steps[1].deltas[0].source,
        )

    def test_resolver_must_return_one_identity_per_mention(self):
        text = "John left"

        def mentions(_text):
            return (MentionCandidate(0, 4, 0.99),)

        def compiler(span):
            if span == "E0 left":
                return (AtomicSemanticCandidate(SemanticPatch.build((
                    RelationDelta.build("E0", "here", "away", ("location",)),
                )), 0.99),)
            return ()

        with self.assertRaises(ValueError):
            compile_resolved_utterance(
                text,
                mentions,
                compiler,
                entity_resolver=lambda _slotted: (),
            )

    def test_distinct_id_resolver_is_deterministic(self):
        from semzip.vm_mentions import slotize_mentions
        slotted = slotize_mentions("A met B", ((0, 1), (6, 7)))
        self.assertEqual(distinct_mention_ids(slotted), ("mention#0", "mention#1"))


if __name__ == "__main__":
    unittest.main()
