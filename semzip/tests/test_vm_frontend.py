import unittest

from semzip.vm_delta import RelationDelta
from semzip.vm_frontend import (
    MentionCandidate,
    compile_raw_utterance,
    ground_patch_slots,
    select_mentions,
)
from semzip.vm_patch import SemanticPatch
from semzip.vm_semantic_parse import AtomicSemanticCandidate


class RawSemanticFrontendTests(unittest.TestCase):
    def test_select_mentions_uses_confidence_without_inventing_spans(self):
        text = "John gave Mary the book."
        candidates = (
            MentionCandidate(0, 4, 0.99),
            MentionCandidate(10, 14, 0.97),
            MentionCandidate(19, 23, 0.96),
            MentionCandidate(5, 9, 0.30),
        )
        self.assertEqual(
            select_mentions(text, candidates),
            ((0, 4), (10, 14), (19, 23)),
        )

    def test_overlapping_high_confidence_mentions_remain_unresolved(self):
        with self.assertRaises(ValueError):
            select_mentions(
                "old brass telescope",
                (
                    MentionCandidate(0, 9, 0.95),
                    MentionCandidate(0, 19, 0.94),
                ),
            )

    def test_slot_patch_is_grounded_back_to_surface_entities(self):
        patch = SemanticPatch.build((
            RelationDelta.build("E2", "E0", "E1", ("owner", "possessor")),
        ))
        grounded = ground_patch_slots(patch, ("John", "Mary", "book"))
        delta = grounded.deltas[0]
        self.assertEqual(delta.subject, "book")
        self.assertEqual(delta.source, "John")
        self.assertEqual(delta.destination, "Mary")

    def test_raw_frontend_runs_mentions_slots_semantics_and_grounding(self):
        text = "John gave Mary the book."

        def mentions(_text):
            return (
                MentionCandidate(0, 4, 0.99),
                MentionCandidate(10, 14, 0.99),
                MentionCandidate(19, 23, 0.99),
            )

        def compiler(slotted):
            if slotted == "E0 gave E1 the E2.":
                patch = SemanticPatch.build((
                    RelationDelta.build("E2", "E0", "E1", ("owner", "possessor")),
                ))
                return (AtomicSemanticCandidate(patch, 0.98, "gift"),)
            return ()

        result = compile_raw_utterance(text, mentions, compiler)
        self.assertIsNotNone(result)
        self.assertEqual(result.slotted.text, "E0 gave E1 the E2.")
        delta = result.grounded_sequence.steps[0].deltas[0]
        self.assertEqual(delta.transition_key(), ("book", "John", "Mary", ("owner", "possessor")))

    def test_raw_frontend_can_return_ordered_sequence(self):
        text = "John to Mary then Mary to Alice"

        def mentions(_text):
            # Surface mentions are intentionally separate here. Coreference resolution
            # is a different layer and is not faked by string equality.
            return (
                MentionCandidate(0, 4, 0.99),
                MentionCandidate(8, 12, 0.99),
                MentionCandidate(18, 22, 0.99),
                MentionCandidate(26, 31, 0.99),
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

        result = compile_raw_utterance(text, mentions, compiler)
        self.assertIsNotNone(result)
        self.assertEqual(len(result.grounded_sequence.steps), 2)


if __name__ == "__main__":
    unittest.main()
